"""Every dashboard page renders without an exception, unfiltered and filtered,
and shows the simulated-data notice. Uses Streamlit's headless AppTest."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from lib import db

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["views/1_overview.py", "views/2_marketing_funnel.py",
         "views/3_event_deep_dive.py", "views/4_query_explorer.py"]
NOTICE = "Simulated data. Concept demo, not real company data."

pytestmark = pytest.mark.skipif(not db.DB_PATH.exists(),
                                reason="run `python generate_data.py` first")


def _all_text(at: AppTest) -> str:
    parts = [str(getattr(el, "value", "")) for el in at.main] + \
            [str(getattr(el, "value", "")) for el in at.sidebar]
    html = [str(node.proto) for node in at.get("html")]
    return " ".join(parts + html)


def _load(page: str, **filters) -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    for key, value in filters.items():
        at.selectbox(key=key).set_value(value)
        at.run()
    if page != PAGES[0]:
        at.switch_page(page)
        at.run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_loads_without_errors(page):
    at = _load(page)
    assert not at.exception, at.exception
    assert "ea-page-head" in _all_text(at)


def test_notice_rendered_by_app_shell():
    # app.py draws the notice before running whichever page is selected.
    # AppTest only reports the shell's elements on the first run, so we
    # check it there; the browser check in the README covers every page.
    at = _load(PAGES[0])
    assert NOTICE in _all_text(at)


@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("filters", [{"f_city": "Riyadh"}, {"f_speciality": "Dental"}, {"f_event": 6}])
def test_page_loads_with_filters(page, filters):
    at = _load(page, **filters)
    assert not at.exception, at.exception


def test_no_pages_folder():
    # A folder named pages/ makes Streamlit route deep links (e.g. /event_deep_dive
    # on a fresh server) straight to the page script, skipping app.py and with it
    # the stylesheet, the filters and the simulated-data notice. Views live in views/.
    assert not (ROOT / "pages").exists()


def test_filters_persist_across_pages():
    at = _load(PAGES[0], f_city="Dubai")
    at.switch_page(PAGES[1])
    at.run()
    assert at.session_state["filters"]["city"] == "Dubai"
