"""Regression tests for the five break points found in the project review.

Each test reproduces a failure the review demonstrated. They failed on the
code as reviewed and pass now, so the weak points cannot quietly come back.
"""

import shutil
import sqlite3
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import generate_data
import load_csv
from lib import db

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["views/1_overview.py", "views/2_marketing_funnel.py",
         "views/3_event_deep_dive.py", "views/4_query_explorer.py"]


def q(name, path, filters=None):
    return db.run_query(name, filters, db_path=path)


def run_page(page, event=None):
    """Load a page like a visitor would; return the first exception seen, if any."""
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    errors = list(at.exception)
    if event is not None and not errors:
        at.selectbox(key="f_event").set_value(event)
        at.run()
        errors += list(at.exception)
    if page != PAGES[0] and not errors:
        at.switch_page(page)
        at.run()
        errors += list(at.exception)
    return at, errors


# ---- 1. Upcoming events --------------------------------------------------------
# Review: 120 pre-sold tickets moved Early Bird no-show from 14.6% to 23.1%,
# labelled a future event "below break-even", and an unsold event crashed the page.

def test_upcoming_tickets_do_not_change_attendance_figures(db_path, tmp_path):
    without = tmp_path / "without_upcoming.db"
    shutil.copy(db_path, without)
    con = sqlite3.connect(without)
    assert con.execute("SELECT COUNT(*) FROM registrations WHERE attended IS NULL").fetchone()[0] > 0
    con.execute("DELETE FROM registrations WHERE attended IS NULL")
    con.commit()
    con.close()
    for name in ["no_show_rates", "feedback_by_ticket"]:
        pd.testing.assert_frame_equal(q(name, db_path), q(name, without))
    a, b = q("channel_funnel", db_path).set_index("channel"), q("channel_funnel", without).set_index("channel")
    pd.testing.assert_series_equal(a["attendance_rate_pct"], b["attendance_rate_pct"].reindex(a.index))
    assert q("kpi_summary", db_path).iloc[0]["attendance_rate_pct"] == q("kpi_summary", without).iloc[0]["attendance_rate_pct"]


def test_upcoming_events_are_never_judged_on_break_even(db_path):
    events = q("event_summary", db_path)
    upcoming = set(events.loc[events["status"] == "Upcoming", "event_id"])
    assert upcoming, "the demo should include upcoming events"
    assert not upcoming & set(q("break_even", db_path)["event_id"])


def test_event_with_no_sales_gets_no_projection_not_a_guess(db_path):
    pace = q("upcoming_pacing", db_path)
    unsold = pace[pace["sold_so_far"] == 0]
    assert len(unsold) == 1
    assert unsold.iloc[0]["pacing_status"] == "No sales yet"
    assert unsold[["projected_low", "projected_tickets", "projected_high"]].isna().all(axis=None)


def test_projection_is_a_range_within_capacity(db_path):
    pace = q("upcoming_pacing", db_path).dropna(subset=["projected_tickets"])
    assert not pace.empty
    assert (pace["projected_low"] <= pace["projected_tickets"]).all()
    assert (pace["projected_tickets"] <= pace["projected_high"]).all()
    assert (pace["projected_high"] <= pace["capacity"]).all()
    assert (q("upcoming_pacing", db_path)["comparables"] <= 3).all()   # bounded work at any scale


def test_event_counts_agree_between_queries(db_path):
    kpi = q("kpi_summary", db_path).iloc[0]
    events = q("event_summary", db_path)
    assert kpi["events"] == len(events)
    assert kpi["completed_events"] == (events["status"] == "Completed").sum()
    assert kpi["upcoming_events"] == (events["status"] == "Upcoming").sum()


@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("event", [9, 10])          # on sale, and announced with no sales
def test_every_page_handles_upcoming_events(page, event):
    _, errors = run_page(page, event)
    assert not errors, errors[0].message


def test_event_that_cannot_break_even_is_flagged_at_risk(db_path, tmp_path, monkeypatch):
    # Even a sell-out cannot cover this fixed cost, so it must never read "On track".
    path = tmp_path / "risky.db"
    shutil.copy(db_path, path)
    con = sqlite3.connect(path)
    con.execute("UPDATE events SET fixed_cost = 2000000 WHERE event_id = 9")
    con.commit()
    con.close()
    pace = q("upcoming_pacing", path, {"event_id": 9}).iloc[0]
    assert pace["breakeven_tickets"] > pace["capacity"]
    assert pace["pacing_status"] == "At risk"
    monkeypatch.setenv("EVENTS_DB", str(path))
    at, errors = run_page(PAGES[2], 9)
    assert not errors
    assert any("at risk" in str(h.proto) for h in at.get("html"))


