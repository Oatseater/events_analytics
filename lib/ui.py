"""Streamlit building blocks shared by every page: CSS, the corner frame,
the data-source note, sidebar filters, headline numbers, chart cards, tables,
and the one personal line."""

from __future__ import annotations

import html
import math
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from lib import db, theme

ROOT = Path(__file__).resolve().parent.parent
NOTICE = "Simulated data. Concept demo, not real company data."

# ---- data access -------------------------------------------------------------

def ensure_database() -> None:
    """Make sure there is a database to read.

    The demo database is generated on first run if it is missing. A database
    someone configured on purpose (EVENTS_DB) is never replaced: if it is
    missing we stop and say so, rather than quietly showing invented data.
    """
    path = db.db_path()
    if path.exists():
        return
    if db.is_configured():
        st.error(
            f"The database set in EVENTS_DB was not found: {path}. "
            "Nothing is shown, so that no substitute figures are mistaken for yours. "
            "Check the path, or rebuild it with load_csv.py."
        )
        st.stop()
    import generate_data
    with st.spinner("Generating the simulated demo database (first run only)..."):
        generate_data.generate(path)


def _file_key() -> tuple[str, float]:
    path = db.db_path()
    return str(path.resolve()), path.stat().st_mtime


@st.cache_data(show_spinner=False)
def _cached_query(name: str, params: tuple, file_key: tuple) -> pd.DataFrame:
    return db.run_query(name, dict(params), db_path=file_key[0])


def q(name: str, filters: dict | None = None) -> pd.DataFrame:
    """Run a queries/*.sql file. Cached until the database file changes."""
    params = {**db.EMPTY_FILTERS, **(filters or {})}
    return _cached_query(name, tuple(sorted(params.items())), _file_key()).copy()


@st.cache_data(show_spinner=False)
def _cached_info(file_key: tuple) -> dict:
    return db.dataset_info(file_key[0])


def info() -> dict:
    """dataset_info for the database in use: source, source_name, as_of_date."""
    return _cached_info(_file_key())


def is_simulated() -> bool:
    return info().get("source") == "simulated"


def as_of_label() -> str:
    raw = info().get("as_of_date")
    return date.fromisoformat(raw).strftime("%d %b %Y").lstrip("0") if raw else "an unknown date"


def source_label() -> str:
    """Short label for the corner frame: what kind of data this is."""
    return {"simulated": "Simulated data", "loaded": "Loaded data"}.get(info().get("source"), "Unverified data")


# ---- page chrome ---------------------------------------------------------------

def load_css() -> None:
    css = (ROOT / "assets" / "style.css").read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")


def frame_top() -> None:
    """Wordmark on the left, what kind of data this is on the right."""
    st.html(
        '<div class="ea-frame"><span class="ea-frame__mark">Events Analytics</span>'
        f'<span class="ea-frame__kind">{html.escape(source_label().lower())}</span></div>'
    )


def frame_bottom(page_title: str) -> None:
    """Nothing at the foot of the page: the note at the top and the sidebar say
    where the data comes from. Kept as a hook so app.py does not change."""


def source_sentence() -> str:
    """One true sentence about where the figures come from."""
    i = info()
    if i.get("source") == "simulated":
        return f"{NOTICE} Snapshot as of {as_of_label()}."
    if i.get("source") == "loaded":
        built = i.get("built_at")
        built = date.fromisoformat(built).strftime("%d %b %Y").lstrip("0") if built else "an unknown date"
        return (f"Loaded from {i.get('source_name', 'an unnamed export')} on {built}. "
                f"Figures describe {as_of_label()}.")
    return ("This database has no record of where its data came from. "
            "Treat the figures as unverified until it is rebuilt with load_csv.py.")


def notice_banner() -> None:
    if is_simulated():
        text = (f"{NOTICE} All names, figures and patterns are invented for illustration. "
                f"Snapshot as of {as_of_label()}.")
    else:
        text = source_sentence()
    st.html(
        '<div class="ea-notice" role="note">'
        '<span class="ea-notice__tag">Note</span>'
        f"<span>{html.escape(text)}</span></div>"
    )


