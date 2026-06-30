"""Pure statistical computation (no Altair).

Backs the chart-annotation constructors in ``layers.py`` (notably
``add_pvalue``).  Holds the omnibus tests, hand-rolled post-hoc tests,
effect-size functions, and the descriptive report builder.  Nothing here
imports Altair, so it is unit-testable in isolation.

The post-hoc tests scipy does not ship (Dunn, Nemenyi, Games-Howell) are
implemented here from scipy primitives (``rankdata``, ``norm``,
``studentized_range``) rather than taking a dependency on ``scikit-posthocs``
(which would drag in statsmodels + seaborn + matplotlib).
"""

from __future__ import annotations

import math
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

# Post-hoc tests treated as parametric (→ Cohen's d effect size); the rest are
# rank-based (→ rank-biserial effect size).
_PARAMETRIC_POSTHOC = {"tukey_hsd", "games_howell", "ttest_ind", "ttest_rel"}


# ── Report registry ────────────────────────────────────────────────────────
# add_pvalue() pushes each generated report here; export.save() drains it and
# appends the text to the export metadata.  Module-level state is the only
# channel available because Altair strips custom metadata when layers are
# combined with ``+`` (see CLAUDE.md).
_REPORTS: list[str] = []


def _push_report(text: str) -> None:
    _REPORTS.append(text)


def _drain_reports() -> list[str]:
    """Return all queued reports (de-duplicated, order-preserving) and clear the queue.

    De-duplication collapses the identical reports produced when ``save()`` rebuilds
    a callable chart once per light/dark variant.
    """
    seen: set[str] = set()
    out: list[str] = []
    for r in _REPORTS:
        if r not in seen:
            seen.add(r)
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
        "sd": float(np.std(x, ddof=1)) if x.size > 1 else float("nan"),
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


# ── Report builder ─────────────────────────────────────────────────────────
def _fmt(x: float, decimals: int = 3) -> str:
    return f"{x:.{decimals}f}"


def _fmt_p(p: float, decimals: int = 3) -> str:
    threshold = 10 ** (-decimals)
    return f"< {_fmt(threshold, decimals)}" if p < threshold else f"= {_fmt(p, decimals)}"


def _build_report(
    *,
    title: str,
    descriptives: list[dict],
    omnibus: _OmnibusResult | None = None,
    comparisons: list[dict] | None = None,
    comparisonName: str | None = None,
    comparisonLabel: str = "Post-hoc",
) -> str:
    """Assemble the plain-text descriptive + effect-size report.

    ``comparisons`` is a list of dicts with keys ``g1``, ``g2``, ``pvalue`` and
    optionally ``effectName``/``effect``.
    """
    lines: list[str] = [f"=== {title} ==="]

    if omnibus is not None:
        df_str = ", ".join(str(d) for d in omnibus.df)
        stat = f"{omnibus.statSymbol}({df_str}) = {_fmt(omnibus.stat, 3)}"
        lines.append(f"{omnibus.name}: {stat}, P {_fmt_p(omnibus.pvalue)}")
        lines.append(f"Effect size: {omnibus.effectName} = {_fmt(omnibus.effectSize, 3)}")
        lines.append("")

    lines.append("Group descriptives:")
    width = max((len(d["label"]) for d in descriptives), default=0)
    for d in descriptives:
        lines.append(
            f"  {d['label']:<{width}}  n={d['n']:<4d} mean={_fmt(d['mean'])}  sd={_fmt(d['sd'])}  "
            f"median={_fmt(d['median'])}  IQR=[{_fmt(d['q1'])}, {_fmt(d['q3'])}]  "
            f"range=[{_fmt(d['min'])}, {_fmt(d['max'])}]"
        )

    if comparisons:
        lines.append("")
        lines.append(f"{comparisonLabel}{f' ({comparisonName})' if comparisonName else ''}:")
        pair_width = max(len(f"{c['g1']} vs {c['g2']}") for c in comparisons)
        for c in comparisons:
            pair = f"{c['g1']} vs {c['g2']}"
            line = f"  {pair:<{pair_width}}  P {_fmt_p(c['pvalue'])}"
            if c.get("effectName") is not None:
                line += f"  {c['effectName']} = {_fmt(c['effect'])}"
            lines.append(line)

    return "\n".join(lines)
