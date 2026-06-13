import altair as alt
from .colors import colors

"""
Defining custom themes using global and
rational configuration values. The theme
must be added to the register uniquely
for each function definition using the
@ decorator to pass the function to the
register.
"""


def options(
    angledX=False,
    axisOffset=None,  # defaults to tickSize if not set
    axisWidth=0.50,
    bandPadding=0.1,
    chartHeight=150,
    chartWidth=150,
    darkmode=False,
    dashedLine=False,
    dashedRule=True,
    dashedWidth=[2, 2],
    font="HelveticaNeue",
    fontSize=7,
    fontStyle="normal",
    fontWeight=400,  # only multiples of 100; 300 = light, 400 = normal/regular; 700 = bold
    grid=False,
    gridColor="darkGray",
    legend=True,
    legendOffset=None,  # defaults to tickSize if not set
    legendStroke=False,
    markFillColor="black",
    markFillOpacity=1.0,
    markSize=10,
    markStrokeColor="black",
    markStrokeOpacity=1,
    markStrokeWidth=0.50,
    chartBackgroundColor="white",
    palette=None,
    ticks=True,
    tickSize=5,
    topAndRightBorder=False,
    transparentBackground=True,
    verticalY=False,
    viewBackgroundColor="white",
    xTicks=True,
    yTicks=True,
):
    """
    Set global configuration options for the custom theme.
    Call this function when plotting to custom-set the
    options to override the defaults.
    """
    alt.theme.options = {}  # must reset options to remove stale keys
    alt.theme.options["angledX"] = angledX
    alt.theme.options["axisOffset"] = axisOffset  # falls back to tickSize in custom()
    alt.theme.options["axisWidth"] = axisWidth
    alt.theme.options["bandPadding"] = bandPadding
    alt.theme.options["chartBackgroundColor"] = chartBackgroundColor
    alt.theme.options["chartHeight"] = chartHeight
    alt.theme.options["chartWidth"] = chartWidth
    alt.theme.options["darkmode"] = darkmode
    alt.theme.options["dashedLine"] = dashedLine
    alt.theme.options["dashedRule"] = dashedRule
    alt.theme.options["dashedWidth"] = dashedWidth
    alt.theme.options["font"] = font
    alt.theme.options["fontSize"] = fontSize
    alt.theme.options["fontStyle"] = fontStyle
    alt.theme.options["fontWeight"] = fontWeight
    alt.theme.options["grid"] = grid
    alt.theme.options["gridColor"] = gridColor
    alt.theme.options["legend"] = legend
    alt.theme.options["legendOffset"] = (
        legendOffset  # falls back to tickSize in custom()
    )
    alt.theme.options["legendStroke"] = legendStroke
    alt.theme.options["markFillColor"] = markFillColor
    alt.theme.options["markFillOpacity"] = markFillOpacity
    alt.theme.options["markSize"] = markSize
    alt.theme.options["markStrokeColor"] = markStrokeColor
    alt.theme.options["markStrokeOpacity"] = markStrokeOpacity
    alt.theme.options["markStrokeWidth"] = markStrokeWidth
    alt.theme.options["palette"] = (
        colors[palette] if palette is not None and palette in colors else palette
    )  # accepts both custom-defined and vegafusion palettes
    alt.theme.options["ticks"] = ticks
    alt.theme.options["tickSize"] = tickSize
    alt.theme.options["tickWidth"] = axisWidth
    alt.theme.options["topAndRightBorder"] = topAndRightBorder
    alt.theme.options["transparentBackground"] = transparentBackground
    alt.theme.options["verticalY"] = verticalY
    alt.theme.options["viewBackgroundColor"] = viewBackgroundColor
    alt.theme.options["xTicks"] = xTicks
    alt.theme.options["yTicks"] = yTicks