def page_header(title: str, subtitle: str, filters: dict | None = None) -> None:
    """Title block on the left, a data stamp on the right (like a film label)."""
    stamp = ""
    if filters is not None:
        scoped = q("event_summary", filters)
        if not scoped.empty:
            first = date.fromisoformat(scoped["start_date"].min()).strftime("%b %Y")
            last = date.fromisoformat(scoped["start_date"].max()).strftime("%b %Y")
            n = len(scoped)
            stamp = (f'<div class="ea-page-head__stamp">{n} event{"s" if n != 1 else ""}'
                     f"<br>{first if first == last else first + ' to ' + last}</div>")
    scope = filter_summary(filters).lower() if filters is not None else ""
    scope_line = f'<div class="ea-annot">scope: {html.escape(scope)}</div>' if scope else ""
    st.html(
        f'<div class="ea-page-head"><div class="ea-page-head__main">{scope_line}'
        f"<h1>{html.escape(title)}</h1>{f'<p>{html.escape(subtitle)}</p>' if subtitle else ''}</div>{stamp}</div>"
    )


# ---- filters -------------------------------------------------------------------

ALL = "All"
ALL_EVENTS = 0          # event ids start at 1, so 0 safely means "all events"
_FILTER_KEYS = ("f_city", "f_speciality", "f_event")


def _clear_filters() -> None:
    st.session_state["f_city"] = ALL
    st.session_state["f_speciality"] = ALL
    st.session_state["f_event"] = ALL_EVENTS


def sidebar_filters() -> dict:
    """Cascading city -> speciality -> event filters. Rendered from app.py on
    every page, so the selection carries across pages."""
    catalogue = q("event_summary")  # unfiltered list of events, from query 01
    for key, default in zip(_FILTER_KEYS, (ALL, ALL, ALL_EVENTS)):
        st.session_state.setdefault(key, default)

    with st.sidebar:
        st.html('<div class="ea-section ea-section--side"><span>Filters</span><i></i></div>')

        cities = [ALL] + sorted(catalogue["city"].unique())
        if st.session_state["f_city"] not in cities:
            st.session_state["f_city"] = ALL
        city = st.selectbox("City", cities, key="f_city")

        in_city = catalogue if city == ALL else catalogue[catalogue["city"] == city]
        specs = [ALL] + sorted(in_city["speciality"].unique())
        if st.session_state["f_speciality"] not in specs:
            st.session_state["f_speciality"] = ALL
        spec = st.selectbox("Speciality", specs, key="f_speciality")

        in_scope = in_city if spec == ALL else in_city[in_city["speciality"] == spec]
        names = {int(e): n for e, n in zip(in_scope["event_id"], in_scope["event_name"])}
        options = [ALL_EVENTS] + list(names)
        if st.session_state["f_event"] not in options:
            st.session_state["f_event"] = ALL_EVENTS
        event = st.selectbox("Event", options, key="f_event",
                             format_func=lambda e: "All events" if e == ALL_EVENTS else names[e])

        n = len(in_scope) if event == ALL_EVENTS else 1
        st.html(f'<div class="ea-side-note">{n} of {len(catalogue)} events in view</div>')
        st.button("Clear filters", on_click=_clear_filters, width="stretch")
        st.html(f'<div class="ea-side-notice">{html.escape(source_sentence())}</div>')

    return {
        "event_id": None if event == ALL_EVENTS else event,
        "city": None if city == ALL else city,
        "speciality": None if spec == ALL else spec,
    }


def get_filters() -> dict:
    return st.session_state.get("filters", dict(db.EMPTY_FILTERS))


def filter_summary(filters: dict) -> str:
    parts = []
    if filters.get("city"):
        parts.append(filters["city"])
    if filters.get("speciality"):
        parts.append(filters["speciality"])
    if filters.get("event_id") is not None:
        names = q("event_summary").set_index("event_id")["event_name"]
        parts.append(names.get(filters["event_id"], ""))
    return ", ".join(parts) if parts else "All events"


# ---- components ----------------------------------------------------------------

