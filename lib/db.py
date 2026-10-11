"""Load and run the .sql files in queries/.

This module has no Streamlit dependency, so the app, the tests and
make_brief.py all run the exact same SQL through the same function.

Which database? By default data/events.db (the simulated demo). Set the
EVENTS_DB environment variable to point the whole project at another file,
for example one built from real exports with load_csv.py.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "data" / "events.db"
DB_PATH = DEFAULT_DB_PATH          # kept for backward compatibility; use db_path()
QUERY_DIR = ROOT / "queries"

# Every query accepts these three named parameters. None means "no filter".
EMPTY_FILTERS = {"event_id": None, "city": None, "speciality": None}


def db_path() -> Path:
    """The database in use: $EVENTS_DB if set, otherwise the demo database."""
    configured = os.environ.get("EVENTS_DB")
    return Path(configured).expanduser() if configured else DEFAULT_DB_PATH


def is_configured() -> bool:
    """True when someone pointed the project at a specific database on purpose."""
    return bool(os.environ.get("EVENTS_DB"))


def query_files() -> list[Path]:
    """All query files in run order (01_..., 02_..., ...)."""
    return sorted(QUERY_DIR.glob("*.sql"))


def query_path(name: str) -> Path:
    """Find a query by its stem without the number, e.g. 'event_summary'."""
    for path in query_files():
        if path.stem == name or path.stem.split("_", 1)[1] == name:
            return path
    raise FileNotFoundError(f"No query called {name!r} in {QUERY_DIR}")


def read_sql(name: str) -> str:
    return query_path(name).read_text(encoding="utf-8")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open the database read-only.

    The file is opened through a proper file: URI built by pathlib, which
    percent-encodes characters such as '#', '?', '%' and spaces. Building the
    URI by hand ("file:" + path) broke on folders like "Projects #2".
    """
    path = Path(path) if path is not None else db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python generate_data.py` for the demo, "
            "or build one from your exports with `python load_csv.py`."
        )
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def run_query(name: str, filters: dict | None = None, db_path: Path | str | None = None) -> pd.DataFrame:
    """Run queries/<nn>_<name>.sql with the given filters and return a DataFrame."""
    params = {**EMPTY_FILTERS, **(filters or {})}
    con = connect(db_path)
    try:
        return pd.read_sql_query(read_sql(name), con, params=params)
    finally:
        con.close()


def dataset_info(path: Path | str | None = None) -> dict[str, str]:
    """Where the data came from and the as-of date, from the dataset_info table."""
    con = connect(path)
    try:
        return dict(con.execute("SELECT key, value FROM dataset_info").fetchall())
    except sqlite3.OperationalError:
        return {"source": "unknown"}          # a database built before dataset_info existed
    finally:
        con.close()


def header_comment(name: str) -> str:
    """The leading -- comment block of a query file, without the dashes."""
    lines = []
    for line in read_sql(name).splitlines():
        if not line.startswith("--"):
            break
        lines.append(line[2:].strip())
    return "\n".join(lines)
