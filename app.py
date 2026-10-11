"""Events Analytics: concept demo.

Simulated data. Concept demo, not real company data.

Run with:  streamlit run app.py

This file is the shell around every page: it loads the stylesheet, builds the
database on first run if needed, draws the sidebar filters (so they persist
across pages), shows the simulated-data notice, and then runs the page the
viewer picked.
"""

import streamlit as st

from lib import ui

st.set_page_config(
    page_title="Events Analytics: concept demo",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui.load_css()
ui.ensure_database()

pages = [
    st.Page("views/1_overview.py", title="Overview", default=True),
    st.Page("views/2_marketing_funnel.py", title="Marketing Funnel"),
    st.Page("views/3_event_deep_dive.py", title="Event Deep-Dive"),
    st.Page("views/4_query_explorer.py", title="Query Explorer"),
]
current = st.navigation(pages, position="sidebar")

st.session_state["filters"] = ui.sidebar_filters()
ui.frame_top()
ui.notice_banner()
current.run()
ui.frame_bottom(current.title)
