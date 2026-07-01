"""Pure statistical computation (no Altair).

Backs the chart-annotation constructors in ``layers.py`` (notably
``add_comparisons``).  Holds the omnibus tests, hand-rolled post-hoc tests,
effect-size functions, and the descriptive report builder.  Nothing here
imports Altair, so it is unit-testable in isolation.

The post-hoc tests scipy does not ship (Dunn, Nemenyi, Games-Howell) are
implemented here from scipy primitives (``rankdata``, ``norm``,
``studentized_range``) rather than taking a dependency on ``scikit-posthocs``
(which would drag in statsmodels + seaborn + matplotlib).
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field

import numpy as np

# Omnibus tests ("are *any* of the groups different?").
_OMNIBUS_TESTS = {"anova", "kruskal", "friedman", "alexandergovern"}

# Display names + the post-hoc each omnibus test defaults to.
_OMNIBUS_NAMES = {
    "anova": "ANOVA",
    "kruskal": "Kruskal-Wallis",
    "friedman": "Friedman",
    "alexandergovern": "Alexander-Govern",
}
_POSTHOC_DEFAULTS = {
    "anova": "tukey_hsd",
    "alexandergovern": "games_howell",
    "kruskal": "dunn",
    "friedman": "nemenyi",
}

# Pairwise tests usable directly (existing behaviour) or as a post-hoc fallback.
_PAIRWISE_TESTS = {"mannwhitneyu", "ttest_ind", "ttest_rel", "wilcoxon"}

# Correlation methods (add_correlation). Only "pearson" implies a straight line.
_CORRELATION_METHODS = {
    "pearson": ("Pearson", "r", "pearson_r"),
    "spearman": ("Spearman", "ρ", "spearman_rho"),
    "kendall": ("Kendall", "τ", "kendall_tau"),
}

# Post-hoc tests treated as parametric (→ Cohen's d effect size); the rest are
# rank-based (→ rank-biserial effect size).
_PARAMETRIC_POSTHOC = {"tukey_hsd", "games_howell", "ttest_ind", "ttest_rel"}

# Human-readable names for pairwise / post-hoc tests — used for the on-plot test label.
_TEST_DISPLAY = {
    "mannwhitneyu": "Mann-Whitney U",
    "ttest_ind": "Student's t-test",
    "ttest_rel": "Paired t-test",
    "wilcoxon": "Wilcoxon signed-rank",
    "tukey_hsd": "Tukey HSD",
    "dunn": "Dunn's test",
    "nemenyi": "Nemenyi test",
    "games_howell": "Games-Howell",
}


# ── Report registry ────────────────────────────────────────────────────────
# add_comparisons() pushes a structured report *record* (a plain dict — the single
# source of truth) here; export.save() drains it, renders the human-readable
# text from each record for the metadata description, and embeds the raw records
# as JSON under usermeta.dysonsphere.statistics in the Vega-Lite spec.  Module-
# level state is the only channel available because Altair strips custom metadata
# when layers are combined with ``+`` (see CLAUDE.md).
_REPORTS: list[dict] = []

# Machine-readable names for the effect-size symbols used in the text report.
_EFFECT_NAMES = {
    "η²": "eta_squared",
    "ε²": "epsilon_squared",
    "W": "kendalls_w",
    "d": "cohens_d",
    "r": "rank_biserial",
}


def _push_report(record: dict) -> None:
    _REPORTS.append(record)


def _drain_reports() -> list[dict]:
    """Return all queued report records (de-duplicated, order-preserving) and clear the queue.

    De-duplication collapses the identical records produced when ``save()`` rebuilds
    a callable chart once per light/dark variant.  Records are dicts, so they are
    compared by their canonical JSON serialization.
    """
    import json

    seen: set[str] = set()
    out: list[dict] = []
    for r in _REPORTS:
        key = json.dumps(r, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            out.append(r)
    _REPORTS.clear()
    return out


# ── Omnibus result ─────────────────────────────────────────────────────────
@dataclass
class _OmnibusResult:
    test: str  # key, e.g. "anova"
    name: str  # display, e.g. "ANOVA"
    stat: float
    pvalue: float
    statSymbol: str  # "F", "H", "χ²", "A"
    df: tuple[int, ...]  # (df1, df2) for F; (df,) otherwise
    effectName: str  # "η²", "ε²", "W"
    effectSize: float
    descriptives: list[dict] = field(default_factory=list)


# ── Descriptive statistics ─────────────────────────────────────────────────
def _describe(label: str, x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    return {
        "label": label,
        "n": int(x.size),
        "mean": float(np.mean(x)),
        "sd": float(np.std(x, ddof=1)) if x.size > 1 else None,
        "median": float(np.median(x)),
        "q1": float(np.percentile(x, 25)),
        "q3": float(np.percentile(x, 75)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def _describe_all(groups: list[np.ndarray], labels: list) -> list[dict]:
    return [_describe(str(lab), g) for lab, g in zip(labels, groups)]


# ── Effect sizes (omnibus) ─────────────────────────────────────────────────
def _eta_squared(groups: list[np.ndarray]) -> float:
    """Classic eta-squared: SS_between / SS_total, computed directly from the data."""
    all_vals = np.concatenate(groups)
    grand = all_vals.mean()
    ss_total = float(np.sum((all_vals - grand) ** 2))
    ss_between = float(sum(g.size * (g.mean() - grand) ** 2 for g in groups))
    return ss_between / ss_total if ss_total > 0 else 0.0


def _epsilon_squared(h: float, n_total: int) -> float:
    """Epsilon-squared for Kruskal-Wallis: H / (N - 1)."""
    return h / (n_total - 1) if n_total > 1 else 0.0


def _kendalls_w(chi2: float, n_subjects: int, k_groups: int) -> float:
    """Kendall's W for Friedman: χ² / (n * (k - 1))."""
    denom = n_subjects * (k_groups - 1)
    return chi2 / denom if denom > 0 else 0.0


