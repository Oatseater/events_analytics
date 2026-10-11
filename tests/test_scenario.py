"""Scenario checks: the simulated world contains the stories the demo is built
to surface. If someone changes the generator and a story disappears, these
fail before the findings brief silently changes meaning."""

from lib.db import run_query


def test_whatsapp_attends_more_than_cold_call(db_path):
    df = run_query("channel_funnel", db_path=db_path).set_index("channel")
    gap = df.loc["WhatsApp", "attendance_rate_pct"] - df.loc["Cold Call", "attendance_rate_pct"]
    assert 12 <= gap <= 28


def test_early_bird_no_show_lower_than_late(db_path):
    df = run_query("no_show_rates", db_path=db_path)
    t = df[df["breakdown"] == "Ticket type"].set_index("segment")["no_show_rate_pct"]
    assert t["Late"] - t["Early Bird"] >= 10


def test_exactly_one_event_below_break_even(db_path):
    df = run_query("break_even", db_path=db_path)
    assert (df["status"] == "Below break-even").sum() == 1


def test_riyadh_grows_fastest(db_path):
    df = run_query("mom_growth_by_city", db_path=db_path)
    avg = df.groupby("city")["city_avg_mom_growth_pct"].first()
    assert avg.idxmax() == "Riyadh"


def test_pricing_feedback_concentrated_in_student_and_standard(db_path):
    df = run_query("feedback_by_ticket", db_path=db_path).set_index("ticket_type")
    top_two = set(df["pricing_share_pct"].nlargest(2).index)
    assert top_two == {"Student", "Standard"}
