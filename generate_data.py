"""Generate the simulated Events Analytics database.

Simulated data. Concept demo, not real company data.

Usage:
    python generate_data.py                     # writes data/events.db
    python generate_data.py --db path/to.db     # custom location
    python generate_data.py --seed 7            # different (still reproducible) world
    python generate_data.py --force             # overwrite a database that holds loaded (real) data

Uses only the Python standard library, so it runs before any pip install.
Everything is driven by one seeded random generator, so the same seed always
produces exactly the same database.
"""

from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "db" / "schema.sql"
DEFAULT_DB = ROOT / "data" / "events.db"
DEFAULT_SEED = 2026

# The date this simulated snapshot describes. Events before it are completed;
# events on or after it are upcoming, so their attendance is not known yet.
# Fixed (not "today") so the same seed always builds the same database.
AS_OF = date(2026, 10, 9)

# --------------------------------------------------------------------------
# Event calendar (generic, invented names)
# fill = expected share of capacity sold; fc = fixed cost as a share of
# (capacity x base price), i.e. the budget the organiser planned against.
# --------------------------------------------------------------------------
EVENTS = [
    # name,                                   speciality,        city,        start,        cap,  price, fill, fc
    ("Dental Congress Dubai 2025",            "Dental",          "Dubai",     "2025-02-18", 950, 1400, 0.86, 0.34),
    ("Dermatology Forum Abu Dhabi 2025",      "Dermatology",     "Abu Dhabi", "2025-04-22", 700, 1650, 0.78, 0.36),
    ("Pharmacy Summit Riyadh 2025",           "Pharmacy",        "Riyadh",    "2025-05-13", 650, 1100, 0.82, 0.35),
    ("Family Medicine Conference Dubai 2025", "Family Medicine", "Dubai",     "2025-10-07", 850, 1200, 0.74, 0.33),
    ("Cardiology Congress Seoul 2025",        "Cardiology",      "Seoul",     "2025-11-18", 700, 2100, 0.80, 0.37),
    ("Nursing Symposium Abu Dhabi 2026",      "Nursing",         "Abu Dhabi", "2026-01-27", 750,  900, 0.40, 0.40),
    ("Dental Congress Riyadh 2026",           "Dental",          "Riyadh",    "2026-03-10", 800, 1350, 0.88, 0.35),
    ("Dermatology Forum Dubai 2026",          "Dermatology",     "Dubai",     "2026-09-15", 900, 1750, 0.80, 0.36),
    # Upcoming at the as-of date: one on sale, one announced with no sales yet.
    ("Dental Congress Dubai 2027",            "Dental",          "Dubai",     "2027-02-16", 950, 1450, 0.84, 0.34),
    ("Cardiology Congress Seoul 2027",        "Cardiology",      "Seoul",     "2027-06-15", 700, 2150, 0.80, 0.37),
]

CHANNELS = ["Email", "WhatsApp", "Social", "Partner Referral", "Cold Call"]
THEMES = ["Content", "Venue", "Networking", "Pricing", "Organisation"]

# Price paid = base ticket price x multiplier. Tests check this exactly.
PRICE_MULTIPLIER = {"Early Bird": 0.80, "Standard": 1.00, "Late": 1.20, "Student": 0.50}

CHANNEL_MIX = {
    "default": {"Email": 0.30, "WhatsApp": 0.21, "Social": 0.18, "Partner Referral": 0.15, "Cold Call": 0.16},
    "Riyadh":  {"Email": 0.24, "WhatsApp": 0.28, "Social": 0.17, "Partner Referral": 0.14, "Cold Call": 0.17},
    "Seoul":   {"Email": 0.36, "WhatsApp": 0.10, "Social": 0.18, "Partner Referral": 0.20, "Cold Call": 0.16},
}