# ── Omnibus runners ────────────────────────────────────────────────────────
def _run_omnibus(test: str, groups: list[np.ndarray], labels: list) -> _OmnibusResult:
    from scipy import stats as _stats

    if test not in _OMNIBUS_TESTS:
        raise ValueError(f"Unknown omnibus test {test!r}. Choose from: {sorted(_OMNIBUS_TESTS)}")

    k = len(groups)
    n_total = int(sum(g.size for g in groups))
    name = _OMNIBUS_NAMES[test]
    descriptives = _describe_all(groups, labels)

    if test == "anova":
        res = _stats.f_oneway(*groups)
        stat, pval = float(res.statistic), float(res.pvalue)
        df = (k - 1, n_total - k)
        return _OmnibusResult(test, name, stat, pval, "F", df, "η²", _eta_squared(groups), descriptives)

    if test == "kruskal":
        res = _stats.kruskal(*groups)
        stat, pval = float(res.statistic), float(res.pvalue)
        return _OmnibusResult(
            test, name, stat, pval, "H", (k - 1,), "ε²", _epsilon_squared(stat, n_total), descriptives
        )

    if test == "friedman":
        lengths = {g.size for g in groups}
        if len(lengths) != 1:
            raise ValueError("friedman requires balanced data: every group must have the same number of observations.")
        res = _stats.friedmanchisquare(*groups)
        stat, pval = float(res.statistic), float(res.pvalue)
        n_subjects = groups[0].size
        return _OmnibusResult(
            test, name, stat, pval, "χ²", (k - 1,), "W", _kendalls_w(stat, n_subjects, k), descriptives
        )

    # alexandergovern
    res = _stats.alexandergovern(*groups)
    stat, pval = float(res.statistic), float(res.pvalue)
    return _OmnibusResult(test, name, stat, pval, "A", (k - 1,), "η²", _eta_squared(groups), descriptives)


