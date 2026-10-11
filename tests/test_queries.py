"""Every SQL file runs, returns rows, and is documented."""

import re

import pytest

from lib.db import query_files, read_sql, run_query

QUERY_NAMES = [p.stem.split("_", 1)[1] for p in query_files()]


def test_there_are_at_least_seven_queries():
    assert len(QUERY_NAMES) >= 7


@pytest.mark.parametrize("name", QUERY_NAMES)
def test_query_runs_and_returns_rows(name, db_path):
    df = run_query(name, db_path=db_path)
    assert len(df) > 0


@pytest.mark.parametrize("name", QUERY_NAMES)
@pytest.mark.parametrize("filters", [{"city": "Riyadh"}, {"speciality": "Dental"}, {"event_id": 1}])
def test_query_respects_filters(name, filters, db_path):
    df = run_query(name, filters, db_path=db_path)
    if name == "upcoming_pacing":
        # Riyadh and event 1 have no upcoming events, so empty is the correct
        # answer there; Dental includes the upcoming Dental Congress Dubai 2027.
        expected = {"city": [], "speciality": ["Dental Congress Dubai 2027"], "event_id": []}
        assert list(df["event_name"]) == expected[next(iter(filters))]
    else:
        assert len(df) > 0


@pytest.mark.parametrize("name", QUERY_NAMES)
def test_query_has_header_comment(name):
    head = read_sql(name)[:1500]
    assert "Business question:" in head
    assert "Technique:" in head


@pytest.mark.parametrize("name", QUERY_NAMES)
def test_query_is_short_enough_to_read(name):
    assert len(read_sql(name).splitlines()) <= 80


def test_city_filter_really_filters(db_path):
    df = run_query("event_summary", {"city": "Seoul"}, db_path=db_path)
    assert set(df["city"]) == {"Seoul"}


def test_kpis_agree_with_event_summary(db_path):
    kpi = run_query("kpi_summary", db_path=db_path).iloc[0]
    events = run_query("event_summary", db_path=db_path)
    assert kpi["registrations"] == events["registrations"].sum()
    assert kpi["revenue_aed"] == events["revenue_aed"].sum()


def test_funnel_stages_never_increase(db_path):
    df = run_query("channel_funnel", db_path=db_path)
    assert (df["leads"] >= df["registered"]).all()
    assert (df["registered"] >= df["attended"]).all()


def test_top_countries_returns_at_most_three_per_event(db_path):
    df = run_query("top_countries", db_path=db_path)
    assert df.groupby("event_id").size().max() <= 3


def test_no_query_contains_hardcoded_event_names():
    for path in query_files():
        assert not re.search(r"Congress|Forum|Summit|Symposium", path.read_text())