COUNTRY_MIX = {
    "Dubai": {"United Arab Emirates": 30, "India": 14, "Saudi Arabia": 10, "Egypt": 10, "Pakistan": 7,
              "Philippines": 6, "Jordan": 6, "Lebanon": 5, "Oman": 4, "Kuwait": 4, "United Kingdom": 4},
    "Abu Dhabi": {"United Arab Emirates": 38, "India": 13, "Egypt": 11, "Saudi Arabia": 8, "Pakistan": 7,
                  "Philippines": 7, "Jordan": 6, "Oman": 5, "Lebanon": 5},
    "Riyadh": {"Saudi Arabia": 52, "Egypt": 12, "United Arab Emirates": 8, "Jordan": 7, "India": 6,
               "Pakistan": 6, "Bahrain": 5, "Kuwait": 4},
    "Seoul": {"South Korea": 62, "Japan": 9, "China": 8, "Vietnam": 5, "Philippines": 5, "India": 4,
              "United Arab Emirates": 4, "Singapore": 3},
}

PROFESSIONS = {
    "Dental": ["Dentist", "Dentist", "Orthodontist", "Dental Hygienist"],
    "Dermatology": ["Dermatologist", "Dermatologist", "Aesthetic Physician", "General Practitioner"],
    "Pharmacy": ["Pharmacist", "Pharmacist", "Clinical Pharmacist", "Pharma Industry"],
    "Family Medicine": ["Family Physician", "Family Physician", "General Practitioner", "Nurse"],
    "Cardiology": ["Cardiologist", "Cardiologist", "Internal Medicine Physician", "Cardiac Nurse"],
    "Nursing": ["Nurse", "Nurse", "Nurse Manager", "Nurse Educator"],
}
STUDENT_SHARE = 0.09
REPEAT_ATTENDEE_SHARE = 0.12

# --- Behavioural levers ---------------------------------------------------
BASE_ATTENDANCE = 0.78
CHANNEL_ATTENDANCE = {"WhatsApp": +0.08, "Partner Referral": +0.04, "Email": 0.00,
                      "Social": -0.04, "Cold Call": -0.14}
TICKET_ATTENDANCE = {"Early Bird": +0.08, "Standard": 0.00, "Student": -0.03, "Late": -0.13}

# Share of each channel's leads that end up registering.
LEAD_CONVERSION = {"Email": 0.62, "WhatsApp": 0.68, "Social": 0.55,
                   "Partner Referral": 0.75, "Cold Call": 0.38}

FEEDBACK_RESPONSE_RATE = 0.55
THEME_WEIGHTS = {  # Content, Venue, Networking, Pricing, Organisation
    "Early Bird": [0.32, 0.18, 0.22, 0.10, 0.18],
    "Standard":   [0.26, 0.14, 0.16, 0.30, 0.14],
    "Late":       [0.25, 0.18, 0.14, 0.15, 0.28],
    "Student":    [0.22, 0.14, 0.16, 0.34, 0.14],
}
THEME_RATING_SHIFT = {"Content": +0.15, "Venue": 0.0, "Networking": +0.10,
                      "Pricing": -0.70, "Organisation": -0.20}


def weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def sample_lead_days(rng: random.Random, city: str) -> int:
    """Days between registration and event start (always >= 1).

    Most cities sell steadily across the six-month window. Riyadh buyers
    leave it late, so Riyadh's monthly volumes climb much more steeply.
    """
    if city == "Riyadh":
        early, mid = 0.12, 0.33
    else:
        early, mid = 0.30, 0.42
    u = rng.random()
    if u < early:
        return rng.randint(91, 170)
    if u < early + mid:
        return rng.randint(31, 90)
    # Late window: skewed toward the final days before the event.
    return max(1, int(30 - rng.triangular(0, 29, 6)))


def ticket_for(lead_days: int, is_student: bool) -> str:
    if is_student:
        return "Student"
    if lead_days > 90:
        return "Early Bird"
    if lead_days > 30:
        return "Standard"
    return "Late"


def existing_source(db_path: Path) -> str | None:
    """'simulated', 'loaded', or None if there is no readable database there."""
    if not Path(db_path).exists():
        return None
    try:
        con = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
        try:
            row = con.execute("SELECT value FROM dataset_info WHERE key = 'source'").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return "unknown"          # an older or foreign file: treat as precious
    return row[0] if row else "unknown"


