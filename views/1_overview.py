"""Overview: headline numbers, revenue and capacity by event, upcoming-event
pacing, city trends, and no-show rates for events that have happened."""

import pandas as pd
import streamlit as st

from lib import charts, ui
from lib import theme as t

MAX_EVENTS = 12      # beyond this, a bar per event stops being readable
MAX_CITIES = 6

filters = ui.get_filters()
ui.page_header("Overview", "", filters)
ui.aside("Built for fun.")

kpi = ui.q("kpi_summary", filters).iloc[0]
summary = ui.q("event_summary", filters)
breakeven = ui.q("break_even", filters)
pacing = ui.q("upcoming_pacing", filters)
mom = ui.q("mom_growth_by_city", filters)
no_show = ui.q("no_show_rates", filters)

if summary.empty:
    ui.empty_state()
    st.stop()

completed, upcoming = int(kpi["completed_events"] or 0), int(kpi["upcoming_events"] or 0)

n_below = int((breakeven["status"] == "Below break-even").sum())
ui.kpi_row([
    {"label": "Tickets sold", "value": t.fmt_int(kpi["registrations"]),
     "sub": f"{t.fmt_int(kpi['events'])} event{'s' if kpi['events'] != 1 else ''}"
            + (f", {t.fmt_int(kpi['upcoming_tickets'])} for ones still to come" if upcoming else "")},
    {"label": "Ticket revenue (AED)", "value": t.fmt_millions(kpi["revenue_aed"]),
     "sub": "no-shows paid too"},
    {"label": "Turnout", "value": t.fmt_pct(kpi["attendance_rate_pct"]),
     "sub": (f"{t.fmt_int(kpi['attended'])} came, finished events only" if completed
             else "known once an event happens")},
    {"label": "Rating", "value": f"{t.fmt_rating(kpi['avg_rating'])} / 5",
     "sub": f"{t.fmt_int(kpi['responses'])} survey answers"},
    {"label": "Below break-even", "value": f"{n_below} of {completed}" if completed else "-",
     "sub": ("didn't cover fixed cost" if n_below
             else ("every finished event covered its costs" if completed else "no finished events selected")),
     "alert": n_below > 0},
])

# ---- the lead visual: money per event, with the one problem in polished silver ----
ui.section("Events")
shown = summary
if len(summary) > MAX_EVENTS and not st.toggle(f"Show all {len(summary):,} events", key="ov_all_events"):
    # Keep what needs a decision (below break-even, upcoming), then fill with the most recent.
    must = summary["event_id"].isin(breakeven.loc[breakeven["status"] == "Below break-even", "event_id"]) \
        | (summary["status"] == "Upcoming")
    rest = summary[~must].sort_values("start_date").tail(max(0, MAX_EVENTS - int(must.sum())))
    keep = set(summary[must].head(MAX_EVENTS)["event_id"]) | set(rest["event_id"])
    shown = summary[summary["event_id"].isin(keep)]          # still in date order
    # Say exactly what is on screen: at scale there can be more flagged events than room.
    flagged = int(must.sum())
    which = ("every event below break-even or still upcoming, then the most recent" if flagged <= MAX_EVENTS
             else f"the earliest {MAX_EVENTS} of {flagged:,} events that are below break-even or still upcoming")
    st.html(f'<div class="ea-meta">showing {len(shown)} of {len(summary):,} events: {which}. '
            "Narrow the filters, switch on show all, or see every row in the Query Explorer.</div>")
left, right = st.columns([3, 2], gap="large")
with left:
    ui.chart_card(
        "Ticket revenue by event",
        "The bright bar didn't cover its fixed cost. Outlines are events still to come, sales so far.",
        charts.revenue_by_event(shown, breakeven),
        source="01_event_summary.sql, 06_break_even.sql",
    )
with right:
    ui.chart_card(
        "Tickets against seats",
        "Filled is sold, the outline is capacity. Events still to come show sales so far.",
        charts.registrations_vs_capacity(shown),
        source="01_event_summary.sql",
    )

if not pacing.empty:
    ui.section("Still to come")
    ui.chart_head(
        "Upcoming events",
        "Tickets sold so far, and where similar past events ended up from the same point. "
        "A projection, so it is shown as a range.",
    )
    order = {"At risk": 0, "Watch": 1, "Too early to project": 2, "No sales yet": 3, "On track": 4}
    pacing = pacing.sort_values(["pacing_status", "start_date"], key=lambda c: c.map(order) if c.name == "pacing_status" else c)
    n_risk = int((pacing["pacing_status"] == "At risk").sum())
    if len(pacing) > MAX_EVENTS:
        limit = max(MAX_EVENTS, n_risk)                       # never hide an event that is at risk
        st.html(f'<div class="ea-meta">showing {limit} of {len(pacing):,} upcoming events, at risk first'
                f'{" (all " + str(n_risk) + " at-risk events included)" if n_risk else ""}. '
                "Every row is in the Query Explorer, query 11.</div>")
        pacing = pacing.head(limit)
    table = pacing.assign(
        projected=[("-" if pd.isna(p) else f"{int(lo):,} to {int(hi):,}")
                   for p, lo, hi in zip(pacing["projected_tickets"], pacing["projected_low"], pacing["projected_high"])],
    )[["event_name", "start_date", "days_to_go", "sold_so_far", "projected", "breakeven_tickets", "capacity", "pacing_status"]]
    ui.html_table(table, labels={"event_name": "Event", "start_date": "Starts", "days_to_go": "Days to go",
                                 "sold_so_far": "Sold so far", "projected": "Projected final tickets",
                                 "breakeven_tickets": "Needed to break even", "capacity": "Capacity",
                                 "pacing_status": "Status"})
    st.html('<div class="ea-source">source: queries/11_upcoming_pacing.sql</div>')

if not mom.empty:
    ui.section("Cities")
    top_cities = mom.groupby("city")["registrations"].sum().nlargest(MAX_CITIES).index
    city_note = (f" Showing the {MAX_CITIES} busiest of {mom['city'].nunique()} cities."
                 if mom["city"].nunique() > MAX_CITIES else "")
    ui.chart_card(
        "Registrations by month, per city",
        "Same scale in every panel. Each sharp drop is the month the event itself happens." + city_note,
        charts.city_trend(mom[mom["city"].isin(top_cities)]),
        source="04_mom_growth_by_city.sql",
    )

ui.section("Turnout")
if no_show.empty:
    ui.empty_state("Turnout is known once an event happens. None of these has yet.")
else:
    left, right = st.columns([2, 3], gap="large")
    with left:
        ui.chart_card(
            "No-shows by ticket type",
            "Share of paid tickets where nobody came. Finished events only.",
            charts.no_show_by_ticket(no_show),
            source="03_no_show_rates.sql",
        )
    with right:
        ui.chart_card(
            "No-shows by booking time",
            "Same measure, by how far ahead people booked.",
            charts.no_show_by_lead_time(no_show),
            source="03_no_show_rates.sql",
        )
