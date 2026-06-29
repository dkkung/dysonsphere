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


def theme(
    axisOffset=None,  # defaults to tickSize if not set, or 0 if closed is True
    axisWidth=0.25,
    bandPadding=0.1,
    closed=None,  # None = auto (True if viewFill is set, else False); set explicitly to override
    chartFill=None,  # defaults to "white" (light) or "#1e1e1e" (dark) based on darkmode
    chartHeight=100,
    chartWidth=100,
    darkmode=False,
    dashedGrid=False,
    dashedLine=False,
    dashedRule=True,
    dashedWidth=[2, 2],
    font="HelveticaNeue",
    fontSize=7,
    fontStyle="normal",
    fontWeight=400,  # only multiples of 100; 300 = light, 400 = normal/regular; 700 = bold
    grid=False,
    gridColor=colors["greys"][0],
    legend=True,
    legendOffset=None,  # defaults to tickSize if not set
    legendStroke=False,
    markFill="black",
    markFillOpacity=1.0,
    markMedianFill="white",
    markMedianStroke="black",
    markSize=None,  # defaults to min(chartWidth, chartHeight) * 0.1 if not set (10 for 100×100)
    markStroke="black",
    markStrokeOpacity=1,
    markStrokeWidth=None,  # defaults to axisWidth if not set
    palette=None,
    strokeCap="round",  # "butt" | "round" | "square"
    ticks=True,
    tickSize=3,
    transparentBackground=False,
    viewFill=None,  # setting a color auto-enables closed
    xAxis=True,
    xDomain=True,
    xLabels=True,
    xLabelAngle=0,
    xTicks=True,
    yAxis=True,
    yDomain=True,
    yLabels=True,
    yLabelAngle=0,
    yTicks=True,
):
    """
    Configure and register the dysonsphere Altair theme.
    Call this function when plotting to custom-set the
    keyword arguments to override the defaults.
    """
    if closed is None:
        closed = viewFill is not None  # auto-close when a view fill color is specified
    if markSize is None:
        markSize = min(chartWidth, chartHeight) * 0.1
    if markStrokeWidth is None:
        markStrokeWidth = axisWidth
    if chartFill is None and not darkmode:
        chartFill = "white"

    alt.theme.options = {}  # must reset options to remove stale keys
    alt.theme.options["xLabelAngle"] = xLabelAngle
    alt.theme.options["axisOffset"] = axisOffset
    alt.theme.options["axisWidth"] = axisWidth
    alt.theme.options["bandPadding"] = bandPadding
    alt.theme.options["chartFill"] = chartFill
    alt.theme.options["chartHeight"] = chartHeight
    alt.theme.options["chartWidth"] = chartWidth
    alt.theme.options["darkmode"] = darkmode
    alt.theme.options["dashedGrid"] = dashedGrid
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
    alt.theme.options["legendOffset"] = legendOffset  # falls back to tickSize in custom()
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
    alt.theme.options["yLabelAngle"] = yLabelAngle
    alt.theme.options["viewFill"] = viewFill
    alt.theme.options["xAxis"] = xAxis
    alt.theme.options["xDomain"] = xDomain
    alt.theme.options["xLabels"] = xLabels
    alt.theme.options["xTicks"] = xTicks
    alt.theme.options["yAxis"] = yAxis
    alt.theme.options["yDomain"] = yDomain
    alt.theme.options["yLabels"] = yLabels
    alt.theme.options["yTicks"] = yTicks


