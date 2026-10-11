-- Events Analytics: concept demo
--
-- Six tables describe a conference organiser's commercial cycle:
--   dataset_info   where the data came from and the date it describes ("as of")
--   events         one row per conference, past or upcoming
--   attendees      one row per person (a person can attend several events)
--   registrations  one row per ticket sold (person x event)
--   leads          one row per outbound sales contact
--   feedback       one row per post-event survey answer (attended tickets only)
--
-- Design rules:
--   * An event is "completed" when its start_date is before the as-of date,
--     otherwise "upcoming". Status is derived, never stored, so it cannot go stale.
--   * attended is NULL until the event has happened. NULL means "not known yet",
--     which SQL aggregates skip, so unsold or future tickets never count as no-shows.
--   * City, speciality, channel, ticket type and feedback theme are open text, so
--     a new city or a new channel can be loaded without changing this file.
--     Values that have a fixed meaning (attended, rating, lead outcome) stay checked.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS feedback;
DROP TABLE IF EXISTS leads;
DROP TABLE IF EXISTS registrations;
DROP TABLE IF EXISTS attendees;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS dataset_info;

CREATE TABLE dataset_info (
    key   TEXT PRIMARY KEY,            -- source, source_name, as_of_date, built_at
    value TEXT NOT NULL
);

CREATE TABLE events (
    event_id            INTEGER PRIMARY KEY,
    name                TEXT    NOT NULL UNIQUE,
    speciality          TEXT    NOT NULL,
    city                TEXT    NOT NULL,
    start_date          TEXT    NOT NULL CHECK (start_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    capacity            INTEGER NOT NULL CHECK (capacity > 0),
    base_ticket_price   INTEGER NOT NULL CHECK (base_ticket_price > 0),     -- AED
    fixed_cost          INTEGER NOT NULL CHECK (fixed_cost > 0),            -- AED
    sponsorship_revenue INTEGER CHECK (sponsorship_revenue >= 0)            -- AED; NULL = not recorded
);

CREATE TABLE attendees (
    attendee_id           INTEGER PRIMARY KEY,
    country               TEXT NOT NULL,
    profession            TEXT NOT NULL,
    registered_first_date TEXT NOT NULL                       -- earliest registered_on for this person
);

CREATE TABLE registrations (
    registration_id INTEGER PRIMARY KEY,
    event_id        INTEGER NOT NULL REFERENCES events (event_id),
    attendee_id     INTEGER NOT NULL REFERENCES attendees (attendee_id),
    registered_on   TEXT    NOT NULL CHECK (registered_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    ticket_type     TEXT    NOT NULL,
    price_paid      INTEGER NOT NULL CHECK (price_paid >= 0),  -- AED; 0 allows complimentary tickets
    channel         TEXT    NOT NULL,                          -- e.g. Email, WhatsApp, Website
    attended        INTEGER CHECK (attended IN (0, 1)),        -- NULL until the event has happened
    UNIQUE (event_id, attendee_id)                             -- one ticket per person per event
);

CREATE TABLE leads (
    lead_id      INTEGER PRIMARY KEY,
    event_id     INTEGER NOT NULL REFERENCES events (event_id),
    contacted_on TEXT    NOT NULL,
    channel      TEXT    NOT NULL,
    outcome      TEXT    NOT NULL CHECK (outcome IN
                     ('Registered', 'Interested', 'No Answer', 'Declined')),
    follow_ups   INTEGER NOT NULL CHECK (follow_ups >= 0)
);

CREATE TABLE feedback (
    feedback_id     INTEGER PRIMARY KEY,
    registration_id INTEGER NOT NULL UNIQUE REFERENCES registrations (registration_id),
    rating          INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment_theme   TEXT    NOT NULL
);

-- Indexes on the columns the analysis joins and groups by.
CREATE INDEX idx_registrations_event    ON registrations (event_id);
CREATE INDEX idx_registrations_attendee ON registrations (attendee_id);
CREATE INDEX idx_registrations_channel  ON registrations (channel);
CREATE INDEX idx_registrations_date     ON registrations (registered_on);
CREATE INDEX idx_leads_event            ON leads (event_id);
CREATE INDEX idx_leads_channel          ON leads (channel);
CREATE INDEX idx_events_city            ON events (city);
CREATE INDEX idx_events_start           ON events (start_date);
