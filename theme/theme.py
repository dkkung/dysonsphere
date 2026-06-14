import altair as alt
from .palettes import colors

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
    axisOffset=None,  # defaults to tickSize if not set, or 0 if closed is True
    axisWidth=0.50,
    bandPadding=0.1,
    closed=None,   # None = auto (True if viewFill is set, else False); set explicitly to override
    chartFill=None,
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
    markFill="black",
    markFillOpacity=1.0,
    markMedianFill="white",
    markMedianStroke="black",
    markSize=10,
    markStroke="black",
    markStrokeOpacity=1,
    markStrokeWidth=0.50,
    palette=None,
    strokeCap="round",  # "butt" | "round" | "square"
    ticks=True,
    tickSize=5,
    transparentBackground=True,
    verticalY=False,
    viewFill=None,  # setting a color auto-enables closed
    xTicks=True,
    yTicks=True,
):
    """
    Set global configuration options for the custom theme.
    Call this function when plotting to custom-set the
    options to override the defaults.
    """
    if closed is None:
        closed = viewFill is not None  # auto-close when a view fill color is specified

    alt.theme.options = {}  # must reset options to remove stale keys
    alt.theme.options["angledX"] = angledX
    alt.theme.options["axisOffset"] = axisOffset
    alt.theme.options["axisWidth"] = axisWidth
    alt.theme.options["bandPadding"] = bandPadding
    alt.theme.options["chartFill"] = chartFill
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
    alt.theme.options["markFill"] = markFill
    alt.theme.options["markFillOpacity"] = markFillOpacity
    alt.theme.options["markMedianFill"] = markMedianFill
    alt.theme.options["markMedianStroke"] = markMedianStroke
    alt.theme.options["markSize"] = markSize
    alt.theme.options["markStroke"] = markStroke
    alt.theme.options["markStrokeOpacity"] = markStrokeOpacity
    alt.theme.options["markStrokeWidth"] = markStrokeWidth
    alt.theme.options["palette"] = (
        colors[palette] if palette is not None and palette in colors else palette
    )  # accepts both custom-defined and vegafusion palettes
    alt.theme.options["strokeCap"] = strokeCap
    alt.theme.options["ticks"] = ticks
    alt.theme.options["tickSize"] = tickSize
    alt.theme.options["tickWidth"] = axisWidth
    alt.theme.options["closed"] = closed
    alt.theme.options["transparentBackground"] = transparentBackground
    alt.theme.options["verticalY"] = verticalY
    alt.theme.options["viewFill"] = viewFill
    alt.theme.options["xTicks"] = xTicks
    alt.theme.options["yTicks"] = yTicks