@alt.theme.register("custom", enable=True)
def custom():
    opts = alt.theme.options
    return {
        "background": (
            None if opts["transparentBackground"] else opts["chartFill"]
        ),  # background of the entire chart
        "config": {
            "arc": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
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
                "gridColor": (opts["gridColor"] if opts["darkmode"] else opts["gridColor"]),
                "gridDash": opts["dashedWidth"] if opts["dashedGrid"] else [0, 0],
                "gridOpacity": 1.00,
                "gridWidth": opts["axisWidth"],
                "labelColor": "white" if opts["darkmode"] else "black",
                "labelFont": opts["font"],
                "labelFontSize": opts["fontSize"],
                "labelFontStyle": opts["fontStyle"],
                "labelFontWeight": opts["fontWeight"],
                "offset": 0
                if opts["closed"]
                else (opts["axisOffset"] if opts["axisOffset"] is not None else opts["tickSize"]),
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
                "domain": opts["xAxis"] and opts["xDomain"],
                "labelAlign": (
                    "right"
                    if opts["xLabelAngle"] < 0
                    else "left"
                    if opts["xLabelAngle"] > 0
                    else "center"
                ),
                "labelAngle": opts["xLabelAngle"] % 360,
                "labels": opts["xLabels"],
                "ticks": opts["xAxis"] and opts["xTicks"] and opts["ticks"],
                "translate": 0,
            },
            "axisY": {
                "domain": opts["yAxis"] and opts["yDomain"],
                "labelAlign": "center" if opts["yLabelAngle"] != 0 else "right",
                "labelAngle": opts["yLabelAngle"] % 360,
                "labels": opts["yLabels"],
                "ticks": opts["yAxis"] and opts["yTicks"] and opts["ticks"],
                "translate": 0,
            },
            "axisRight": {
                "domain": opts["yAxis"] and opts["yDomain"],
                "labelAlign": "center" if opts["yLabelAngle"] != 0 else "left",
                "labelAngle": (-opts["yLabelAngle"]) % 360,
                "labels": opts["yLabels"],
                "ticks": opts["yAxis"] and opts["yTicks"] and opts["ticks"],
                "translate": 0,
            },
            "axisTop": {
                "domain": opts["xAxis"] and opts["xDomain"],
                "labelAlign": (
                    "left"
                    if opts["xLabelAngle"] < 0
                    else "right"
                    if opts["xLabelAngle"] > 0
                    else "center"
                ),
                "labelAngle": (-opts["xLabelAngle"]) % 360,
                "labels": opts["xLabels"],
                "ticks": opts["xAxis"] and opts["xTicks"] and opts["ticks"],
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
                "size": opts["markSize"] * 0.8,
                "ticks": {
                    "fill": "white" if opts["darkmode"] else "black",
                    "size": opts["markSize"] * 0.6,
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
                    "size": opts["markSize"] * 0.8,
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
                "size": opts["markSize"] / 4,
                "stroke": "black" if opts["darkmode"] else opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "errorband": {
                "band": {
                    "fillOpacity": 0.60,
                    "stroke": None,
                    "strokeWidth": opts["markStrokeWidth"],
                    "strokeOpacity": opts["markStrokeOpacity"],
                },
                "borders": {
                    "opacity": 0,
                    "strokeOpacity": opts["markStrokeWidth"],
                    "strokeWidth": opts["markStrokeOpacity"],
                },
            },
            "errorbar": {
                "opacity": 1,
                "rule": {"strokeDash": [0, 0], "strokeWidth": opts["markStrokeWidth"] * 2},
                "ticks": {
                    "color": "white" if opts["darkmode"] else "black",
                    "cornerRadius": opts["markStrokeWidth"],
                    "opacity": 1,
                    "size": opts["markSize"] * 0.6,
                    "thickness": opts["markStrokeWidth"] * 2,
                },
                "thickness": opts["markStrokeWidth"] * 2,
            },
            "font": opts["font"],
            "geoshape": {
                "fill": opts["markFill"],
                "fillOpacity": opts["markFillOpacity"],
                "stroke": "white" if opts["darkmode"] else "black",
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
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
                "gradientLength": opts["markSize"] * 5,
                "gradientThickness": opts["markSize"] * 0.5,
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
                "symbolSize": opts["fontSize"] * 6,
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
                "size": opts["markSize"] / 2,
                "stroke": opts["markStroke"],
                "strokeOpacity": opts["markStrokeOpacity"],
                "strokeWidth": opts["markStrokeWidth"],
            },
            "range": {
                # pass in a list to AVOID interpolation; use {scheme: _} to USE interpolation
                "category": {
                    "scheme": opts["palette"]
                    if opts.get("palette") is not None
                    else colors["blues"][::2]
                },
                "diverging": {
                    "scheme": opts["palette"]
                    if opts.get("palette") is not None
                    else colors["redsblues"]
                },
                "heatmap": {
                    "scheme": opts["palette"]
                    if opts.get("palette") is not None
                    else colors["blues"]
                },
                "ordinal": {
                    "scheme": opts["palette"]
                    if opts.get("palette") is not None
                    else colors["blues"]
                },
                "ramp": {
                    "scheme": opts["palette"]
                    if opts.get("palette") is not None
                    else colors["blues"]
                },
                # "symbol": ["circle", "square", "diamond", "triangle-up", "triangle-down", "cross"],  # noqa: E501
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
                "round": False,
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
                "fontSize": opts["fontSize"],
                "fontStyle": opts["fontStyle"],
                "fontWeight": opts["fontWeight"],
            },
            "title": {
                "color": "white" if opts["darkmode"] else "black",
                "font": opts["font"],
                "fontSize": opts["fontSize"],
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
                "fill": None
                if opts["darkmode"]
                else opts["viewFill"],  # background of the plotted area
                "stroke": ("white" if opts["darkmode"] else "black") if opts["closed"] else None,
                "strokeWidth": opts["axisWidth"],
            },
        },
    }