def generate(db_path: Path = DEFAULT_DB, seed: int = DEFAULT_SEED, force: bool = False) -> dict[str, int]:
    source = existing_source(db_path)
    if source not in (None, "simulated") and not force:
        raise RuntimeError(
            f"{db_path} holds {source} data, not simulated data. Refusing to overwrite it. "
            "Pass --force (or force=True) if you really want to replace it."
        )
    rng = random.Random(seed)

    events, attendees, registrations, leads, feedback = [], [], [], [], []
    attendee_pool: list[int] = []          # attendee ids, for repeat visitors

    for event_id, (name, spec, city, start, cap, price, fill, fc_share) in enumerate(EVENTS, start=1):
        start_date = date.fromisoformat(start)
        fixed_cost = int(round(cap * price * fc_share * rng.uniform(0.97, 1.03), -3))
        # Sponsorship is not simulated: NULL means "not recorded", never zero.
        events.append((event_id, name, spec, city, start, cap, price, fixed_cost, None))
        upcoming = start_date >= AS_OF

        n_regs = min(cap, round(cap * fill * rng.uniform(0.96, 1.04)))
        event_attendance_shift = rng.uniform(-0.03, 0.03)
        event_rating_shift = rng.uniform(-0.25, 0.25) - (0.2 if fill < 0.5 else 0.0)
        mix = CHANNEL_MIX.get(city, CHANNEL_MIX["default"])
        seen_here: set[int] = set()
        regs_by_channel = {c: 0 for c in CHANNELS}

        for _ in range(n_regs):
            # Pick the person: mostly new, sometimes someone from an earlier event.
            # (Chosen before the sale date is known, so the random stream for
            # completed events is the same as before upcoming events existed.)
            attendee_id = None
            new_person = False
            if attendee_pool and rng.random() < REPEAT_ATTENDEE_SHARE:
                for _try in range(5):
                    candidate = attendee_pool[rng.randrange(len(attendee_pool))]
                    if candidate not in seen_here:
                        attendee_id = candidate
                        break
            if attendee_id is None:
                attendee_id = len(attendees) + 1
                is_student = rng.random() < STUDENT_SHARE
                profession = "Student" if is_student else rng.choice(PROFESSIONS[spec])
                country = weighted_choice(rng, COUNTRY_MIX[city])
                attendees.append([attendee_id, country, profession, None])
                attendee_pool.append(attendee_id)
                new_person = True
            seen_here.add(attendee_id)
            is_student = attendees[attendee_id - 1][2] == "Student"

            lead_days = sample_lead_days(rng, city)
            registered_on = start_date - timedelta(days=lead_days)
            if registered_on > AS_OF:
                # This sale has not happened yet at the as-of date: undo the
                # person we just created, so nobody exists without a ticket.
                # (Only upcoming events reach this line, so completed events
                # draw exactly the same random numbers as before.)
                seen_here.discard(attendee_id)
                if new_person:
                    attendees.pop()
                    attendee_pool.pop()
                continue
            ticket = ticket_for(lead_days, is_student)
            price_paid = int(round(price * PRICE_MULTIPLIER[ticket]))
            channel = weighted_choice(rng, mix)
            regs_by_channel[channel] += 1

            p_attend = (BASE_ATTENDANCE + event_attendance_shift
                        + CHANNEL_ATTENDANCE[channel] + TICKET_ATTENDANCE[ticket])
            attended = int(rng.random() < min(0.97, max(0.05, p_attend)))
            if upcoming:
                attended = None   # unknown until the event happens

            registrations.append([None, event_id, attendee_id, registered_on, ticket,
                                  price_paid, channel, attended, event_rating_shift])

            # Every registration traces back to the lead that produced it.
            contacted_on = registered_on - timedelta(days=rng.randint(0, 14))
            follow_ups = {"WhatsApp": rng.randint(1, 3), "Cold Call": rng.randint(1, 4),
                          "Email": rng.randint(0, 2), "Social": rng.randint(0, 1),
                          "Partner Referral": rng.randint(0, 2)}[channel]
            leads.append([None, event_id, contacted_on, channel, "Registered", follow_ups])

        # Leads that did not convert, sized from each channel's conversion rate.
        for channel in CHANNELS:
            conv = LEAD_CONVERSION[channel]
            n_lost = round(regs_by_channel[channel] * (1 / conv - 1) * rng.uniform(0.9, 1.1))
            for _ in range(n_lost):
                if channel == "Cold Call":
                    outcome = weighted_choice(rng, {"No Answer": 0.50, "Declined": 0.30, "Interested": 0.20})
                else:
                    outcome = weighted_choice(rng, {"Interested": 0.45, "No Answer": 0.30, "Declined": 0.25})
                contacted_on = start_date - timedelta(days=rng.randint(1, 175))
                follow_ups = rng.randint(0, 3)
                if contacted_on <= AS_OF:
                    leads.append([None, event_id, contacted_on, channel, outcome, follow_ups])

    # Assign ids in date order, as an operational system would.
    registrations.sort(key=lambda r: (r[3], r[1], r[2]))
    for i, r in enumerate(registrations, start=1):
        r[0] = i
    leads.sort(key=lambda l: (l[2], l[1], l[3]))
    for i, l in enumerate(leads, start=1):
        l[0] = i

    # First registration date per attendee.
    first_seen: dict[int, date] = {}
    for r in registrations:
        if r[2] not in first_seen or r[3] < first_seen[r[2]]:
            first_seen[r[2]] = r[3]
    for a in attendees:
        a[3] = first_seen[a[0]].isoformat()

    # Post-event survey: only people who attended can answer.
    for r in registrations:
        reg_id, ticket, attended, rating_shift = r[0], r[4], r[7], r[8]
        if not attended or rng.random() > FEEDBACK_RESPONSE_RATE:
            continue
        theme = rng.choices(THEMES, weights=THEME_WEIGHTS[ticket], k=1)[0]
        score = (4.05 + rating_shift + THEME_RATING_SHIFT[theme]
                 - (0.10 if ticket == "Late" else 0.0) + rng.gauss(0, 0.85))
        rating = int(min(5, max(1, round(score))))
        feedback.append((len(feedback) + 1, reg_id, rating, theme))

    # ---- write -----------------------------------------------------------
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        con.executemany("INSERT INTO dataset_info VALUES (?, ?)", [
            ("source", "simulated"),
            ("source_name", f"generate_data.py, seed {seed}"),
            ("as_of_date", AS_OF.isoformat()),
        ])
        con.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)", events)
        con.executemany("INSERT INTO attendees VALUES (?,?,?,?)", [tuple(a) for a in attendees])
        con.executemany(
            "INSERT INTO registrations VALUES (?,?,?,?,?,?,?,?)",
            [(r[0], r[1], r[2], r[3].isoformat(), r[4], r[5], r[6], r[7]) for r in registrations],
        )
        con.executemany(
            "INSERT INTO leads VALUES (?,?,?,?,?,?)",
            [(l[0], l[1], l[2].isoformat(), l[3], l[4], l[5]) for l in leads],
        )
        con.executemany("INSERT INTO feedback VALUES (?,?,?,?)", feedback)
        con.commit()
    finally:
        con.close()

    return {"events": len(events), "attendees": len(attendees), "registrations": len(registrations),
            "leads": len(leads), "feedback": len(feedback)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the simulated Events Analytics database.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="output SQLite file")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed")
    parser.add_argument("--force", action="store_true", help="overwrite a database that holds loaded data")
    args = parser.parse_args()
    try:
        counts = generate(args.db, args.seed, force=args.force)
    except RuntimeError as err:
        raise SystemExit(f"Stopped: {err}")
    print(f"Wrote {args.db} (seed {args.seed}). Simulated data. Concept demo, not real company data.")
    for table, n in counts.items():
        print(f"  {table:<14}{n:>7,}")


if __name__ == "__main__":
    main()