# ---- 2. Real data ---------------------------------------------------------------
# Review: a new city or speciality was rejected, 680 website sign-ups vanished
# from the funnel, the banner would mislabel real data, and a missing database
# was silently replaced with invented data.

def test_csv_round_trip_is_lossless(db_path, tmp_path):
    as_of = load_csv.export_demo(tmp_path / "csv", db_path)
    ok, report = load_csv.load(tmp_path / "csv", tmp_path / "loaded.db", as_of, "round trip")
    assert ok, report
    for path in db.query_files():
        name = path.stem.split("_", 1)[1]
        pd.testing.assert_frame_equal(q(name, db_path), q(name, tmp_path / "loaded.db"), check_dtype=False)


def _messy_export(db_path, folder):
    load_csv.export_demo(folder, db_path)
    regs = (folder / "registrations.csv").read_text(encoding="utf-8").splitlines()
    cells = regs[4].split(",")
    cells[3] = "03/04/2025"                                  # row 5: ambiguous date
    regs[4] = ",".join(cells)
    cells = regs[5].split(",")
    cells[1] = "99"                                          # row 6: no such event
    regs[5] = ",".join(cells)
    (folder / "registrations.csv").write_text("\n".join(regs) + "\n", encoding="utf-8")


def test_loader_reports_every_problem_and_writes_nothing(db_path, tmp_path):
    _messy_export(db_path, tmp_path / "csv")
    out = tmp_path / "out.db"
    ok, report = load_csv.load(tmp_path / "csv", out, "2026-10-09")
    assert not ok and not out.exists()
    assert "row 5" in report and "not YYYY-MM-DD" in report
    assert "no such event" in report and "row 6" in report


def test_new_city_speciality_and_unlinked_channel_load(db_path, tmp_path):
    folder = tmp_path / "csv"
    load_csv.export_demo(folder, db_path)
    with (folder / "events.csv").open("a", encoding="utf-8") as fh:
        fh.write("11,Ophthalmology Forum Jeddah 2027,Ophthalmology,Jeddah,2027-04-20,500,1300,200000,\n")
    with (folder / "registrations.csv").open("a", encoding="utf-8") as fh:
        fh.write("999001,11,1,2026-09-01,Standard,1300,Website,\n")
    ok, report = load_csv.load(folder, tmp_path / "loaded.db", "2026-10-09")
    assert ok, report
    loaded = tmp_path / "loaded.db"
    assert "Jeddah" in set(q("event_summary", loaded)["city"])
    funnel, kpi = q("channel_funnel", loaded), q("kpi_summary", loaded).iloc[0]
    assert funnel["registered"].sum() == kpi["registrations"]           # nobody drops out
    website = funnel.set_index("channel").loc["Website"]
    assert website["leads"] == 0 and pd.isna(website["lead_to_registration_pct"])


def test_loaded_data_is_labelled_as_loaded_not_simulated(db_path, tmp_path, monkeypatch):
    load_csv.export_demo(tmp_path / "csv", db_path)
    ok, _ = load_csv.load(tmp_path / "csv", tmp_path / "loaded.db", "2026-10-09", "Acme CRM export")
    assert ok
    monkeypatch.setenv("EVENTS_DB", str(tmp_path / "loaded.db"))
    at, errors = run_page(PAGES[0])
    assert not errors
    html = " ".join(str(h.proto) for h in at.get("html"))
    assert "Acme CRM export" in html
    assert "Simulated data. Concept demo" not in html


def test_missing_configured_database_is_never_replaced(tmp_path, monkeypatch):
    missing = tmp_path / "not_there.db"
    monkeypatch.setenv("EVENTS_DB", str(missing))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    assert not missing.exists()
    assert any("not found" in e.value for e in at.error)