# ── Correlation ────────────────────────────────────────────────────────────
def _run_correlation(method: str, x: np.ndarray, y: np.ndarray) -> dict:
    """Compute a correlation coefficient (+ OLS fit for Pearson) between two continuous vars."""
    from scipy import stats as _stats

    if method not in _CORRELATION_METHODS:
        raise ValueError(f"method must be one of {sorted(_CORRELATION_METHODS)}, got {method!r}")
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    _, symbol, machine = _CORRELATION_METHODS[method]

    if method == "pearson":
        res = _stats.linregress(x, y)
        coef = float(res.rvalue)
        return {
            "method": method,
            "symbol": symbol,
            "machine": machine,
            "coefficient": coef,
            "rSquared": coef * coef,
            "pvalue": float(res.pvalue),
            "slope": float(res.slope),
            "intercept": float(res.intercept),
            "n": int(x.size),
        }

    res = _stats.spearmanr(x, y) if method == "spearman" else _stats.kendalltau(x, y)
    return {
        "method": method,
        "symbol": symbol,
        "machine": machine,
        "coefficient": float(res.statistic),
        "rSquared": None,  # not meaningful for rank correlations
        "pvalue": float(res.pvalue),
        "slope": None,
        "intercept": None,
        "n": int(x.size),
    }


def _make_correlation_record(result: dict, xCol: str, yCol: str) -> dict:
    """Structured record for a correlation (the single source of truth, → usermeta)."""
    return {
        "kind": "correlation",
        "method": result["method"],
        "x": xCol,
        "y": yCol,
        "n": result["n"],
        "coefficient": {"name": result["machine"], "symbol": result["symbol"], "value": result["coefficient"]},
        "rSquared": result["rSquared"],
        "pvalue": _clamp_p(result["pvalue"]),
        "fit": None if result["slope"] is None else {"slope": result["slope"], "intercept": result["intercept"]},
    }


# ── Post-hoc tests (hand-rolled) ───────────────────────────────────────────
def _dunn_matrix(groups: list[np.ndarray]) -> np.ndarray:
    """Dunn's test (post-hoc for Kruskal-Wallis). Returns a k×k matrix of unadjusted p-values.

    z_ij = (R̄_i − R̄_j) / sqrt( [N(N+1)/12 − Σ(t³−t)/(12(N−1))] · (1/n_i + 1/n_j) )
    where R̄ are mean ranks over the pooled, tie-averaged ranking.
    """
    from scipy.stats import norm, rankdata

    k = len(groups)
    sizes = [g.size for g in groups]
    n = int(sum(sizes))
    pooled = np.concatenate(groups)
    ranks = rankdata(pooled)
    mean_ranks, idx = [], 0
    for s in sizes:
        mean_ranks.append(ranks[idx : idx + s].mean())
        idx += s

    _, counts = np.unique(pooled, return_counts=True)
    ties = float(np.sum(counts**3 - counts))
    sigma = (n * (n + 1) / 12.0) - ties / (12.0 * (n - 1))

    p = np.ones((k, k))
    for i in range(k):
        for j in range(i + 1, k):
            se = math.sqrt(sigma * (1.0 / sizes[i] + 1.0 / sizes[j]))
            z = (mean_ranks[i] - mean_ranks[j]) / se
            p[i, j] = p[j, i] = float(2 * norm.sf(abs(z)))
    return p


