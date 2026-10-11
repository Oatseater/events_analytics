"""The findings brief is generated, current, and consistent with the queries."""

import re
from pathlib import Path

import make_brief
from lib import db
from lib import theme as t

ROOT = Path(__file__).resolve().parent.parent
NOTICE = "Simulated data. Concept demo, not real company data."
# Emoji and pictograph blocks, built from code points so this file stays plain ASCII.
EMOJI = re.compile("[%s-%s%s-%s%s]" % (chr(0x1F000), chr(0x1FAFF), chr(0x2600), chr(0x27BF), chr(0xFE0F)))


def test_brief_contains_notice_and_three_findings(db_path):
    text = make_brief.build_brief(db_path)
    assert NOTICE in text
    assert len(re.findall(r"^### \d\. ", text, flags=re.M)) == 3


def test_committed_brief_is_up_to_date(db_path):
    # Same seed -> same database -> the committed file must match exactly.
    committed = (ROOT / "findings_brief.md").read_text(encoding="utf-8")
    assert committed == make_brief.build_brief(db_path)


def test_brief_numbers_come_from_queries(db_path):
    text = make_brief.build_brief(db_path)
    funnel = db.run_query("channel_funnel", db_path=db_path)
    assert t.fmt_pct(funnel["attendance_rate_pct"].max()) in text
    assert t.fmt_pct(funnel["attendance_rate_pct"].min()) in text
    be = db.run_query("break_even", db_path=db_path)
    below = be[be["status"] == "Below break-even"].iloc[0]
    assert below["event_name"] in text
    assert t.fmt_int(below["breakeven_tickets"]) in text


def test_no_emoji_in_ui_readme_or_brief():
    files = [ROOT / "README.md", ROOT / "findings_brief.md", ROOT / "app.py",
             *ROOT.glob("views/*.py"), *ROOT.glob("lib/*.py"), ROOT / "assets" / "style.css"]
    for f in files:
        if f.exists():
            assert not EMOJI.search(f.read_text(encoding="utf-8")), f"emoji in {f.name}"
