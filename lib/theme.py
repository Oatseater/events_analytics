"""Colours, number formatting and the shared Plotly template.

Warm near-black and brushed silver, no accent colour. Ordinary marks are
matte silver; the one mark that needs attention is polished silver and
labelled in words. No Streamlit import here, so make_brief.py can reuse the
formatters.
"""

from __future__ import annotations

import math

import plotly.graph_objects as go
import plotly.io as pio

# ---- palette: warm black and silver --------------------------------------------
NIGHT = "#12100E"      # page background: warm near-black
RAISED = "#1A1816"     # hover labels
SILVER = "#D6D3CE"     # brushed silver: text and marks
BRIGHT = "#F0EEEA"     # polished silver: the one thing to look at
DULL = "#9A9792"       # secondary text, axes
FAINT = "#6E6B67"      # reference lines
HAIRLINE = "#2E2B28"   # 1px gridlines (decorative only)


def silver(alpha: float) -> str:
    return f"rgba(214,211,206,{alpha})"


SANS = "Archivo, 'Helvetica Neue', Arial, sans-serif"
MONO = "'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, monospace"
SERIF = "'Bodoni Moda', Didot, 'Bodoni 72', Georgia, serif"

TICKET_ORDER = ["Early Bird", "Standard", "Late", "Student"]

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


def bar_marker(kind: str = "normal") -> dict:
    """normal: matte silver. flag: polished silver, the thing to look at.
    pending: an outline only, for numbers that are not final yet."""
    if kind == "flag":
        return dict(color=BRIGHT, line=dict(width=0))
    if kind == "pending":
        return dict(color="rgba(0,0,0,0)", line=dict(color=silver(0.55), width=1))
    return dict(color=silver(0.28), line=dict(width=0))


def annotate(fig: go.Figure, x, y, text: str, xref: str = "x", yref: str = "y",
             xanchor: str = "left", xshift: float = 0, yshift: float = 0, bright: bool = True) -> None:
    """A short label set in the mono, beside a mark (shifts are in pixels)."""
    fig.add_annotation(x=x, y=y, xref=xref, yref=yref, text=text, showarrow=False,
                       xanchor=xanchor, xshift=xshift, yshift=yshift,
                       font=dict(family=MONO, size=11, color=BRIGHT if bright else DULL))


# ---- number formatting -----------------------------------------------------------

def _missing(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def fmt_int(x) -> str:
    return "-" if _missing(x) else f"{int(round(x)):,}"


def fmt_aed(x, compact: bool = False) -> str:
    if _missing(x):
        return "-"
    if compact and abs(x) >= 1_000_000:
        return f"AED {x / 1_000_000:,.2f}M"
    if compact and abs(x) >= 10_000:
        return f"AED {x / 1_000:,.0f}K"
    return f"AED {int(round(x)):,}"


def fmt_millions(x) -> str:
    """Big money for headline numbers: 6.89M. Exact figures stay in the tables."""
    if _missing(x):
        return "-"
    return f"{x / 1_000_000:,.2f}M" if abs(x) >= 1_000_000 else fmt_int(x)


def fmt_pct(x) -> str:
    return "-" if _missing(x) else f"{x:.1f}%"


def fmt_signed_pct(x) -> str:
    return "-" if _missing(x) else f"{x:+.1f}%"


def fmt_pp(x) -> str:
    return "-" if _missing(x) else f"{x:.1f} percentage points"


def fmt_rating(x) -> str:
    return "-" if _missing(x) else f"{x:.2f}"


def two_line(name: str) -> str:
    """Break a long event name before its city, for compact axis labels."""
    for city in ("Abu Dhabi", "Dubai", "Riyadh", "Seoul"):
        if f" {city} " in f"{name} ":
            head, tail = name.split(f" {city}", 1)
            return f"{head}<br>{city}{tail}"
    return name


# ---- Plotly template ---------------------------------------------------------------

_axis = dict(
    showgrid=False,
    zeroline=False,
    showline=True,
    linecolor=HAIRLINE,
    ticks="",
    tickfont=dict(family=MONO, color=DULL, size=11),
    title=dict(font=dict(family=SANS, color=DULL, size=11.5), standoff=12),
    ticklabelstandoff=8,
    automargin=True,
)

pio.templates["events_analytics"] = go.layout.Template(
    layout=dict(
        font=dict(family=SANS, size=12, color=SILVER),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[SILVER, DULL, FAINT],
        margin=dict(l=8, r=24, t=8, b=48),
        xaxis=_axis,
        yaxis={**_axis, "showgrid": True, "gridcolor": HAIRLINE, "showline": False},
        bargap=0.5,
        barcornerradius=0,
        legend=dict(orientation="h", x=0, xanchor="left", y=1.02, yanchor="bottom",
                    font=dict(family=SANS, size=11.5, color=DULL), title=None),
        hoverlabel=dict(bgcolor=RAISED, bordercolor=HAIRLINE,
                        font=dict(family=MONO, size=12, color=BRIGHT)),
        hovermode="closest",
    )
)
pio.templates.default = "events_analytics"
