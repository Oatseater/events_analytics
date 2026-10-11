"""Write findings_brief.md from the SQL query results.

Simulated data. Concept demo, not real company data.

Usage:
    python make_brief.py                      # reads data/events.db, writes findings_brief.md
    python make_brief.py --out other.md

No number in the brief is typed by hand. Every figure, and every channel,
ticket type and event name, is read from the same queries/*.sql files the
dashboard runs, so the brief and the dashboard always agree.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from lib import db
from lib import theme as t

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "findings_brief.md"
NOTICE = "Simulated data. Concept demo, not real company data."


def _month(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%b %Y")


def finding_channels(db_path) -> str:
    f = db.run_query("channel_funnel", db_path=db_path)
    best = f.loc[f["attendance_rate_pct"].idxmax()]
    worst = f.loc[f["attendance_rate_pct"].idxmin()]
    gap = best["attendance_rate_pct"] - worst["attendance_rate_pct"]
    if worst["channel"] == f.loc[f["lead_to_registration_pct"].idxmin(), "channel"]:
        conversion = f"{worst['channel']} also turns the fewest leads into tickets"
    else:
        conversion = f"{worst['channel']} turns"
    conversion += (f": {t.fmt_pct(worst['lead_to_registration_pct'])}, against "
                   f"{t.fmt_pct(best['lead_to_registration_pct'])} for {best['channel']}.")
    return f"""### 1. {best['channel']} sign-ups show up. {worst['channel']} sign-ups often don't.

Number: {t.fmt_pct(best['attendance_rate_pct'])} of people who registered through {best['channel']} came. {t.fmt_pct(worst['attendance_rate_pct'])} of {worst['channel']} ones did. That's a gap of {t.fmt_pp(gap)}. {conversion}

Why it matters: a paid ticket with nobody behind it is still an empty seat on the day. [PLACEHOLDER: if sponsor deals are judged on turnout, say so here.]

What to do: move some {worst['channel']} time to {best['channel']}. Try a {best['channel']} reminder for people who signed up through {worst['channel']}.

*Dashboard: Marketing Funnel, "Turnout by channel".*
"""


def finding_no_shows(db_path) -> str:
    n = db.run_query("no_show_rates", db_path=db_path)
    by_ticket = n[n["breakdown"] == "Ticket type"].set_index("segment")
    worst = by_ticket["no_show_rate_pct"].idxmax()
    best = by_ticket["no_show_rate_pct"].idxmin()
    lead = n[n["breakdown"] == "Lead time"].set_index("segment")["no_show_rate_pct"]
    ratio = by_ticket.loc[worst, "no_show_rate_pct"] / by_ticket.loc[best, "no_show_rate_pct"]
    return f"""### 2. {worst} buyers are the likeliest to pay and not come

Number: {t.fmt_pct(by_ticket.loc[worst, 'no_show_rate_pct'])} of {worst} tickets were no-shows, {t.fmt_int(by_ticket.loc[worst, 'no_shows'])} people. {best}: {t.fmt_pct(by_ticket.loc[best, 'no_show_rate_pct'])}. That's about {ratio:.1f} times as often. People who booked in the last 14 days missed {t.fmt_pct(lead['0-14 days'])} of the time. People who booked more than 90 days out missed {t.fmt_pct(lead['91+ days'])}.

Why it matters: the money is already in, so no-shows look free. They still mean fewer people in the hall.

What to do: sell earlier. Make {best} easier to find and run it longer. Send {worst} buyers a confirmation in the final week.

*Dashboard: Overview, "No-shows by ticket type".*
"""


def finding_break_even(db_path) -> str:
    be = db.run_query("break_even", db_path=db_path)
    below = be[be["status"] == "Below break-even"]
    if below.empty:
        tightest = be.loc[be["ticket_gap"].idxmin()]
        return f"""### 3. Every finished event broke even. {tightest['event_name']} only just.

Number: {tightest['event_name']} sold {t.fmt_int(tightest['ticket_gap'])} paid tickets more than it needed to cover its fixed cost.

Why it matters: a thin margin leaves no room for a slow sales month.

What to do: check every upcoming event against its break-even line eight weeks out.

