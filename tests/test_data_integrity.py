"""Data integrity: the simulated data must never contain impossible values."""

import generate_data
from conftest import scalar


def test_row_counts_in_expected_ranges(con):
    assert scalar(con, "SELECT COUNT(*) FROM events") == 10        # 8 completed, 2 upcoming
    assert 4000 <= scalar(con, "SELECT COUNT(*) FROM registrations") <= 6000
    assert 7000 <= scalar(con, "SELECT COUNT(*) FROM leads") <= 9000


def test_events_span_2025_to_2027(con):
    years = {r[0] for r in con.execute("SELECT DISTINCT substr(start_date, 1, 4) FROM events")}
    assert years == {"2025", "2026", "2027"}


def test_dataset_records_its_source_and_as_of_date(con):
    info = dict(con.execute("SELECT key, value FROM dataset_info").fetchall())
    assert info["source"] == "simulated"
    assert info["as_of_date"] == generate_data.AS_OF.isoformat()


def test_attendance_is_unknown_exactly_for_upcoming_events(con):
    # NULL attended means "not happened yet". It must never appear on a
    # completed event, and an upcoming event must never have 0 or 1.
    assert scalar(con, """
        SELECT COUNT(*) FROM registrations r JOIN events e USING (event_id)
        WHERE (r.attended IS NULL) <> (e.start_date >= (SELECT value FROM dataset_info WHERE key = 'as_of_date'))""") == 0


def test_nothing_happens_after_the_as_of_date(con):
    as_of = generate_data.AS_OF.isoformat()
    assert scalar(con, "SELECT COUNT(*) FROM registrations WHERE registered_on > ?", (as_of,)) == 0
    assert scalar(con, "SELECT COUNT(*) FROM leads WHERE contacted_on > ?", (as_of,)) == 0


def test_sqlite_foreign_key_check_is_clean(con):
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []


def test_no_orphan_registrations(con):
    assert scalar(con, """
        SELECT COUNT(*) FROM registrations r
        LEFT JOIN events e    ON e.event_id    = r.event_id
        LEFT JOIN attendees a ON a.attendee_id = r.attendee_id
        WHERE e.event_id IS NULL OR a.attendee_id IS NULL""") == 0


def test_no_orphan_leads_or_feedback(con):
    assert scalar(con, """
        SELECT COUNT(*) FROM leads l LEFT JOIN events e ON e.event_id = l.event_id
        WHERE e.event_id IS NULL""") == 0
    assert scalar(con, """
        SELECT COUNT(*) FROM feedback f
        LEFT JOIN registrations r ON r.registration_id = f.registration_id
        WHERE r.registration_id IS NULL""") == 0


def test_every_attendee_has_a_registration(con):
    assert scalar(con, """
        SELECT COUNT(*) FROM attendees a
        WHERE NOT EXISTS (SELECT 1 FROM registrations r WHERE r.attendee_id = a.attendee_id)""") == 0


def test_attended_is_binary_or_unknown(con):
    assert scalar(con, "SELECT COUNT(*) FROM registrations WHERE attended IS NOT NULL AND attended NOT IN (0, 1)") == 0


def test_no_attendance_evidence_without_registration(con):
    # Attendance only exists as a flag on a registration, and feedback
    # (the only other proof of attendance) must point at an attended ticket.
    assert scalar(con, """
        SELECT COUNT(*) FROM feedback f
        JOIN registrations r ON r.registration_id = f.registration_id
        WHERE r.attended = 0""") == 0


def test_no_registration_on_or_after_event_date(con):
    assert scalar(con, """
        SELECT COUNT(*) FROM registrations r JOIN events e ON e.event_id = r.event_id
        WHERE r.registered_on >= e.start_date""") == 0


def test_one_ticket_per_person_per_event(con):
    assert scalar(con, """
        SELECT COUNT(*) FROM (SELECT event_id, attendee_id FROM registrations
                              GROUP BY event_id, attendee_id HAVING COUNT(*) > 1)""") == 0


def test_price_paid_matches_ticket_type(con):
    rows = con.execute("""
        SELECT r.ticket_type, r.price_paid, e.base_ticket_price
        FROM registrations r JOIN events e ON e.event_id = r.event_id""").fetchall()
    bad = [r for r in rows
           if r[1] != round(r[2] * generate_data.PRICE_MULTIPLIER[r[0]])]
    assert bad == []


def test_ticket_type_matches_booking_window(con):
    # Early Bird only > 90 days out, Late only within 30 days.
    assert scalar(con, """
        SELECT COUNT(*) FROM registrations r JOIN events e ON e.event_id = r.event_id
        WHERE (r.ticket_type = 'Early Bird' AND julianday(e.start_date) - julianday(r.registered_on) <= 90)
           OR (r.ticket_type = 'Late'       AND julianday(e.start_date) - julianday(r.registered_on) > 30)""") == 0


def test_student_tickets_only_for_students(con):
    assert scalar(con, """
        SELECT COUNT(*) FROM registrations r JOIN attendees a ON a.attendee_id = r.attendee_id
        WHERE (r.ticket_type = 'Student') <> (a.profession = 'Student')""") == 0


def test_registered_first_date_is_earliest_registration(con):
    assert scalar(con, """
        SELECT COUNT(*) FROM attendees a
        JOIN (SELECT attendee_id, MIN(registered_on) AS first_reg
              FROM registrations GROUP BY attendee_id) f USING (attendee_id)
        WHERE a.registered_first_date <> f.first_reg""") == 0


def test_lead_contacted_before_registration_window_closes(con):
    assert scalar(con, """
        SELECT COUNT(*) FROM leads l JOIN events e ON e.event_id = l.event_id
        WHERE l.contacted_on >= e.start_date""") == 0


def test_registered_leads_match_registrations_per_channel(con):
    rows = con.execute("""
        SELECT l.channel, l.n, r.n FROM
          (SELECT channel, COUNT(*) n FROM leads WHERE outcome = 'Registered' GROUP BY channel) l
        JOIN (SELECT channel, COUNT(*) n FROM registrations GROUP BY channel) r USING (channel)""").fetchall()
    assert rows and all(lead_n == reg_n for _, lead_n, reg_n in rows)


def test_ratings_in_range(con):
    assert scalar(con, "SELECT COUNT(*) FROM feedback WHERE rating NOT BETWEEN 1 AND 5") == 0


def test_generation_is_reproducible(tmp_path, db_path):
    import sqlite3
    other = tmp_path / "again.db"
    generate_data.generate(other, generate_data.DEFAULT_SEED)
    sql = "SELECT * FROM registrations ORDER BY registration_id"
    a = sqlite3.connect(db_path).execute(sql).fetchall()
    b = sqlite3.connect(other).execute(sql).fetchall()
    assert a == b
