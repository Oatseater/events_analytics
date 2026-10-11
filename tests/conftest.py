"""Shared fixtures: build a fresh database in a temp folder once per test run."""

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_data  # noqa: E402


@pytest.fixture(scope="session")
def db_path(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("data") / "events.db"
    generate_data.generate(path, generate_data.DEFAULT_SEED)
    return path


@pytest.fixture()
def con(db_path):
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


def scalar(con, sql, params=()):
    return con.execute(sql, params).fetchone()[0]
