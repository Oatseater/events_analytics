"""Figure builders. Each function takes a query result and returns a Plotly
figure styled by the shared template in lib/theme.py. No analysis happens
here: the numbers arrive already computed by SQL.

Marks are matte silver. The one that needs attention is polished silver and
named in a short mono label. Numbers that are not final yet are outlines."""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from lib import theme as t

LABEL_FONT = dict(family=t.MONO, size=12, color=t.SILVER)
QUIET_LABEL = dict(family=t.MONO, size=11, color=t.DULL)
CATEGORY_FONT = dict(family=t.SANS, size=12.5, color=t.DULL)
OUTLINE = dict(color="rgba(0,0,0,0)", line=dict(color=t.FAINT, width=1))


def _height(n: int, per_bar: int = 40, base: int = 56) -> int:
    return max(170, base + per_bar * n)


def hbar(labels, values, text, *, x_title: str, flags=None, hover=None,
         height: int | None = None) -> go.Figure:
    """Horizontal bars with direct value labels; first item on top.
    flags: optional per-bar kinds. True or "flag" draws the bar in polished
    silver (needs attention); "pending" draws an outline (not final yet)."""
    labels, values, text = list(labels), [float(v) for v in values], list(text)
    kinds = ["flag" if f is True else ("normal" if f is False else f)
             for f in (list(flags) if flags is not None else [False] * len(values))]
    fig = go.Figure()
    for kind in ("normal", "pending", "flag"):     # one trace per style keeps the marker simple
        idx = [i for i, k in enumerate(kinds) if k == kind]
        if not idx:
            continue
        fig.add_bar(
            y=[labels[i] for i in idx], x=[values[i] for i in idx], orientation="h",
            marker=t.bar_marker(kind),
            text=[text[i] for i in idx], textposition="outside", cliponaxis=False,
            textfont=dict(LABEL_FONT, color=t.BRIGHT) if kind == "flag" else LABEL_FONT,
            hovertext=[(hover or text)[i] for i in idx], hoverinfo="text",
        )
    hi = max(values + [0]) or 1
    lo = min(values + [0])
    pad = (hi - lo) * 0.34
    fig.update_layout(height=height or _height(len(labels)), showlegend=False, barmode="overlay")
    fig.update_yaxes(type="category", categoryorder="array", categoryarray=labels,
                     autorange="reversed", showgrid=False, showline=False, tickfont=CATEGORY_FONT)
    fig.update_xaxes(title_text=x_title, showticklabels=False,
                     range=[lo - (pad if lo < 0 else 0), hi + pad])
    return fig


# ---- Overview ----------------------------------------------------------------------

def revenue_by_event(summary: pd.DataFrame, breakeven: pd.DataFrame) -> go.Figure:
    below = set(breakeven.loc[breakeven["status"] == "Below break-even", "event_id"])
    upcoming = list(summary["status"] == "Upcoming")
    flags = ["pending" if up else (e in below) for e, up in zip(summary["event_id"], upcoming)]
    hover = [f"{n}<br>revenue {t.fmt_aed(r)}{' so far' if up else ''}<br>{t.fmt_int(g)} tickets"
             for n, r, g, up in zip(summary["event_name"], summary["revenue_aed"], summary["registrations"], upcoming)]
    values = list(summary["revenue_aed"])
    fig = hbar([t.two_line(n) for n in summary["event_name"]], values,
               [t.fmt_aed(v, compact=True) + (" so far" if up else "") for v, up in zip(values, upcoming)],
               x_title="ticket revenue (AED)", flags=flags, hover=hover,
               height=_height(len(summary), 52))
    # Name the problem in words beside its bar. No colour, no circle.
    for i, (flag, v) in enumerate(zip(flags, values)):
        if flag is True:
            t.annotate(fig, v, i, "below break-even", xshift=78)
    return fig


def registrations_vs_capacity(summary: pd.DataFrame) -> go.Figure:
    labels = [t.two_line(n) for n in summary["event_name"]]
    fig = go.Figure()
    fig.add_bar(y=labels, x=summary["capacity"], orientation="h", name="capacity (outline)",
                marker=OUTLINE,
                text=[f"{t.fmt_int(r)} / {t.fmt_int(c)}" for r, c in zip(summary["registrations"], summary["capacity"])],
                customdata=summary["fill_rate_pct"],
                textposition="outside", textfont=LABEL_FONT, cliponaxis=False,
                hovertemplate="%{y}<br>capacity %{x:,}<br>%{customdata:.1f}% filled<extra></extra>")
    fig.add_bar(y=labels, x=summary["registrations"], orientation="h", name="tickets sold (filled)",
                marker=t.bar_marker(), width=0.42,
                hovertemplate="%{y}<br>tickets sold %{x:,}<extra></extra>")
    fig.update_layout(barmode="overlay", height=_height(len(summary), 52),
                      legend=dict(traceorder="reversed"))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=CATEGORY_FONT)
    fig.update_xaxes(title_text="people", showticklabels=False,
                     range=[0, summary["capacity"].max() * 1.42])
    return fig


