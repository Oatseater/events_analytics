"""Build an Events Analytics database from your own CSV exports.

    python load_csv.py exports/ --as-of 2026-10-09 --name "CRM export, Oct 2026"
    python load_csv.py --templates templates/      # empty CSVs with the right headers
    python load_csv.py --export-demo demo_csv/     # the simulated data, in this same format

Then point the dashboard at the result:

    EVENTS_DB=data/loaded.db streamlit run app.py        (macOS / Linux)
    set EVENTS_DB=data\\loaded.db && streamlit run app.py (Windows)

Rules this loader keeps:
  * Nothing is written unless every check passes. Problems are listed by file
    and spreadsheet row in a report, so they can be fixed at the source.
  * Nothing is guessed. A date like 03/04/2026 is rejected rather than read as
    March or April; a blank attendance stays unknown rather than becoming 0.
  * The database records where it came from and its as-of date, so the
    dashboard can say so on every page.
  * The demo database is never touched: the default output is data/loaded.db.

Standard library only, like generate_data.py.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "db" / "schema.sql"
DEFAULT_OUT = ROOT / "data" / "loaded.db"

# file -> [(column, kind, required)]. kind: int, money, date, text, attended, rating, outcome
COLUMNS = {
    "events": [("event_id", "int", True), ("name", "text", True), ("speciality", "text", True),
               ("city", "text", True), ("start_date", "date", True), ("capacity", "int", True),
               ("base_ticket_price", "money", True), ("fixed_cost", "money", True),
               ("sponsorship_revenue", "money", False)],
    "attendees": [("attendee_id", "int", True), ("country", "text", True), ("profession", "text", True)],
    "registrations": [("registration_id", "int", True), ("event_id", "int", True), ("attendee_id", "int", True),
                      ("registered_on", "date", True), ("ticket_type", "text", True), ("price_paid", "money", True),
                      ("channel", "text", True), ("attended", "attended", False)],
    "leads": [("lead_id", "int", False), ("event_id", "int", True), ("contacted_on", "date", True),
              ("channel", "text", True), ("outcome", "outcome", True), ("follow_ups", "int", False)],
    "feedback": [("feedback_id", "int", False), ("registration_id", "int", True), ("rating", "rating", True),
                 ("comment_theme", "text", True)],
}
REQUIRED_FILES = ("events", "attendees", "registrations")
OUTCOMES = {"Registered", "Interested", "No Answer", "Declined"}
GUIDE = {
    "event_id": "whole number, unique per event", "name": "unique event name",
    "start_date": "first day of the event, YYYY-MM-DD", "capacity": "seats available",
    "base_ticket_price": "standard ticket price in AED", "fixed_cost": "venue, AV, staff etc. in AED",
    "sponsorship_revenue": "optional, AED; leave blank if not recorded (blank is not zero)",
    "registered_on": "date the ticket was bought, YYYY-MM-DD", "price_paid": "AED actually paid; 0 for complimentary",
    "channel": "any label, e.g. Email, WhatsApp, Website", "ticket_type": "any label, e.g. Early Bird",
    "attended": "1 came, 0 did not come, blank = not known yet (must be blank for upcoming events)",
    "outcome": "one of: " + ", ".join(sorted(OUTCOMES)), "rating": "whole number 1 to 5",
}

MAX_LISTED = 15   # per rule, so a report stays readable when one mistake repeats 5,000 times


class Report:
    def __init__(self) -> None:
        self.errors: dict[str, list[str]] = defaultdict(list)
        self.warnings: dict[str, list[str]] = defaultdict(list)

    def error(self, rule: str, where: str) -> None:
        self.errors[rule].append(where)

    def warn(self, rule: str, where: str) -> None:
        self.warnings[rule].append(where)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self, folder: Path, counts: dict[str, int]) -> str:
        lines = [f"# Load report for {folder}", ""]
        lines.append("Result: **loaded**" if self.ok else "Result: **not loaded**. Nothing was written; fix the errors below and run again.")
        lines += ["", "Rows read: " + ", ".join(f"{k} {v:,}" for k, v in counts.items()), ""]
        for title, group in (("Errors (must fix)", self.errors), ("Warnings (check these; they do not block loading)", self.warnings)):
            if not group:
                continue
            lines += [f"## {title}", ""]
            for rule, places in group.items():
                shown = ", ".join(places[:MAX_LISTED]) + (f" and {len(places) - MAX_LISTED:,} more" if len(places) > MAX_LISTED else "")
                lines.append(f"- {rule} ({len(places):,}): {shown}")
            lines.append("")
        return "\n".join(lines)


def parse(value: str, kind: str):
    """Return the parsed value, or raise ValueError with a plain-English reason."""
    v = value.strip()
    if kind == "text":
        if not v:
            raise ValueError("is empty")
        return v
    if v == "":
        return None
    if kind in ("int", "money", "rating"):
        if re.fullmatch(r"\d{1,3}(,\d{3})+", v):          # 1,234 from a formatted spreadsheet
            v = v.replace(",", "")
        if not re.fullmatch(r"-?\d+", v):
            raise ValueError(f"'{value}' is not a whole number")
        n = int(v)
        if kind == "rating" and not 1 <= n <= 5:
            raise ValueError(f"rating {n} is outside 1 to 5")
        if kind == "money" and n < 0:
            raise ValueError(f"{n} is negative")
        return n
    if kind == "date":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError(f"'{value}' is not YYYY-MM-DD (dates like 03/04/2026 are refused, not guessed)")
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError(f"'{value}' is not a real date") from None
        return v
    if kind == "attended":
        if v not in ("0", "1"):
            raise ValueError(f"'{value}' should be 1, 0 or blank")
        return int(v)
    if kind == "outcome":
        if v not in OUTCOMES:
            raise ValueError(f"'{value}' is not one of {', '.join(sorted(OUTCOMES))}")
        return v
    raise AssertionError(kind)


def read_file(folder: Path, name: str, report: Report) -> list[dict] | None:
    path = folder / f"{name}.csv"
    if not path.exists():
        if name in REQUIRED_FILES:
            report.error("Required file missing", f"{name}.csv")
        return None if name in REQUIRED_FILES else []
    with path.open(newline="", encoding="utf-8-sig") as fh:      # utf-8-sig: Excel's byte-order mark
        reader = csv.DictReader(fh)
        header = [h.strip() for h in (reader.fieldnames or [])]
        spec = COLUMNS[name]
        missing = [c for c, _, req in spec if req and c not in header]
        extra = [h for h in header if h and h not in {c for c, _, _ in spec}]
        if extra:
            report.warn("Columns not used by the dashboard (ignored)", f"{name}.csv: {', '.join(extra)}")
        if missing:
            report.error("Required column missing", f"{name}.csv: {', '.join(missing)}")
            return None
        rows = []
        for line_no, raw in enumerate(reader, start=2):           # row 1 is the header, as in a spreadsheet
            raw = {(k or "").strip(): (v or "") for k, v in raw.items()}
            row, bad = {"_where": f"{name}.csv row {line_no}"}, False
            for col, kind, req in spec:
                try:
                    val = parse(raw.get(col, ""), kind)
                except ValueError as err:
                    report.error(f"{name}.{col}: invalid value", f"row {line_no} ({err})")
                    bad = True
                    continue
                if val is None and req and kind not in ("attended",):
                    report.error(f"{name}.{col}: required value missing", f"row {line_no}")
                    bad = True
                row[col] = val
            if not bad:
                rows.append(row)
        return rows


def validate(data: dict[str, list[dict]], as_of: str, report: Report) -> None:
    def unique(table: str, col: str) -> None:
        seen = set()
        for r in data[table]:
            if r.get(col) is None:
                continue
            if r[col] in seen:
                report.error(f"{table}.{col}: duplicate", r["_where"])
            seen.add(r[col])

    for t, c in [("events", "event_id"), ("events", "name"), ("attendees", "attendee_id"),
                 ("registrations", "registration_id"), ("leads", "lead_id"), ("feedback", "feedback_id"),
                 ("feedback", "registration_id")]:
        unique(t, c)

    events = {r["event_id"]: r for r in data["events"]}
    attendees = {r["attendee_id"] for r in data["attendees"]}
    regs = {r["registration_id"]: r for r in data["registrations"]}

    pair_seen, sold = set(), defaultdict(int)
    for r in data["registrations"]:
        ev = events.get(r["event_id"])
        if ev is None:
            report.error("registrations.event_id: no such event in events.csv", r["_where"])
            continue
        if r["attendee_id"] not in attendees:
            report.error("registrations.attendee_id: no such person in attendees.csv", r["_where"])
        if (r["event_id"], r["attendee_id"]) in pair_seen:
            report.error("Same person registered twice for the same event", r["_where"])
        pair_seen.add((r["event_id"], r["attendee_id"]))
        sold[r["event_id"]] += 1
        if r["registered_on"] >= ev["start_date"]:
            report.error("Ticket bought on or after the event's start date", r["_where"])
        if r["registered_on"] > as_of:
            report.error("Ticket bought after the as-of date (is --as-of right?)", r["_where"])
        upcoming = ev["start_date"] >= as_of
        if upcoming and r.get("attended") is not None:
            report.error("Attendance filled in for an event that has not happened yet", r["_where"])
        if not upcoming and r.get("attended") is None:
            report.warn("No attendance recorded for a completed event (left out of attendance rates, "
                        "not counted as a no-show)", r["_where"])

    for eid, n in sold.items():
        if n > events[eid]["capacity"]:
            report.warn("More tickets sold than capacity", f"event {eid} ({n:,} sold, capacity {events[eid]['capacity']:,})")
    for eid, ev in events.items():
        if eid not in sold:
            report.warn("Event with no tickets sold (shown as 'no sales yet')", ev["_where"])

    for r in data["leads"]:
        if r["event_id"] not in events:
            report.error("leads.event_id: no such event in events.csv", r["_where"])
        elif r["contacted_on"] > as_of:
            report.error("Lead contacted after the as-of date (is --as-of right?)", r["_where"])
    for r in data["feedback"]:
        reg = regs.get(r["registration_id"])
        if reg is None:
            report.error("feedback.registration_id: no such ticket in registrations.csv", r["_where"])
        elif reg.get("attended") != 1:
            report.error("Feedback from a ticket not marked as attended", r["_where"])


def write_db(data: dict[str, list[dict]], out: Path, as_of: str, name: str) -> None:
    """Build into a temporary file next to the target, then swap it in, so a
    failure halfway never leaves a half-written database behind."""
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".db", dir=out.parent)
    os.close(fd)
    try:
        con = sqlite3.connect(tmp)
        con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        first = {}
        for r in sorted(data["registrations"], key=lambda r: r["registered_on"]):
            first.setdefault(r["attendee_id"], r["registered_on"])
        con.executemany("INSERT INTO dataset_info VALUES (?, ?)", [
            ("source", "loaded"), ("source_name", name), ("as_of_date", as_of),
            ("built_at", date.today().isoformat())])
        def rows(table, cols):
            return [tuple(r.get(c) for c in cols) for r in data[table]]
        ev_cols = [c for c, _, _ in COLUMNS["events"]]
        con.executemany(f"INSERT INTO events ({','.join(ev_cols)}) VALUES ({','.join('?' * len(ev_cols))})",
                        rows("events", ev_cols))
        con.executemany("INSERT INTO attendees VALUES (?,?,?,?)",
                        [(r["attendee_id"], r["country"], r["profession"], first.get(r["attendee_id"]))
                         for r in data["attendees"] if r["attendee_id"] in first])
        defaults = {"follow_ups": 0}          # an export without follow-up counts means none recorded
        for table in ("registrations", "leads", "feedback"):
            cols = [c for c, _, _ in COLUMNS[table]]
            con.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                            [tuple(defaults.get(c) if r.get(c) is None else r.get(c) for c in cols)
                             for r in data[table]])
        problems = con.execute("PRAGMA foreign_key_check").fetchall()
        con.commit()
        con.close()
        if problems:
            raise RuntimeError(f"foreign key check failed after load: {problems[:5]}")
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load(folder: Path, out: Path = DEFAULT_OUT, as_of: str | None = None, name: str | None = None) -> tuple[bool, str]:
    """Validate the CSVs in folder and, only if they all pass, write out. Returns (loaded, report)."""
    as_of = as_of or date.today().isoformat()
    parse(as_of, "date")
    report = Report()
    data = {t: read_file(folder, t, report) for t in COLUMNS}
    counts = {t: len(v or []) for t, v in data.items()}
    if all(v is not None for v in data.values()):
        # Check relationships even if some rows failed to parse, so one run
        # lists every problem instead of revealing them one at a time.
        validate(data, as_of, report)
    if report.ok:
        attendees_without_tickets = len({r["attendee_id"] for r in data["attendees"]}
                                        - {r["attendee_id"] for r in data["registrations"]})
        if attendees_without_tickets:
            report.warn("People in attendees.csv with no ticket (not loaded)", f"{attendees_without_tickets:,} people")
        write_db(data, out, as_of, name or folder.name)
    text = report.render(folder, counts)
    return report.ok, text


def write_templates(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    guide = ["# Column guide", "", "Fill one CSV per table, UTF-8, with these headers. Dates are YYYY-MM-DD.", ""]
    for table, spec in COLUMNS.items():
        with (folder / f"{table}.csv").open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow([c for c, _, _ in spec])
        need = "required" if table in REQUIRED_FILES else "optional file"
        guide += [f"## {table}.csv ({need})", ""]
        guide += [f"- `{c}`{'' if req else ' (optional)'}: {GUIDE.get(c, kind)}" for c, kind, req in spec]
        guide.append("")
    (folder / "COLUMNS.md").write_text("\n".join(guide), encoding="utf-8")


def export_demo(folder: Path, db_file: Path) -> str:
    """Write the simulated database out as CSVs in the loader's format."""
    folder.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_file)
    try:
        for table, spec in COLUMNS.items():
            cols = [c for c, _, _ in spec]
            with (folder / f"{table}.csv").open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(cols)
                w.writerows(["" if v is None else v for v in row]
                            for row in con.execute(f"SELECT {','.join(cols)} FROM {table}"))
        return con.execute("SELECT value FROM dataset_info WHERE key = 'as_of_date'").fetchone()[0]
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build an Events Analytics database from CSV exports.")
    ap.add_argument("folder", nargs="?", type=Path, help="folder with events.csv, attendees.csv, registrations.csv ...")
    ap.add_argument("--db", type=Path, default=DEFAULT_OUT, help=f"output database (default {DEFAULT_OUT.relative_to(ROOT)})")
    ap.add_argument("--as-of", help="the date the exports describe, YYYY-MM-DD (default today)")
    ap.add_argument("--name", help="a label for the source, shown on every page")
    ap.add_argument("--templates", type=Path, metavar="FOLDER", help="write empty CSV templates and a column guide")
    ap.add_argument("--export-demo", type=Path, metavar="FOLDER", help="write the simulated demo data as CSVs")
    args = ap.parse_args()

    if args.templates:
        write_templates(args.templates)
        print(f"Wrote templates and COLUMNS.md to {args.templates}")
        return
    if args.export_demo:
        as_of = export_demo(args.export_demo, ROOT / "data" / "events.db")
        print(f"Wrote the simulated demo as CSVs to {args.export_demo} (as of {as_of}). "
              "Simulated data. Concept demo, not real company data.")
        return
    if not args.folder:
        ap.error("give a folder of CSVs, or --templates / --export-demo")
    try:
        ok, text = load(args.folder, args.db, args.as_of, args.name)
    except ValueError as err:
        raise SystemExit(f"Stopped: --as-of {err}")
    report_path = args.db.with_suffix(".load_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nReport saved to {report_path}")
    if ok:
        print(f"Loaded into {args.db}. Start the dashboard with EVENTS_DB={args.db} streamlit run app.py")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