def _games_howell_matrix(groups: list[np.ndarray]) -> np.ndarray:
    """Games-Howell (post-hoc for unequal-variance / Welch-type designs). k×k p-value matrix.

    t = (m_i − m_j) / sqrt(s_i²/n_i + s_j²/n_j), with Welch-Satterthwaite df, and
    p from the studentized range: q = |t|·√2, p = sr.sf(q, k, df).
    """
    from scipy.stats import studentized_range

    k = len(groups)
    means = [float(g.mean()) for g in groups]
    var = [float(g.var(ddof=1)) for g in groups]
    sizes = [g.size for g in groups]

    p = np.ones((k, k))
    for i in range(k):
        for j in range(i + 1, k):
            vi, vj = var[i] / sizes[i], var[j] / sizes[j]
            t = (means[i] - means[j]) / math.sqrt(vi + vj)
            df = (vi + vj) ** 2 / (vi**2 / (sizes[i] - 1) + vj**2 / (sizes[j] - 1))
            q = abs(t) * math.sqrt(2)
            p[i, j] = p[j, i] = float(studentized_range.sf(q, k, df))
    return p


def _nemenyi_matrix(groups: list[np.ndarray]) -> np.ndarray:
    """Nemenyi (post-hoc for Friedman). Requires balanced data. k×k p-value matrix.

    Within-block ranks → mean rank per treatment. q = |R̄_i − R̄_j| / sqrt(k(k+1)/(6n)),
    p = sr.sf(q·√2, k, ∞).
    """
    from scipy.stats import rankdata, studentized_range

    lengths = {g.size for g in groups}
    if len(lengths) != 1:
        raise ValueError("nemenyi requires balanced data: every group must have the same number of observations.")

    data = np.column_stack(groups)  # n_subjects × k
    n, k = data.shape
    ranks = np.apply_along_axis(rankdata, 1, data)
    mean_ranks = ranks.mean(axis=0)

    p = np.ones((k, k))
    denom = math.sqrt(k * (k + 1) / (6.0 * n))
    for i in range(k):
        for j in range(i + 1, k):
            q = abs(mean_ranks[i] - mean_ranks[j]) / denom
            p[i, j] = p[j, i] = float(studentized_range.sf(q * math.sqrt(2), k, np.inf))
    return p


def _tukey_matrix(groups: list[np.ndarray]) -> np.ndarray:
    from scipy import stats as _stats

    return np.asarray(_stats.tukey_hsd(*groups).pvalue, dtype=float)


def _adjust(pvals: list[float], method: str | None, m: int) -> list[float]:
    """Apply a multiple-comparison correction to a flat list of p-values."""
    if method is None:
        return list(pvals)
    if method == "bonferroni":
        return [min(p * m, 1.0) for p in pvals]
    if method == "holm":
        order = sorted(range(len(pvals)), key=lambda i: pvals[i])
        out = [0.0] * len(pvals)
        running = 0.0
        for rank, i in enumerate(order):
            running = max(running, min(pvals[i] * (m - rank), 1.0))
            out[i] = running
        return out
    raise ValueError(f"correction must be None, 'bonferroni', or 'holm', got {method!r}")


def _post_hoc_matrix(name: str, groups: list[np.ndarray], correction: str | None) -> np.ndarray:
    """Return a k×k matrix of post-hoc p-values, corrected over all unique pairs.

    ``tukey_hsd`` ignores ``correction`` (its correction is built in).
    """
    builders = {
        "tukey_hsd": _tukey_matrix,
        "dunn": _dunn_matrix,
        "nemenyi": _nemenyi_matrix,
        "games_howell": _games_howell_matrix,
    }
    if name not in builders:
        raise ValueError(f"Unknown post-hoc test {name!r}. Choose from: {sorted(builders)}")

    mat = builders[name](groups)
    if name == "tukey_hsd" or correction is None:
        return mat

    k = mat.shape[0]
    pairs = [(i, j) for i in range(k) for j in range(i + 1, k)]
    adjusted = _adjust([mat[i, j] for i, j in pairs], correction, len(pairs))
    out = np.ones_like(mat)
    for (i, j), p in zip(pairs, adjusted):
        out[i, j] = out[j, i] = p
    return out


