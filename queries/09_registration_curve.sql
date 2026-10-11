-- 09 Registration curve (supports the Event Deep-Dive page)
-- Business question: How did registrations build up day by day before each
--   event, and how close did they get to capacity?
-- Technique: Count registrations per event per day, then a running total
--   with SUM() OVER (PARTITION BY event ORDER BY day). Days before the event
--   come from julianday() date arithmetic.
-- Filters: :event_id, :city, :speciality (NULL means "all").

WITH scope AS (
    SELECT event_id
    FROM events
    WHERE (:event_id   IS NULL OR event_id   = :event_id)
      AND (:city       IS NULL OR city       = :city)
      AND (:speciality IS NULL OR speciality = :speciality)
),
daily AS (
    SELECT r.event_id, r.registered_on, COUNT(*) AS new_registrations
    FROM registrations AS r
    JOIN scope AS s ON s.event_id = r.event_id
    GROUP BY r.event_id, r.registered_on
)
SELECT d.event_id,
       e.name                                                         AS event_name,
       d.registered_on,
       CAST(julianday(e.start_date) - julianday(d.registered_on) AS INTEGER) AS days_before_event,
       d.new_registrations,
       SUM(d.new_registrations) OVER (PARTITION BY d.event_id
                                      ORDER BY d.registered_on)       AS cumulative_registrations,
       e.capacity
FROM daily AS d
JOIN events AS e ON e.event_id = d.event_id
ORDER BY d.event_id, d.registered_on;