@alt.theme.register("custom", enable=True)
def custom():
    opts = alt.theme.options
    return {
        "background": (
            None
            if opts["transparentBackground"] or opts["darkmode"]
            else opts["chartBackgroundColor"]
        ),  # background of the entire view
        "config": {
            "area": {
                "fill": opts["markFillColor"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": "white" if opts["darkmode"] else opts["markStrokeColor"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "axis": {
                "domain": True,
                "domainCap": "round",
                "domainColor": "white" if opts["darkmode"] else "black",
                "domainWidth": opts["axisWidth"],
                "grid": opts["grid"],
                "gridCap": "round",
                "gridColor": (
                    opts["gridColor"] if opts["darkmode"] else opts["gridColor"]
                ),
                "gridOpacity": 0.25,
                "gridWidth": opts["axisWidth"],
                "labelColor": "white" if opts["darkmode"] else "black",
                "labelFont": opts["font"],
                "labelFontSize": opts["fontSize"],
                "labelFontStyle": opts["fontStyle"],
                "labelFontWeight": opts["fontWeight"],
                "offset": opts["axisOffset"]
                if opts["axisOffset"] is not None
                else opts["tickSize"],
                "ticks": opts["ticks"],
                "tickCap": "round",
                "tickColor": "white" if opts["darkmode"] else "black",
                "tickSize": opts["tickSize"],
                "tickWidth": opts["axisWidth"],
                "titleColor": "white" if opts["darkmode"] else "black",
                "titleFont": opts["font"],
                "titleFontSize": opts["fontSize"],
                "titleFontStyle": opts["fontStyle"],
                "titleFontWeight": opts["fontWeight"],
                "translate": 0,  # default is 0.5, which causes x and y axes to be misaligned / shifted. Required for top and right border alignment.
            },
            "axisX": {
                "labelAlign": (
                    "right" if opts["angledX"] else "center"
                ),  # keep label alignment distinct between X & Y
                "labelAngle": 315 if opts["angledX"] else 0,
                "ticks": True if opts["xTicks"] and opts["ticks"] else False,
            },
            "axisY": {
                "labelAlign": (
                    "center" if opts["verticalY"] else "right"
                ),  # keep label alignment distinct between X & Y
                "labelAngle": 270 if opts["verticalY"] else 0,
                "ticks": True if opts["yTicks"] and opts["ticks"] else False,
            },
            "bar": {
                "fill": opts["markFillColor"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": "white" if opts["darkmode"] else opts["markStrokeColor"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "boxplot": {
                "ticks": {
                    "size": opts["markSize"],
                    "thickness": opts["markStrokeWidth"],
                },
                "box": {
                    # 'fill': opts['markFillColor'],
                    "fillOpacity": opts["markFillOpacity"],
                    "stroke": "white" if opts["darkmode"] else opts["markStrokeColor"],
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                },
                "median": {
                    "fill": (
                        "black" if opts["darkmode"] else opts["viewBackgroundColor"]
                    ),
                    "fillOpacity": opts["markFillOpacity"],
                    "size": opts["markSize"],
                    "stroke": "white" if opts["darkmode"] else opts["markStrokeColor"],
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                },
                "rule": {  # may inherit undeclared fields from top-level rule config
                    "fill": "white" if opts["darkmode"] else "black",
                    "fillOpacity": opts["markFillOpacity"],
                    "size": opts["markSize"],
                    "stroke": "white" if opts["darkmode"] else opts["markStrokeColor"],
                    "strokeDash": [0, 0],
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                },
                "outliers": {
                    "color": "white" if opts["darkmode"] else "black",
                    "fill": "white" if opts["darkmode"] else "black",
                    "fillOpacity": opts["markFillOpacity"],
                    "size": 0,
                    "stroke": "white" if opts["darkmode"] else opts["markStrokeColor"],
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                },
            },
            "circle": {
                "fill": "white",
                "fillOpacity": opts["markFillOpacity"],
                "size": opts["markSize"],
                "stroke": "white" if opts["darkmode"] else opts["markStrokeColor"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "font": opts["font"],
            "header": {
                "labelColor": "white" if opts["darkmode"] else "black",
                "labelFont": opts["font"],
                "labelFontSize": opts["fontSize"],
                "labelFontStyle": opts["fontStyle"],
                "labelFontWeight": opts["fontWeight"],
                "titleColor": "white" if opts["darkmode"] else "black",
                "titleFont": opts["font"],
                "titleFontSize": opts["fontSize"],
                "titleFontStyle": opts["fontStyle"],
                "titleFontWeight": opts["fontWeight"],
                "titlePadding": 0,
            },
            "legend": {
                "disable": not opts["legend"],
                "offset": opts["legendOffset"]
                if opts["legendOffset"] is not None
                else opts["tickSize"],
                "gradientOpacity": opts["markFillOpacity"],
                "gradientStrokeColor": "white" if opts["darkmode"] else "black",
                "gradientStrokeWidth": opts["markStrokeWidth"],
                "labelColor": "white" if opts["darkmode"] else "black",
                "labelFont": opts["font"],
                "labelFontSize": opts["fontSize"],
                "labelFontStyle": opts["fontStyle"],
                "labelFontWeight": opts["fontWeight"],
                "strokeColor": "white" if opts["darkmode"] else "black",
                "strokeWidth": opts["axisWidth"] if opts["legendStroke"] else 0,
                "symbolStrokeColor": "white" if opts["darkmode"] else "black",
                "symbolStrokeWidth": opts["markStrokeWidth"]
                if opts["markStrokeOpacity"] > 0
                else 0,
                "titleColor": "white" if opts["darkmode"] else "black",
                "titleFont": opts["font"],
                "titleFontSize": opts["fontSize"],
                "titleFontStyle": opts["fontStyle"],
                "titleFontWeight": opts["fontWeight"],
            },
            "line": {
                "color": "white" if opts["darkmode"] else "black",
                "stroke": "white" if opts["darkmode"] else "black",
                "strokeCap": "round",
                "strokeDash": opts["dashedWidth"] if opts["dashedLine"] else [0, 0],
                "strokeOpacity": 1,
                "strokeWidth": opts["axisWidth"] * 1.5,
            },
            "point": {
                "fill": opts["markFillColor"],
                "fillOpacity": opts["markFillOpacity"],
                "size": opts["markSize"],
                "stroke": opts["markStrokeColor"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "range": {
                # pass in a list outside of a dict to AVOID interpolations; define as {scheme: _} to USE interpolation, which will NOT use the maximum range of colors
                "category": {
                    "scheme": opts["palette"]
                    if opts.get("palette") is not None
                    else colors["mpl_YlGnBu"]
                },
                "diverging": {
                    "scheme": opts["palette"]
                    if opts.get("palette") is not None
                    else colors["mpl_YlGnBu"]
                },
                "heatmap": {
                    "scheme": opts["palette"]
                    if opts.get("palette") is not None
                    else colors["mpl_RdPu"]
                },
                "ordinal": {
                    "scheme": opts["palette"]
                    if opts.get("palette") is not None
                    else colors["mpl_YlGnBu"]
                },
                "ramp": {
                    "scheme": opts["palette"]
                    if opts.get("palette") is not None
                    else colors["mpl_RdPu"]
                },
                # "symbol": ["circle", "square", "diamond", "triangle-up", "triangle-down", "cross"],
                # "strokeDash": [[1, 0], [4, 2], [2, 2], [4, 2, 1, 2], [1, 2]],
            },
            "rule": {
                "color": "white" if opts["darkmode"] else "black",
                "stroke": "white" if opts["darkmode"] else "black",
                "strokeDash": opts["dashedWidth"] if opts["dashedRule"] else [0, 0],
                "strokeOpacity": 1,
                "strokeWidth": opts["axisWidth"],
            },
            "scale": {
                "bandPaddingInner": opts["bandPadding"],
                "bandPaddingOuter": opts["bandPadding"],
            },
            "rect": {
                "fill": opts["markFillColor"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": "white" if opts["darkmode"] else opts["markStrokeColor"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "square": {
                "fill": opts["markFillColor"],
                "fillOpacity": opts["markFillOpacity"],
                "size": opts["markSize"],
                "stroke": opts["markStrokeColor"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "text": {
                "color": "white" if opts["darkmode"] else "black",
                "font": opts["font"],
                "fontStyle": opts["fontStyle"],
                "fontWeight": opts["fontWeight"],
            },
            "title": {
                "color": "white" if opts["darkmode"] else "black",
                "font": opts["font"],
                "fontStyle": opts["fontStyle"],
                "fontWeight": opts["fontWeight"],
                "subtitleColor": "white" if opts["darkmode"] else "black",
                "subtitleFont": opts["font"],
                "subtitleFontSize": opts["font"],
                "subtitleFontStyle": opts["fontStyle"],
                "subtitleFontWeight": opts["fontWeight"],
            },
            "view": {
                "continuousWidth": opts["chartWidth"],
                "continuousHeight": opts["chartHeight"],
                "discreteWidth": opts["chartWidth"],
                "discreteHeight": opts["chartHeight"],
                "fill": (
                    None
                    if opts["transparentBackground"] or opts["darkmode"]
                    else opts["viewBackgroundColor"]
                ),
                "stroke": "white" if opts["darkmode"] else "black",
                "strokeOpacity": (
                    1 if opts["topAndRightBorder"] else 0
                ),  # remove top and right axis borders
                "strokeWidth": opts["axisWidth"],
            },
        },
    }


"""
TO-DO LIST:
- Try to add default paddingOutter and paddingInner values for all types of charts/marks.
- Add support for area marks.
    - Add support for gradients - linear and maybe radial.
- Figure out why opacity decreases (or does color change?) for area marks when line = True.
- Figure out why the Y axis and X axis have dissimilar domain widths on large plots.
- Maybe change legend scale size?
"""