def city_trend(mom: pd.DataFrame) -> go.Figure:
    """Small multiples: one panel per city on a single shared y-scale. Each
    panel's title carries that city's average monthly growth from query 04."""
    cities = list(dict.fromkeys(mom["city"]))
    growth_by_city = mom.drop_duplicates("city").set_index("city")["city_avg_mom_growth_pct"]
    titles = [c + ("" if pd.isna(growth_by_city.get(c)) else
                   f"<br><span style='font-size:11.5px;color:{t.DULL}'>"
                   f"{t.fmt_signed_pct(growth_by_city[c])} a month, on average</span>") for c in cities]
    cols = 1 if len(cities) == 1 else 2
    rows = math.ceil(len(cities) / cols)
    fig = make_subplots(rows=rows, cols=cols, shared_xaxes=True, shared_yaxes=True,
                        subplot_titles=titles, vertical_spacing=0.24, horizontal_spacing=0.08)
    months = pd.period_range(pd.Period(mom["month"].min(), "M"), pd.Period(mom["month"].max(), "M"), freq="M")
    keys = [str(p) for p in months]
    x = [p.to_timestamp() for p in months]
    for i, city in enumerate(cities):
        d = mom[mom["city"] == city].set_index("month")
        regs = d["registrations"].reindex(keys)          # months with no sales stay as gaps
        growth = d["mom_growth_pct"].reindex(keys)
        hover = [f"{city}, {m.strftime('%b %Y')}<br>{t.fmt_int(v)} registrations"
                 + ("" if pd.isna(g) else f"<br>{t.fmt_signed_pct(g)} vs previous month")
                 for m, v, g in zip(x, regs.values, growth.values)]
        fig.add_scatter(x=x, y=regs.values, mode="lines+markers", connectgaps=False,
                        line=dict(color=t.SILVER, width=1.25),
                        marker=dict(size=4, color=t.SILVER),
                        hovertext=hover, hoverinfo="text", showlegend=False,
                        row=i // cols + 1, col=i % cols + 1)
    for i, ann in enumerate(fig.layout.annotations):
        dom = fig.layout[f"xaxis{'' if i == 0 else i + 1}"].domain
        ann.update(x=dom[0], xanchor="left", align="left", font=dict(family=t.SERIF, size=17, color=t.BRIGHT))
    fig.update_xaxes(tickformat="%b %y", dtick="M6", showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=t.HAIRLINE, rangemode="tozero",
                     tickformat=",", matches="y")              # one scale for every panel
    for r in range(1, rows + 1):
        fig.update_yaxes(title_text="registrations / month", row=r, col=1)
    fig.update_layout(height=290 * rows + 70, margin=dict(t=52, b=40))
    return fig


# ---- Marketing funnel ---------------------------------------------------------------

def funnel_by_channel(funnel: pd.DataFrame) -> go.Figure:
    """Each stage gets brighter as it narrows: contacted is an outline,
    registered is matte, attended is polished silver."""
    d = funnel.sort_values("leads", ascending=False)
    stages = [
        ("leads", "leads contacted (outline)", OUTLINE),
        ("registered", "registered (matte)", t.bar_marker()),
        ("attended", "attended (bright)", dict(color=t.silver(0.85), line=dict(width=0))),
    ]
    fig = go.Figure()
    for col, name, marker in stages:
        fig.add_bar(y=d["channel"], x=d[col], orientation="h", name=name, marker=marker,
                    text=[t.fmt_int(v) for v in d[col]], textposition="outside",
                    textfont=QUIET_LABEL, cliponaxis=False,
                    hovertemplate=f"%{{y}}<br>{name.split(' (')[0]}: %{{x:,}}<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.34, bargroupgap=0.14, height=_height(len(d), 80))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=CATEGORY_FONT)
    fig.update_xaxes(title_text="people", showticklabels=False, range=[0, d["leads"].max() * 1.15])
    return fig


def pct_by_channel(funnel: pd.DataFrame, col: str, x_title: str, hover_label: str) -> go.Figure:
    d = funnel.sort_values(col, ascending=False)
    hover = [f"{c}<br>{hover_label}: {t.fmt_pct(v)}" for c, v in zip(d["channel"], d[col])]
    return hbar(d["channel"], d[col], [t.fmt_pct(v) for v in d[col]], x_title=x_title, hover=hover)


# ---- Event deep-dive --------------------------------------------------------------

def registration_curve(curve: pd.DataFrame, capacity: int, start_date: str) -> go.Figure:
    x = pd.to_datetime(curve["registered_on"])
    fig = go.Figure(go.Scatter(
        x=x, y=curve["cumulative_registrations"], mode="lines", line=dict(color=t.SILVER, width=1.5),
        customdata=curve[["days_before_event", "new_registrations"]],
        hovertemplate="%{x|%d %b %Y}<br>%{y:,} registered so far<br>"
                      "+%{customdata[1]} that day, %{customdata[0]} days before the event<extra></extra>",
    ))
    fig.add_hline(y=capacity, line=dict(color=t.FAINT, width=1, dash="dash"),
                  annotation_text=f"capacity {capacity:,}", annotation_position="top left",
                  annotation_font=QUIET_LABEL)
    last = curve.iloc[-1]
    fig.add_annotation(x=x.iloc[-1], y=last["cumulative_registrations"],
                       text=f"{int(last['cumulative_registrations']):,} registered",
                       showarrow=False, xanchor="right", yanchor="bottom", yshift=8,
                       font=dict(family=t.MONO, size=12, color=t.BRIGHT))
    fig.update_layout(height=330, showlegend=False, hovermode="x")
    fig.update_xaxes(title_text="registration date", tickformat="%b %Y")
    fig.update_yaxes(title_text="cumulative registrations", range=[0, capacity * 1.12], tickformat=",")
    return fig


def no_show_by_ticket(no_show: pd.DataFrame) -> go.Figure:
    d = no_show[no_show["breakdown"] == "Ticket type"].set_index("segment")
    d = d.reindex([k for k in t.TICKET_ORDER if k in d.index]
                  + sorted(k for k in d.index if k not in t.TICKET_ORDER))
    hover = [f"{k}<br>{t.fmt_pct(r)} no-show ({t.fmt_int(n)} of {t.fmt_int(g)})"
             for k, r, n, g in zip(d.index, d["no_show_rate_pct"], d["no_shows"], d["registrations"])]
    return hbar(d.index, d["no_show_rate_pct"], [t.fmt_pct(v) for v in d["no_show_rate_pct"]],
                x_title="ticket holders who did not come (%)", hover=hover)


def no_show_by_lead_time(no_show: pd.DataFrame) -> go.Figure:
    d = no_show[no_show["breakdown"] == "Lead time"]
    return hbar(d["segment"], d["no_show_rate_pct"], [t.fmt_pct(v) for v in d["no_show_rate_pct"]],
                x_title="ticket holders who did not come (%)")


def break_even_bars(row: pd.Series) -> go.Figure:
    """Tickets sold against tickets needed. No-shows have paid, so tickets decide
    break-even; attendance is drawn underneath as a reference for sponsors."""
    below = row["status"] == "Below break-even"
    sold, needed, came = float(row["tickets_sold"]), float(row["breakeven_tickets"]), float(row["attended"])
    labels = ["tickets sold", "needed to<br>break even", "attended"]
    fig = go.Figure()
    fig.add_bar(y=[labels[0]], x=[sold], orientation="h", marker=t.bar_marker("flag" if below else "normal"),
                text=[t.fmt_int(sold)], textposition="outside", cliponaxis=False,
                textfont=dict(LABEL_FONT, color=t.BRIGHT if below else t.SILVER),
                hovertemplate=f"tickets sold {t.fmt_int(sold)}<extra></extra>")
    # The target is an outline: it is a threshold, not a quantity.
    fig.add_bar(y=[labels[1]], x=[needed], orientation="h", marker=OUTLINE,
                text=[t.fmt_int(needed)], textposition="outside", cliponaxis=False, textfont=QUIET_LABEL,
                hovertemplate=f"paid tickets needed to cover fixed cost {t.fmt_int(needed)}<extra></extra>")
    fig.add_bar(y=[labels[2]], x=[came], orientation="h", marker=t.bar_marker("pending"), width=0.35,
                text=[t.fmt_int(came)], textposition="outside", cliponaxis=False, textfont=QUIET_LABEL,
                hovertemplate=f"people who attended {t.fmt_int(came)} (no-shows had still paid)<extra></extra>")
    top = max(sold, needed, came)
    if below:
        t.annotate(fig, sold, 0, f"{int(needed - sold):,} short", xshift=44)
    fig.update_layout(height=220, showlegend=False, barmode="overlay")
    fig.update_yaxes(type="category", categoryorder="array", categoryarray=labels, autorange="reversed",
                     showgrid=False, tickfont=CATEGORY_FONT)
    fig.update_xaxes(title_text="people", showticklabels=False, range=[0, top * 1.7])
    return fig


def pacing_chart(curve: pd.DataFrame, pace: pd.Series, as_of: str) -> go.Figure:
    """Tickets sold so far, the break-even line, and the projected range at the
    event date. The projection is dotted and drawn as a range, never as a fact."""
    cap, need = int(pace["capacity"]), pace["breakeven_tickets"]
    start = pd.Timestamp(pace["start_date"])
    fig = go.Figure()
    if not curve.empty:
        x = pd.to_datetime(curve["registered_on"])
        fig.add_scatter(x=x, y=curve["cumulative_registrations"], mode="lines",
                        line=dict(color=t.SILVER, width=1.5), name="sold so far",
                        hovertemplate="%{x|%d %b %Y}<br>%{y:,} tickets sold<extra></extra>")
    if pd.notna(pace["projected_tickets"]):
        sold = int(pace["sold_so_far"])
        fig.add_scatter(x=[pd.Timestamp(as_of), start], y=[sold, pace["projected_tickets"]], mode="lines",
                        line=dict(color=t.DULL, width=1, dash="dot"), hoverinfo="skip", name="projection")
        fig.add_scatter(x=[start], y=[pace["projected_tickets"]], mode="markers",
                        marker=dict(symbol="circle-open", size=9, color=t.BRIGHT),
                        error_y=dict(type="data", symmetric=False, color=t.DULL, thickness=1, width=8,
                                     array=[pace["projected_high"] - pace["projected_tickets"]],
                                     arrayminus=[pace["projected_tickets"] - pace["projected_low"]]),
                        hovertemplate=(f"projected {t.fmt_int(pace['projected_tickets'])} tickets<br>"
                                       f"range {t.fmt_int(pace['projected_low'])} to {t.fmt_int(pace['projected_high'])}"
                                       "<extra></extra>"), name="projected")
        t.annotate(fig, start, pace["projected_tickets"], "projected", xanchor="right", xshift=-14, yshift=14)
    if pd.notna(need):
        fig.add_hline(y=need, line=dict(color=t.SILVER, width=1, dash="dash"),
                      annotation_text=f"break-even {int(need):,} tickets", annotation_position="bottom left",
                      annotation_font=dict(family=t.MONO, size=11, color=t.SILVER))
    fig.add_hline(y=cap, line=dict(color=t.FAINT, width=1, dash="dot"),
                  annotation_text=f"capacity {cap:,}", annotation_position="top left",
                  annotation_font=QUIET_LABEL)
    fig.add_vline(x=pd.Timestamp(as_of), line=dict(color=t.FAINT, width=1))
    # Fix the time window explicitly: with no sales yet there is no line to set it.
    first = pd.to_datetime(curve["registered_on"]).min() if not curve.empty else pd.Timestamp(as_of)
    window = [min(first, pd.Timestamp(as_of)) - pd.Timedelta(days=14), start + pd.Timedelta(days=14)]
    fig.update_layout(height=340, showlegend=False, hovermode="closest")
    fig.update_xaxes(title_text="date", tickformat="%b %Y", type="date", range=window)
    fig.update_yaxes(title_text="tickets", range=[0, cap * 1.12], tickformat=",")
    return fig


def feedback_themes(themes: pd.DataFrame) -> go.Figure:
    text = [f"{t.fmt_pct(s)}   avg {t.fmt_rating(r)}" for s, r in zip(themes["share_pct"], themes["avg_rating"])]
    hover = [f"{c}<br>{t.fmt_int(m)} comments ({t.fmt_pct(s)})<br>average rating {t.fmt_rating(r)} / 5"
             for c, m, s, r in zip(themes["comment_theme"], themes["mentions"], themes["share_pct"], themes["avg_rating"])]
    fig = hbar(themes["comment_theme"], themes["share_pct"], text,
               x_title="share of survey comments (%)", hover=hover)
    fig.update_xaxes(range=[0, themes["share_pct"].max() * 1.6])
    return fig