*Dashboard: Overview, "Upcoming events"; Event Deep-Dive, "Break-even".*
"""
    ev = below.sort_values("ticket_gap").iloc[0]
    others = len(below) - 1
    extra = f" {others} other finished event(s) also fell short." if others else ""
    summary = db.run_query("event_summary", {"event_id": int(ev["event_id"])}, db_path=db_path).iloc[0]
    margin = ("a loss of " + t.fmt_aed(abs(ev["margin_aed"]))) if ev["margin_aed"] < 0 \
        else ("a margin of just " + t.fmt_aed(ev["margin_aed"]))
    sponsorship = ("Sponsorship isn't in this data, so this is tickets only."
                   if pd.isna(ev["sponsorship_aed"]) else
                   f"That counts {t.fmt_aed(ev['sponsorship_aed'])} of recorded sponsorship.")
    curve = db.run_query("registration_curve", {"event_id": int(ev["event_id"])}, db_path=db_path)
    by_8_weeks = curve[curve["days_before_event"] >= 56]
    sold_8w = int(by_8_weeks["cumulative_registrations"].iloc[-1]) if not by_8_weeks.empty else 0
    early_signal = (f"eight weeks out it had sold {t.fmt_int(sold_8w)} tickets, "
                    f"{t.fmt_pct(100 * sold_8w / ev['breakeven_tickets'])} of what it needed. "
                    "The problem was visible early.")
    return f"""### 3. {ev['event_name']} didn't break even

Number: it needed {t.fmt_int(ev['breakeven_tickets'])} paid tickets at its average price ({t.fmt_aed(ev['avg_ticket_aed'])}) to cover {t.fmt_aed(ev['fixed_cost_aed'])} of fixed cost. It sold {t.fmt_int(ev['tickets_sold'])}. That's {t.fmt_int(abs(ev['ticket_gap']))} short, and {margin}. {t.fmt_int(ev['attended'])} of those ticket holders came. It filled {t.fmt_pct(summary['fill_rate_pct'])} of its {t.fmt_int(summary['capacity'])} seats.{extra} {sponsorship}

Why it matters: {early_signal}

What to do: check every event against its break-even line eight weeks out, with a fallback agreed in advance, like a smaller venue. The Overview now does this for upcoming events, as a range.

*Dashboard: Overview, the bright bar in "Ticket revenue by event" and "Upcoming events".*
"""


def notice(db_path) -> str:
    """A true statement about where the figures came from, whatever the source."""
    info = db.dataset_info(db_path)
    if info.get("source") == "simulated":
        return f"**{NOTICE}** All names and figures are invented to demonstrate the analysis."
    if info.get("source") == "loaded":
        return f"**Built from {info.get('source_name', 'loaded exports')}, as of {info.get('as_of_date', 'an unknown date')}.**"
    return "**Data source unknown.** Treat these figures as unverified."


def build_brief(db_path=None) -> str:
    db_path = db_path or db.db_path()
    kpi = db.run_query("kpi_summary", db_path=db_path).iloc[0]
    events = db.run_query("event_summary", db_path=db_path)
    done = events[events["status"] == "Completed"]
    period = f"{_month(done['start_date'].min())} to {_month(done['start_date'].max())}"
    upcoming = int(kpi["upcoming_events"] or 0)
    later = (f" {upcoming} upcoming event{'s are' if upcoming != 1 else ' is'} left out of turnout "
             "until they happen.") if upcoming else ""
    return f"""# Events Analytics: three findings

> {notice(db_path)}

Scope: {t.fmt_int(kpi['completed_events'])} finished medical conferences, {period}, plus tickets sold so far for the ones still to come. {t.fmt_int(kpi['registrations'])} tickets. {t.fmt_aed(kpi['revenue_aed'])} in ticket revenue. {t.fmt_pct(kpi['attendance_rate_pct'])} of ticket holders came to the finished events.{later}

{finding_channels(db_path)}
{finding_no_shows(db_path)}
{finding_break_even(db_path)}
---
*Written by `make_brief.py` from the SQL in `queries/`. No number here is typed by hand. {notice(db_path).replace('**', '')}*
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate findings_brief.md from the query results.")
    parser.add_argument("--db", type=Path, default=None, help="default: $EVENTS_DB or the demo database")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.write_text(build_brief(args.db), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
