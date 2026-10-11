"""Event Deep-Dive: one event's sales, attendance, break-even and feedback.
An upcoming event shows sales so far and a pacing projection instead, since
its attendance and feedback do not exist yet."""

import html
from datetime import date

import pandas as pd
import streamlit as st

from lib import charts, ui
from lib import theme as t

filters = ui.get_filters()
ui.page_header("Event Deep-Dive", "One event, start to finish.", filters)

scoped = ui.q("event_summary", filters)
if scoped.empty:
    ui.empty_state()
    st.stop()

names = {int(e): n for e, n in zip(scoped["event_id"], scoped["event_name"])}
pick, label_slot = st.columns([1, 1], gap="large")
if filters.get("event_id") is not None:
    event_id = int(filters["event_id"])
    with pick:
        st.html(f'<div class="ea-meta">Event set in the sidebar filter: {html.escape(names[event_id])}</div>')
else:
    if st.session_state.get("dd_event") not in names:
        st.session_state["dd_event"] = list(names)[0]
    with pick:
        event_id = st.selectbox("Event", list(names), format_func=names.get, key="dd_event")

one = {"event_id": event_id, "city": None, "speciality": None}
ev = ui.q("event_summary", one).iloc[0]
curve = ui.q("registration_curve", one)
countries = ui.q("top_countries", one)
upcoming = ev["status"] == "Upcoming"

when = date.fromisoformat(ev["start_date"]).strftime("%d %b %Y").lower()
slug = ev["event_name"].lower().replace(" ", "_")

# Specimen label for the event, written beside the picker like a film annotation.
with label_slot:
    st.html(
        f'<div class="ea-object">object ({int(ev["event_id"]):02d}){" / upcoming" if upcoming else ""}<br>'
        f"<b>{html.escape(slug)}</b><br>"
        f'{html.escape(ev["speciality"].lower())}, {html.escape(ev["city"].lower())}, {when}, '
        f'capacity {t.fmt_int(ev["capacity"])}</div>'
    )


def countries_table() -> None:
    ui.section("Where they came from")
    if countries.empty:
        ui.empty_state("No tickets sold yet.")
        return
    ui.html_table(countries[["country_rank", "country", "registrations", "share_pct"]],
                  labels={"country_rank": "Rank", "country": "Country",
                          "registrations": "Registrations", "share_pct": "Share (%)"})


# ---- upcoming event: pacing, not results ------------------------------------------
if upcoming:
    pace = ui.q("upcoming_pacing", one).iloc[0]
    status = pace["pacing_status"]
    projected = ("-" if pd.isna(pace["projected_tickets"])
                 else f"{t.fmt_int(pace['projected_low'])}-{t.fmt_int(pace['projected_high'])}")
    ui.kpi_row([
        {"label": "Tickets sold so far", "value": t.fmt_int(pace["sold_so_far"]),
         "sub": f"{t.fmt_pct(ev['fill_rate_pct'])} of capacity, as of {ui.as_of_label()}"},
        {"label": "Days to go", "value": t.fmt_int(pace["days_to_go"]), "sub": f"opens {when}"},
        {"label": "Projected final tickets", "value": projected,
         "sub": ("starts with the first sale" if pd.isna(pace["projected_tickets"]) else
                 f"from {int(pace['comparables'])} similar past event"
                 f"{'s' if pace['comparables'] != 1 else ''}; an estimate")},
        {"label": "Needed to break even", "value": t.fmt_int(pace["breakeven_tickets"]),
         "sub": "paid tickets, at the price mix of similar past events"},
        {"label": "Pacing", "value": status.lower().replace(" ", "\n", 1) if len(status) > 9 else status.lower(),
         "alert": status == "At risk",
         "sub": {"On track": "even the slowest projection covers fixed cost",
                 "Watch": "the range straddles break-even",
                 "At risk": "the typical projection falls short",
                 "No sales yet": "pacing starts with the first sale",
                 "Too early to project": "past events had not sold yet at this point"}.get(status, "")},
    ])
    left, right = st.columns([5, 4], gap="large")
    with left:
        ui.chart_card(
            "Where sales are heading",
            f"Tickets sold up to {ui.as_of_label()}, the line it needs to clear, "
            "and the projected range on opening day.",
            charts.pacing_chart(curve, pace, ui.info().get("as_of_date")),
            takeaway=(f"No tickets sold yet as of {ui.as_of_label()}. The projection starts with the first sale."
                      if pace["sold_so_far"] == 0 else
                      f"Similar past events in {ev['city']} had sold {t.fmt_pct(pace['typical_share_by_now_pct'])} "
                      f"of their final tickets by this point, so {t.fmt_int(pace['sold_so_far'])} sold today points "
                      f"to about {t.fmt_int(pace['projected_tickets'])} in the end."),
            source="11_upcoming_pacing.sql, 09_registration_curve.sql",
        )
    with right:
        countries_table()
        st.html('<div class="ea-meta">Turnout, no-shows and feedback come after the event.</div>')
    st.stop()