def kpi_row(tiles: list[dict]) -> None:
    """tiles: [{label, value, sub, alert}]. A newline in value stacks it.
    An alert number is drawn in polished silver with a short rule; no colour."""
    cells = []
    for t in tiles:
        cls = "ea-kpi is-alert" if t.get("alert") else "ea-kpi"
        value = html.escape(t["value"]).replace("\n", "<br>")
        cells.append(
            f'<div class="{cls}"><div class="ea-kpi__label">{html.escape(t["label"])}</div>'
            f'<div class="ea-kpi__value">{value}</div>'
            f'<div class="ea-kpi__sub">{html.escape(t.get("sub", ""))}</div></div>'
        )
    st.html(f'<div class="ea-kpis">{"".join(cells)}</div>')


def _source(source: str | None) -> str:
    """Where the numbers came from, as a quiet line under the chart."""
    if not source:
        return ""
    files = ", ".join(f"queries/{f.strip()}" for f in source.split(","))
    return f'<div class="ea-source">source: {html.escape(files)}</div>'


def chart_head(title: str, subtitle: str) -> None:
    st.html(f'<div class="ea-chart-head"><h3>{html.escape(title)}</h3><p>{html.escape(subtitle)}</p></div>')


def chart_card(title: str, subtitle: str, fig, takeaway: str | None = None, source: str | None = None) -> None:
    chart_head(title, subtitle)
    # Streamlit fills unset background fields from its own theme, so set them
    # explicitly: transparent, so the film grain shows through every chart.
    fig.update_layout(template="events_analytics",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch", config=theme.PLOTLY_CONFIG, theme=None)
    below = (f'<div class="ea-takeaway">{html.escape(takeaway)}</div>' if takeaway else "") + _source(source)
    if below:
        st.html(below)


def aside(text: str) -> None:
    """The one personal line, in serif italic."""
    st.html(f'<div class="ea-aside">{html.escape(text)}</div>')


def section(title: str) -> None:
    st.html(f'<div class="ea-section"><span>{html.escape(title)}</span><i></i></div>')


def _format_cell(col: str, value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if col.endswith("_pct"):
            return f"{value:,.1f}"
        if "rating" in col:
            return f"{value:.2f}"
        if col.endswith("_id") or col in {"country_rank"}:
            return f"{int(value)}"
        if float(value).is_integer():
            return f"{int(value):,}"
        return f"{value:,.1f}"
    return str(value)


def html_table(df: pd.DataFrame, labels: dict | None = None, max_height: int | None = None) -> None:
    labels = labels or {}
    numeric = {c: pd.api.types.is_numeric_dtype(df[c]) for c in df.columns}
    head = "".join(
        f'<th class="{"num" if numeric[c] else ""}">{html.escape(labels.get(c, c))}</th>'
        for c in df.columns
    )
    num_attr = ' class="num"'
    rows = []
    for rec in df.itertuples(index=False):
        cells = "".join(
            f"<td{num_attr if numeric[col] else ''}>{html.escape(_format_cell(col, val))}</td>"
            for col, val in zip(df.columns, rec)
        )
        rows.append(f"<tr>{cells}</tr>")
    style = f' style="max-height:{max_height}px"' if max_height else ""
    st.html(
        f'<div class="ea-table-wrap"{style}><table class="ea-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


PAGE_ROWS = 200


def paged_table(df: pd.DataFrame, key: str, labels: dict | None = None) -> None:
    """Show a large result 200 rows at a time. Rendering tens of thousands of
    rows as one HTML table made a 9.6 MB page; the CSV download has every row."""
    pages = max(1, math.ceil(len(df) / PAGE_ROWS))
    page = 1
    if pages > 1:
        page = st.number_input(f"Page (of {pages:,}, {PAGE_ROWS} rows each)", min_value=1,
                               max_value=pages, value=1, step=1, key=key)
    start = (int(page) - 1) * PAGE_ROWS
    html_table(df.iloc[start:start + PAGE_ROWS], labels=labels, max_height=640)
    if pages > 1:
        st.html(f'<div class="ea-meta">rows {start + 1:,} to {min(start + PAGE_ROWS, len(df)):,} '
                f"of {len(df):,}</div>")


def empty_state(message: str = "Nothing matches these filters. Widen them in the sidebar.") -> None:
    st.html(f'<div class="ea-empty">{html.escape(message)}</div>')