@alt.theme.register("custom", enable=True)
def custom():
    opts = alt.theme.options
    return {
        "background": (
            None
            if opts["transparentBackground"] or opts["darkmode"]
            else opts["chartFill"]
        ),  # background of the entire view
        "config": {
            "area": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "axis": {
                "domain": True,
                "domainCap": opts["strokeCap"],
                "domainColor": "white" if opts["darkmode"] else "black",
                "domainWidth": opts["axisWidth"],
                "grid": opts["grid"],
                "gridCap": opts["strokeCap"],
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
                "offset": 0
                if opts["closed"]
                else (
                    opts["axisOffset"]
                    if opts["axisOffset"] is not None
                    else opts["tickSize"]
                ),
                "ticks": opts["ticks"],
                "tickCap": opts["strokeCap"],
                "tickColor": "white" if opts["darkmode"] else "black",
                "tickSize": opts["tickSize"],
                "tickWidth": opts["axisWidth"],
                "titleColor": "white" if opts["darkmode"] else "black",
                "titleFont": opts["font"],
                "titleFontSize": opts["fontSize"],
                "titleFontStyle": opts["fontStyle"],
                "titleFontWeight": opts["fontWeight"],
            },
            "axisX": {
                "labelAlign": (
                    "right" if opts["angledX"] else "center"
                ),  # keep label alignment distinct between X & Y
                "labelAngle": 315 if opts["angledX"] else 0,
                "ticks": True if opts["xTicks"] and opts["ticks"] else False,
                "translate": 0
                if opts["closed"]
                else 0.5,  # sub-pixel shift so axis domain line falls on a pixel boundary; 0 when closed=True so domain line aligns with view stroke
            },
            "axisY": {
                "labelAlign": (
                    "center" if opts["verticalY"] else "right"
                ),  # keep label alignment distinct between X & Y
                "labelAngle": 270 if opts["verticalY"] else 0,
                "ticks": True if opts["yTicks"] and opts["ticks"] else False,
                "translate": 0,
            },
            "bar": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "boxplot": {
                "ticks": {
                    "fill": "white" if opts["darkmode"] else "black",
                    "size": opts["markSize"] * 0.75,
                    "thickness": opts["markStrokeWidth"],
                },
                "box": {
                    # 'fill': opts['markFill'],
                    "fillOpacity": opts["markFillOpacity"],
                    "stroke": opts["markStroke"],
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                },
                "median": {
                    "fill": opts["markMedianFill"],
                    "fillOpacity": opts["markFillOpacity"],
                    "size": opts["markSize"],
                    "stroke": opts["markMedianStroke"],
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                },
                "rule": {  # may inherit undeclared fields from top-level rule config
                    "fill": "white" if opts["darkmode"] else "black",
                    "fillOpacity": opts["markFillOpacity"],
                    "size": opts["markSize"],
                    "stroke": "white" if opts["darkmode"] else "black",
                    "strokeDash": [0, 0],
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                },
                "outliers": {
                    "color": "white" if opts["darkmode"] else "black",
                    "fill": "white" if opts["darkmode"] else "black",
                    "fillOpacity": opts["markFillOpacity"],
                    "size": 0,
                    "stroke": opts["markStroke"],
                    "strokeOpacity": opts["markStrokeOpacity"],
                    "strokeWidth": opts["markStrokeWidth"],
                },
            },
            "circle": {
                "fill": "white",
                "fillOpacity": opts["markFillOpacity"],
                "size": opts["markSize"],
                "stroke": "black" if opts["darkmode"] else opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "errorbar": {
                "opacity": 1,
                "rule": {"strokeDash": [0, 0]},
                "ticks": {
                    "color": "white" if opts["darkmode"] else "black",
                    "opacity": 1,
                    "size": opts["markSize"] * 0.75,
                    "thickness": opts["markStrokeWidth"],
                },
                "thickness": opts["markStrokeWidth"],
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
                "gradientLength": opts["chartHeight"] * 0.5,
                "gradientThickness": opts["chartWidth"] * 0.05,
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
                "symbolSize": opts["fontSize"] ** 2,
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
                "strokeCap": opts["strokeCap"],
                "strokeDash": opts["dashedWidth"] if opts["dashedLine"] else [0, 0],
                "strokeOpacity": 1,
                "strokeWidth": opts["axisWidth"] * 1.5,
            },
            "point": {
                "filled": True,
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "size": opts["markSize"],
                "stroke": opts["markStroke"],
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
                "strokeCap": opts["strokeCap"],
                "strokeDash": opts["dashedWidth"] if opts["dashedRule"] else [0, 0],
                "strokeOpacity": 1,
                "strokeWidth": opts["axisWidth"],
            },
            "scale": {
                "bandPaddingInner": opts["bandPadding"],
                "bandPaddingOuter": opts["bandPadding"],
                "round": False,  # keeps band positions as floats so axis ticks align with mark centers
            },
            "rect": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "square": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "size": opts["markSize"],
                "stroke": opts["markStroke"],
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
                    else opts["viewFill"]
                ),
                "stroke": ("white" if opts["darkmode"] else "black")
                if opts["closed"]
                else None,
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
