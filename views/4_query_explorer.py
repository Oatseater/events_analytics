"""Query Explorer: every .sql file beside the exact result it produced."""

import html
import re

import streamlit as st

from lib import db, ui

filters = ui.get_filters()
ui.page_header("Query Explorer", "The SQL behind every number, next to what it returns.", filters)

files = db.query_files()
names = [p.stem.split("_", 1)[1] for p in files]


def title_of(name: str) -> str:
    first = db.header_comment(name).splitlines()[0]          # e.g. "01 Event summary"
    return first


choice = st.selectbox("Query", names, format_func=title_of, key="qx_query")
path = db.query_path(choice)
header = db.header_comment(choice)

# Pull the labelled parts out of the header comment for a readable summary.
FLAT = " ".join(header.split())


def field(label: str) -> str:
    match = re.search(rf"{label}\s*(.*?)(?=Business question:|Technique:|Filters:|$)", FLAT)
    return match.group(1).strip() if match else ""


params = {**db.EMPTY_FILTERS, **filters}
shown = ", ".join(f":{k} = {'NULL (all)' if v is None else repr(v)}" for k, v in params.items())
st.html(
    f'<div class="ea-qmeta"><b>Business question.</b> {html.escape(field("Business question:"))}<br>'
    f'<b>Technique.</b> {html.escape(field("Technique:"))}</div>'
    f'<div class="ea-params">File: queries/{path.name}  |  Parameters from sidebar: {html.escape(shown)}</div>'
)

result = ui.q(choice, filters)
code_col, result_col = st.columns([1, 1], gap="large")
with code_col:
    ui.section(f"sql: {path.name}")
    st.code(path.read_text(encoding="utf-8"), language="sql", line_numbers=True)
with result_col:
    ui.section(f"result: {len(result):,} row{'s' if len(result) != 1 else ''}")
    if result.empty:
        ui.empty_state()
    else:
        ui.paged_table(result, key=f"qx_page_{choice}")
        st.download_button("Download result as CSV", result.to_csv(index=False).encode("utf-8"),
                           file_name=f"{path.stem}.csv", mime="text/csv")
