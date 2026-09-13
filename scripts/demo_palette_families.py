"""Render the four numbered categorical/diverging palette families."""

from pathlib import Path

import altair as alt

import dysonsphere as ds


def _categorical_swatches() -> alt.Chart:
    rows = [
        {"palette": palette, "slot": slot, "hex": color}
        for palette in ("cat1", "cat2", "cat3", "cat4")
        for slot, color in enumerate(ds.palettes.colors[palette])
    ]
    return (
        alt.Chart(ds.ext.internal_data(rows))
        .mark_rect()
        .encode(
            x=alt.X("slot:O", title="categorical slot"),
            y=alt.Y("palette:N", sort=["cat1", "cat2", "cat3", "cat4"], title=None),
            color=alt.Color("hex:N", scale=None, legend=None),
            tooltip=["palette:N", "slot:O", "hex:N"],
        )
        .properties(title="Categorical families", width=720, height=125)
    )


def _diverging_swatches() -> alt.Chart:
    rows = [
        {"palette": palette, "stop": stop, "hex": color}
        for palette in ("div1", "div2", "div3", "div4")
        for stop, color in enumerate(ds.palettes.colors[palette])
    ]
    return (
        alt.Chart(ds.ext.internal_data(rows))
        .mark_rect()
        .encode(
            x=alt.X("stop:O", title="negative - zero - positive"),
            y=alt.Y("palette:N", sort=["div1", "div2", "div3", "div4"], title=None),
            color=alt.Color("hex:N", scale=None, legend=None),
            tooltip=["palette:N", "stop:O", "hex:N"],
        )
        .properties(title="Diverging companions", width=720, height=125)
    )


def _heatmap(palette: str) -> alt.Chart:
    values = (-8, -5, -3, -1, 0, 1, 3, 5, 8)
    rows = [
        {"column": column + 1, "row": row + 1, "value": values[(column * 2 + row * 3) % len(values)]}
        for row in range(5)
        for column in range(9)
    ]
    return (
        alt.Chart(ds.ext.internal_data(rows))
        .mark_rect(stroke="#FFFFFF", strokeWidth=0.5)
        .encode(
            x=alt.X("column:O", title=None),
            y=alt.Y("row:O", title=None),
            color=alt.Color(
                "value:Q",
                title="signed value",
                scale=alt.Scale(domain=[-8, 8], domainMid=0, range=ds.palettes.colors[palette]),
                legend=alt.Legend(orient="bottom", gradientLength=130),
            ),
        )
        .properties(title=palette, width=165, height=145)
    )


def _categorical_bars(palette: str) -> alt.Chart:
    rows = [{"category": f"C{i + 1}", "value": 10 + ((i * 7 + 3) % 17)} for i in range(10)]
    order = [f"C{i + 1}" for i in range(10)]
    return (
        alt.Chart(ds.ext.internal_data(rows))
        .mark_bar()
        .encode(
            x=alt.X("category:N", sort=order, title=None),
            y=alt.Y("value:Q", scale=alt.Scale(domain=[0, 28]), title=None),
            color=alt.Color("category:N", sort=order, scale=alt.Scale(range=ds.palettes.colors[palette]), legend=None),
        )
        .properties(title=palette, width=165, height=125)
    )


def build_review() -> alt.VConcatChart:
    """Build swatches and matched synthetic examples for all four families."""
    bars = alt.hconcat(*[_categorical_bars(f"cat{i}") for i in range(1, 5)], spacing=20).resolve_scale(
        color="independent"
    )
    heatmaps = alt.hconcat(*[_heatmap(f"div{i}") for i in range(1, 5)], spacing=20).resolve_scale(color="independent")
    return (
        alt.vconcat(_categorical_swatches(), _diverging_swatches(), bars, heatmaps, spacing=24)
        .properties(
            title={
                "text": "Four palette families",
                "subtitle": "Deterministic synthetic bars and signed matrices; cat1/div1 are defaults",
            }
        )
        .resolve_scale(color="independent")
    )


def main() -> None:
    output = Path("demo_output/cat4")
    output.mkdir(parents=True, exist_ok=True)
    ds.theme()
    ds.save(
        build_review,
        output / "palette_families_review",
        format=["png", "svg"],
        background="light",
        transparent=False,
        ppi=240,
    )


if __name__ == "__main__":
    main()