# ---- completed event: results -------------------------------------------------------
be = ui.q("break_even", one).iloc[0]
no_show = ui.q("no_show_rates", one)
themes = ui.q("feedback_themes", one)
fb = ui.q("kpi_summary", one).iloc[0]
below = be["status"] == "Below break-even"

ui.kpi_row([
    {"label": "Tickets sold", "value": t.fmt_int(ev["registrations"]),
     "sub": f"{t.fmt_pct(ev['fill_rate_pct'])} of capacity"},
    {"label": "Came", "value": t.fmt_int(ev["attended"]),
     "sub": f"{t.fmt_pct(ev['attendance_rate_pct'])} turnout"},
    {"label": "Ticket revenue (AED)", "value": t.fmt_millions(be["ticket_revenue_aed"]),
     "sub": f"fixed cost {t.fmt_aed(be['fixed_cost_aed'])}"},
    {"label": "Margin (AED)", "value": f"{be['margin_aed']:+,.0f}",
     "sub": ("tickets only, sponsorship not recorded" if pd.isna(be["sponsorship_aed"])
             else "tickets and sponsorship, minus fixed cost"),
     "alert": be["margin_aed"] < 0},
    {"label": "Break-even", "value": "not\nreached" if below else "reached",
     "sub": f"{t.fmt_int(be['tickets_sold'])} tickets sold, {t.fmt_int(be['breakeven_tickets'])} needed",
     "alert": below},
])

left, right = st.columns([3, 2], gap="large")
with left:
    ui.chart_card(
        "How it sold",
        "Running total of tickets. The dashed line is capacity.",
        charts.registration_curve(curve, int(ev["capacity"]), ev["start_date"]),
        source="09_registration_curve.sql",
    )
with right:
    ui.chart_card(
        "No-shows by ticket type",
        "Share of paid tickets where nobody came.",
        charts.no_show_by_ticket(no_show),
        source="03_no_show_rates.sql",
    )

left, right = st.columns([2, 3], gap="large")
with left:
    gap = int(be["ticket_gap"])
    result = (f"{t.fmt_int(-gap)} tickets short of break-even." if below
              else f"{t.fmt_int(gap)} tickets past break-even.")
    ui.chart_card(
        "Break-even",
        f"Tickets needed = fixed cost / average ticket price ({t.fmt_aed(be['avg_ticket_aed'])}). "
        "No-shows paid too, so tickets decide it.",
        charts.break_even_bars(be),
        takeaway=f"{result} {t.fmt_int(be['attended'])} of {t.fmt_int(be['tickets_sold'])} ticket holders came.",
        source="06_break_even.sql",
    )
with right:
    if themes.empty:
        ui.empty_state("No survey answers for this event.")
    else:
        ui.chart_card(
            "What people said",
            f"Themes from {t.fmt_int(fb['responses'])} survey answers, with the average rating out of 5 for each.",
            charts.feedback_themes(themes),
            source="10_feedback_themes.sql",
        )
    countries_table()