def test_generator_refuses_to_overwrite_loaded_data(db_path, tmp_path):
    load_csv.export_demo(tmp_path / "csv", db_path)
    target = tmp_path / "loaded.db"
    assert load_csv.load(tmp_path / "csv", target, "2026-10-09")[0]
    before = target.read_bytes()
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        generate_data.generate(target)
    assert target.read_bytes() == before


# ---- 3. Break-even ---------------------------------------------------------------
# Review: in 5 of 40 seeds a profitable event was labelled "below break-even",
# because attendees were compared with a ticket-revenue threshold.

@pytest.mark.parametrize("seed", [4, 10, 22, 31, 32, 2026])     # the five that contradicted, plus the default
def test_break_even_status_agrees_with_margin(seed, tmp_path):
    path = tmp_path / f"seed{seed}.db"
    generate_data.generate(path, seed)
    be = q("break_even", path)
    assert ((be["status"] == "Below break-even") == (be["margin_aed"] < 0)).all()


def test_recorded_sponsorship_counts_toward_break_even(db_path, tmp_path):
    path = tmp_path / "sponsored.db"
    shutil.copy(db_path, path)
    con = sqlite3.connect(path)
    con.execute("UPDATE events SET sponsorship_revenue = 30000 WHERE event_id = 6")
    con.commit()
    con.close()
    before = q("break_even", db_path, {"event_id": 6}).iloc[0]
    after = q("break_even", path, {"event_id": 6}).iloc[0]
    assert before["status"] == "Below break-even" and after["status"] == "Above break-even"
    assert after["margin_aed"] == before["margin_aed"] + 30000
    assert after["breakeven_tickets"] < before["breakeven_tickets"]


# ---- 4. Scale --------------------------------------------------------------------
# Review: 328 events made the Overview 19,488 px tall and one Query Explorer
# table a 9.6 MB page.

def _clone_events(src, dst, copies):
    shutil.copy(src, dst)
    con = sqlite3.connect(dst)
    n = con.execute("SELECT MAX(event_id) FROM events").fetchone()[0]
    for k in range(1, copies + 1):
        off = n * k
        con.execute(f"INSERT INTO events SELECT event_id+{off}, name||' #{k}', speciality, city, start_date, "
                    f"capacity, base_ticket_price, fixed_cost, sponsorship_revenue FROM events WHERE event_id <= {n}")
        base = con.execute("SELECT MAX(registration_id) FROM registrations").fetchone()[0]
        con.execute(f"INSERT INTO registrations SELECT registration_id+{base}, event_id+{off}, attendee_id, "
                    f"registered_on, ticket_type, price_paid, channel, attended FROM registrations WHERE event_id <= {n}")
    con.commit()
    con.close()


def test_long_event_lists_are_capped_and_big_tables_paged(db_path, tmp_path, monkeypatch):
    big = tmp_path / "big.db"
    _clone_events(db_path, big, 12)                         # 130 events
    monkeypatch.setenv("EVENTS_DB", str(big))
    at, errors = run_page(PAGES[0])
    assert not errors
    import json
    revenue = json.loads(at.get("plotly_chart")[0].proto.spec)
    bars = sum(len(trace.get("y", [])) for trace in revenue["data"])
    assert bars <= 12
    # The caption must describe what is really shown: 13 copies x (1 below break-even
    # + 2 upcoming) = 39 flagged events, more than the 12 that fit.
    notes = " ".join(str(h.proto) for h in at.get("html"))
    assert "the earliest 12 of 39 events that are below break-even or still upcoming" in notes

    at, errors = run_page(PAGES[3])
    at.selectbox(key="qx_query").set_value("registration_curve")
    at.run()
    assert not at.exception
    rows = max(str(h.proto).count("<tr>") for h in at.get("html"))
    assert rows <= 201                                      # 200 rows plus the header


# ---- 5. Folder names ---------------------------------------------------------------
# Review: a project in a folder such as "Projects #2" could not open its database.

@pytest.mark.parametrize("folder", ["Projects #2", "What? Data", "100% done",
                                    "OneDrive - Acme Events", "\u0628\u064a\u0627\u0646\u0627\u062a"])  # the last one is "data" in Arabic script
def test_database_opens_from_awkward_folder_names(db_path, tmp_path, folder):
    target = tmp_path / folder / "events.db"
    target.parent.mkdir()
    shutil.copy(db_path, target)
    assert len(q("event_summary", target)) == 10