# ── Pairwise effect sizes ──────────────────────────────────────────────────
def _cohens_d(a: np.ndarray, b: np.ndarray, paired: bool) -> float:
    if paired:
        d = a - b
        sd = np.std(d, ddof=1)
        return float(np.mean(d) / sd) if sd > 0 else 0.0
    na, nb = a.size, b.size
    sp = math.sqrt(((na - 1) * np.var(a, ddof=1) + (nb - 1) * np.var(b, ddof=1)) / (na + nb - 2))
    return float((a.mean() - b.mean()) / sp) if sp > 0 else 0.0


def _rank_biserial(a: np.ndarray, b: np.ndarray) -> float:
    """Rank-biserial correlation from the Mann-Whitney U: r = 1 − 2U/(n_a·n_b)."""
    from scipy.stats import mannwhitneyu

    u = float(mannwhitneyu(a, b, alternative="two-sided").statistic)
    return 1.0 - (2.0 * u) / (a.size * b.size)


def _pair_effect(a: np.ndarray, b: np.ndarray, *, parametric: bool, paired: bool = False) -> tuple[str, float]:
    if parametric:
        return "d", _cohens_d(a, b, paired)
    return "r", _rank_biserial(a, b)


# ── Report record (single source of truth) ─────────────────────────────────
def _clamp_p(p: float) -> float:
    """Clamp a p-value away from an impossible ``0.0``.

    A p-value is strictly positive; scipy returns ``0.0`` only when the true value
    underflows below the smallest representable float.  We store the smallest positive
    float instead, so the record (and the JSON) never claim ``P = 0``.  The text report
    renders this clamp value with ``<`` (see ``_fmt_p``) because the true value is
    genuinely below float precision.
    """
    return sys.float_info.min if p == 0.0 else p


def _make_record(
    *,
    test: str,
    is_omnibus: bool,
    omnibus: _OmnibusResult | None,
    descriptives: list[dict],
    comparisons: list[dict],
    comparison_test: str | None,
    correction: str | None,
    pvalues_provided: bool,
) -> dict:
    """Build the structured report record.

    This dict is the single source of truth: ``_render_report`` turns it into the
    plain-text report, and ``export.save`` embeds it verbatim under
    ``usermeta.dysonsphere.statistics``.  ``comparisons`` is the internal list of
    dicts with keys ``g1``/``g2``/``pvalue`` and optionally ``effectName``/``effect``.
    """

    def _effect(symbol: str | None, value) -> dict | None:
        if symbol is None:
            return None
        return {"name": _EFFECT_NAMES.get(symbol, symbol), "symbol": symbol, "value": value}

    record: dict = {
        "kind": "omnibus" if is_omnibus else "pairwise",
        "test": None if pvalues_provided else test,
        "groups": descriptives,
    }
    if omnibus is not None:
        record["omnibus"] = {
            "name": omnibus.name,
            "statistic": {"symbol": omnibus.statSymbol, "value": omnibus.stat, "df": list(omnibus.df)},
            "pvalue": _clamp_p(omnibus.pvalue),
            "effect": _effect(omnibus.effectName, omnibus.effectSize),
        }
    record["comparisons"] = {
        "test": comparison_test,
        "correction": correction,
        "pairs": [
            {
                "group1": c["g1"],
                "group2": c["g2"],
                "pvalue": _clamp_p(c["pvalue"]),
                "effect": _effect(c.get("effectName"), c.get("effect")),
            }
            for c in comparisons
        ],
    }
    return record


# ── Text report (rendered from a record) ───────────────────────────────────
# The report/metadata uses a fixed 3 significant figures — independent of the on-plot
# label's theme sigFigs, so a cosmetic on-plot choice never coarsens the record.
_REPORT_SIGFIGS = 3


def _fmt(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.{_REPORT_SIGFIGS}g}"


