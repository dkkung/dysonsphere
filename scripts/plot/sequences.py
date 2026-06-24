"""
Amino acid and nucleotide sequences colored by biochemical/chemical identity.
Protein: rendered with proteins and proteins2 palettes.
Nucleotide: rendered with the nucleotide palette.
Renders in Courier at fontSize=7.
H (histidine) grouped with polar (imidazole side chain; H-bond donor/acceptor).
"""

import altair as alt
import polars as pl

import dysonsphere as ds
from dysonsphere.palettes import colors

# ── Protein sequence ──────────────────────────────────────────────────────────

SEQ = (
    "MTMTLHTKASGMALLHQIQGNELEPLNRPQLKIPLERPLGEVYLDSSKPAVYNYPEGAAY"
    "EFNAAAAANAQVYGQTGLPYGPGSEAAAFGSNGLGGFPPLNSVSPSPLMLLHPPPQLSPF"
    "LQPHGQQVPYYLENEPSGYTVREAGPPAFYRPNSDNRRQGGRERLASTNDKGSMAMESAK"
    "ETRYCAVCNDYASGYHYGVWSCEGCKAFFKRSIQGHNDYMCPATNQCTIDKNRRKSCQAC"
    "RLRKCYEVGMMKGGIRKDRRGGRMLKHKRQRDDGEGRGEVGSAGDMRAANLWPSPLMIKR"
    "SKKNSLALSLTADQMVSALLDAEPPILYSEYDPTRPFSEASMMGLLTNLADRELVHMINW"
    "AKRVPGFVDLTLHDQVHLLECAWLEILMIGLVWRSMEHPGKLLFAPNLLLDRNQGKCVEG"
    "MVEIFDMLLATSSRFRMMNLQGEEFVCLKSIILLNSGVYTFLSSTLKSLEEKDHIHRVLD"
    "KITDTLIHLMAKAGLTLQQQHQRLAQLLLILSHIRHMSNKGMEHLYSMKCKNVVPLYDLL"
    "LEMLDAHRLHAPTSRGGASVEETDQSHLATAGSTSSHSLQKYYITGEAEGFPATV"
)

_AA_GROUP: dict[str, str] = {}
for _aa in "AILMV":
    _AA_GROUP[_aa] = "hydrophobic"
for _aa in "FYW":
    _AA_GROUP[_aa] = "aromatic"
for _aa in "RK":
    _AA_GROUP[_aa] = "positive"
for _aa in "DE":
    _AA_GROUP[_aa] = "negative"
for _aa in "STNQH":
    _AA_GROUP[_aa] = "polar"
_AA_GROUP["P"] = "proline"
_AA_GROUP["G"] = "glycine"
_AA_GROUP["C"] = "cysteine"

GROUP_ORDER = [
    "hydrophobic",
    "aromatic",
    "positive",
    "negative",
    "polar",
    "proline",
    "glycine",
    "cysteine",
]

# ── Nucleotide sequence ───────────────────────────────────────────────────────

NUC_ORDER = ["A", "T", "G", "C", "U"]

# Encodes the first 120 AAs of SEQ using common human codons.
NUC_SEQ = (
    "ATGACAATGACTCTGCACACGAAAGCCTCCGGCATGGCCCTGCTGCACCAGATCCAGGGC"
    "AACGAGCTGGAACCCCTGAACCGGCCGCAGCTGAAGATTCCCCTGGAACGGCCCCTGGGC"
    "GAGGTGTACCTGGACAGCAGCAAGCCCGCCGTGTACAACTACCCGGAGGGCGCCGCCTAC"
    "GAGTTCAACGCCGCCGCCGCCGCCAACGCGCAGGTGTACGGCCAGACGGGCCTGCCCTAC"
    "GGCCCGGGCTCGGAGGCCGCGGCCTTTGGCTCCAACGGCCTGGGCGGCTTCCCCCCGCTG"
    "AACAGCGTGTCGCCCAGCCCCCTGATGCTGCTGCACCCGCCCCCCCAGCTGTCCCCCTTC"
)

# ── Layout ────────────────────────────────────────────────────────────────────

CHARS_PER_LINE = 60
FONT_SIZE = 7
CHAR_WIDTH = FONT_SIZE * 0.6  # Courier: advance width = 0.6 × em
LINE_HEIGHT = FONT_SIZE * 1.5  # 1.5× line spacing

n_aa_lines = (len(SEQ) - 1) // CHARS_PER_LINE + 1
n_nuc_lines = (len(NUC_SEQ) - 1) // CHARS_PER_LINE + 1
chart_w = CHARS_PER_LINE * CHAR_WIDTH  # 252.0 px
aa_chart_h = n_aa_lines * LINE_HEIGHT  # 105.0 px
nuc_chart_h = n_nuc_lines * LINE_HEIGHT  # 63.0 px

# x and y pre-computed as pixel positions; domain matches chart dimensions so
# data coords map 1:1 to SVG pixels (x: domain=[0,w]; y: domain=[h,0] → top-to-bottom)
aa_df = pl.DataFrame(
    [
        {
            "aa": aa,
            "group": _AA_GROUP.get(aa, "unknown"),
            "x": (i % CHARS_PER_LINE) * CHAR_WIDTH,
            "y": (i // CHARS_PER_LINE) * LINE_HEIGHT,
        }
        for i, aa in enumerate(SEQ)
    ]
)

nuc_df = pl.DataFrame(
    [
        {
            "base": base,
            "x": (i % CHARS_PER_LINE) * CHAR_WIDTH,
            "y": (i // CHARS_PER_LINE) * LINE_HEIGHT,
        }
        for i, base in enumerate(NUC_SEQ)
    ]
)

ds.theme(chartWidth=int(chart_w), chartHeight=int(aa_chart_h))


def seq_chart(palette_name: str) -> alt.Chart:
    pal = colors[palette_name]
    return (
        alt.Chart(aa_df)
        .mark_text(font="Courier", fontSize=FONT_SIZE, align="left", baseline="top")
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, chart_w]), axis=None),
            y=alt.Y("y:Q", scale=alt.Scale(domain=[aa_chart_h, 0]), axis=None),
            text="aa:N",
            color=alt.Color(
                "group:N",
                scale=alt.Scale(domain=GROUP_ORDER, range=pal),
                legend=alt.Legend(title=None),
            ),
        )
        .properties(width=chart_w, height=aa_chart_h, title=palette_name)
    )


def nuc_chart() -> alt.Chart:
    pal = colors["nucleotides"]
    return (
        alt.Chart(nuc_df)
        .mark_text(font="Courier", fontSize=FONT_SIZE, align="left", baseline="top")
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[0, chart_w]), axis=None),
            y=alt.Y("y:Q", scale=alt.Scale(domain=[nuc_chart_h, 0]), axis=None),
            text="base:N",
            color=alt.Color(
                "base:N",
                scale=alt.Scale(domain=NUC_ORDER, range=pal),
                legend=alt.Legend(title=None),
            ),
        )
        .properties(width=chart_w, height=nuc_chart_h, title="nucleotide")
    )


chart = alt.vconcat(
    seq_chart("proteins"),
    nuc_chart(),
    spacing=20,
).resolve_scale(color="independent")

ds.save(chart, "sequences")
print("saved sequences")
