"""Marketing Funnel: leads -> registrations -> attendance, by channel.

Each takeaway line is written from the query result at run time, so it
changes with the filters and never contains a hand-typed number."""

import html

import streamlit as st

from lib import charts, ui
from lib import theme as t

filters = ui.get_filters()
ui.page_header("Marketing Funnel", "Which channels bring people who actually show up.", filters)

funnel = ui.q("channel_funnel", filters)
if funnel.empty:
    ui.empty_state()
    st.stop()

def pick(col: str, best: bool = True):
    """Row with the highest (or lowest) value, or None when nothing is known yet."""
    known = funnel.dropna(subset=[col])
    if known.empty:
        return None
    return known.loc[known[col].idxmax() if best else known[col].idxmin()]


most_leads = funnel.loc[funnel["leads"].idxmax()]
best_yield = pick("lead_to_attendance_pct")
conv_best, conv_worst = pick("lead_to_registration_pct"), pick("lead_to_registration_pct", best=False)
att_best, att_worst = pick("attendance_rate_pct"), pick("attendance_rate_pct", best=False)
has_attendance = att_best is not None

untracked = funnel[funnel["leads"] == 0]
if not untracked.empty:
    n = int(untracked["registered"].sum())
    st.html(f'<div class="ea-meta">{n:,} registration{"s" if n != 1 else ""} came through channels with no '
            f'tracked sales leads ({html.escape(", ".join(untracked["channel"]))}). They are counted below, '
            "but have no lead-conversion rate.</div>")

if best_yield is None:
    funnel_takeaway = (f"{most_leads['channel']} brings the most leads ({t.fmt_int(most_leads['leads'])}). "
                       "Turnout isn't known yet for these events.")
elif most_leads["channel"] == best_yield["channel"]:
    funnel_takeaway = (f"{most_leads['channel']} brings the most leads ({t.fmt_int(most_leads['leads'])}), and "
                       f"{t.fmt_pct(best_yield['lead_to_attendance_pct'])} of them make it to the event. Nothing beats that.")
else:
    funnel_takeaway = (f"{most_leads['channel']} brings the most leads ({t.fmt_int(most_leads['leads'])}). "
                       f"{best_yield['channel']} gets the most of its leads to the event: "
                       f"{t.fmt_pct(best_yield['lead_to_attendance_pct'])}, against "
                       f"{t.fmt_pct(most_leads['lead_to_attendance_pct'])} for {most_leads['channel']}.")

ui.chart_card(
    "Funnel by channel",
    "Contacted, then registered, then came. Each stage is brighter than the one before.",
    charts.funnel_by_channel(funnel),
    takeaway=funnel_takeaway,
    source="02_channel_funnel.sql",
)

left, right = st.columns([5, 4], gap="large")
with left:
    if conv_best is None:
        ui.empty_state("No sales leads tracked for these events.")
    else:
        ui.chart_card(
            "Leads to tickets",
            "Share of contacted leads who bought a ticket.",
            charts.pct_by_channel(funnel.dropna(subset=["lead_to_registration_pct"]), "lead_to_registration_pct",
                                  "leads who bought a ticket (%)", "Conversion"),
            takeaway=(f"{conv_best['channel']} turns {t.fmt_pct(conv_best['lead_to_registration_pct'])} of leads "
                      f"into tickets. {conv_worst['channel']} manages "
                      f"{t.fmt_pct(conv_worst['lead_to_registration_pct'])}."),
            source="02_channel_funnel.sql",
        )
with right:
    if not has_attendance:
        ui.empty_state("Turnout is known once an event happens. None of these has yet.")
    else:
        gap = att_best["attendance_rate_pct"] - att_worst["attendance_rate_pct"]
        ui.chart_card(
            "Turnout by channel",
            "Share of ticket holders who came. Finished events only.",
            charts.pct_by_channel(funnel.dropna(subset=["attendance_rate_pct"]), "attendance_rate_pct",
                                  "ticket holders who came (%)", "Turnout"),
            takeaway=(f"{t.fmt_pct(att_best['attendance_rate_pct'])} of {att_best['channel']} sign-ups came. "
                      f"{t.fmt_pct(att_worst['attendance_rate_pct'])} of {att_worst['channel']} ones did. "
                      f"That's a gap of {t.fmt_pp(gap)}."),
            source="02_channel_funnel.sql",
        )

ui.section("The numbers")
ui.html_table(
    funnel,
    labels={"channel": "Channel", "leads": "Leads", "registered": "Registered", "attended": "Attended",
            "lead_to_registration_pct": "Leads who bought (%)", "attendance_rate_pct": "Turnout (%)",
            "lead_to_attendance_pct": "Leads who came (%)"},
)