def _fmt_p(p: float) -> str:
    """Format a report p-value at 3 significant figures — never floored.

    ``%g`` keeps ordinary p-values as readable decimals (``= 0.032``) and switches
    tiny ones to e-notation (``= 1.22e-11``) automatically.  This is the *record*
    format and is independent of the on-plot label style (``notation``/``sigFigs``).
    The one clamp-value (see ``_clamp_p``) is rendered with ``<`` because the true
    value is genuinely below float precision.
    """
    if p == sys.float_info.min:
        return f"< {sys.float_info.min:.{_REPORT_SIGFIGS}g}"
    return f"= {p:.{_REPORT_SIGFIGS}g}"


def _render_correlation(record: dict) -> str:
    method = _CORRELATION_METHODS[record["method"]][0]
    title = f"Statistics | Correlation | {method}"
    lines: list[str] = [title, "─" * len(title), ""]
    c = record["coefficient"]
    parts = [f"{c['symbol']} = {_fmt(c['value'])}"]
    if record["rSquared"] is not None:
        parts.append(f"r² = {_fmt(record['rSquared'])}")
    parts.append(f"P {_fmt_p(record['pvalue'])}")
    lines.append(", ".join(parts))
    if record["fit"] is not None:
        f = record["fit"]
        sign = "+" if f["intercept"] >= 0 else "-"
        lines.append(f"Fit: y = {_fmt(f['slope'])}x {sign} {_fmt(abs(f['intercept']))}")
    lines.append(f"n = {record['n']}  ({record['x']} vs {record['y']})")
    return "\n".join(lines)


def _render_report(record: dict) -> str:
    """Render the plain-text descriptive + effect-size report from a record dict."""
    if record["kind"] == "correlation":
        return _render_correlation(record)
    if record["kind"] == "omnibus":
        title = f"Statistics | Omnibus | {record['omnibus']['name']}"
    elif record["test"] is None:
        title = "Statistics | Pairwise comparisons | user p-values"
    else:
        title = f"Statistics | Pairwise comparisons | {record['test']}"

    lines: list[str] = [title, "─" * len(title), ""]

    if record["kind"] == "omnibus":
        o = record["omnibus"]
        df_str = ", ".join(str(d) for d in o["statistic"]["df"])
        stat = f"{o['statistic']['symbol']}({df_str}) = {_fmt(o['statistic']['value'])}"
        lines.append(f"{stat}, P {_fmt_p(o['pvalue'])}")
        lines.append(f"Effect size: {o['effect']['symbol']} = {_fmt(o['effect']['value'])}")
        lines.append("")

    lines.append("Group descriptives:")
    groups = record["groups"]
    width = max((len(g["label"]) for g in groups), default=0)
    for g in groups:
        lines.append(
            f"  {g['label']:<{width}}  n={g['n']:<4d} mean={_fmt(g['mean'])}  sd={_fmt(g['sd'])}  "
            f"median={_fmt(g['median'])}  IQR=[{_fmt(g['q1'])}, {_fmt(g['q3'])}]  "
            f"range=[{_fmt(g['min'])}, {_fmt(g['max'])}]"
        )

    pairs = record["comparisons"]["pairs"]
    if pairs:
        name = record["comparisons"]["test"]
        corr = record["comparisons"].get("correction")
        label = "Post-hoc" if record["kind"] == "omnibus" else "Comparisons"
        suffix = ", ".join(x for x in (name, corr) if x)
        lines.append("")
        lines.append(f"{label}{f' ({suffix})' if suffix else ''}:")
        pair_width = max(len(f"{p['group1']} vs {p['group2']}") for p in pairs)
        for p in pairs:
            pair = f"{p['group1']} vs {p['group2']}"
            line = f"  {pair:<{pair_width}}  P {_fmt_p(p['pvalue'])}"
            if p["effect"] is not None:
                line += f"  {p['effect']['symbol']} = {_fmt(p['effect']['value'])}"
            lines.append(line)

    return "\n".join(lines)
