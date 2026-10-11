-- 03 No-show rates by ticket type and by lead time
-- Business question: Which buyers are most likely to pay and then not turn
--   up? We look two ways: by ticket type, and by how many days before the
--   event the person registered. Only events that have happened count.
-- Technique: Date arithmetic with julianday() to get days-before-event, a
--   CASE expression to put each registration into a lead-time bucket, and
--   UNION ALL to stack the two breakdowns into one result. Tickets whose
--   attendance is still NULL (upcoming events) are left out, never counted
--   as no-shows.
-- Filters: :event_id, :city, :speciality (NULL means "all").

WITH scope AS (
    SELECT event_id
    FROM events
    WHERE (:event_id   IS NULL OR event_id   = :event_id)
      AND (:city       IS NULL OR city       = :city)
      AND (:speciality IS NULL OR speciality = :speciality)
),
bucketed AS (
    SELECT
        r.ticket_type,
        r.attended,
        CASE
            WHEN julianday(e.start_date) - julianday(r.registered_on) <= 14 THEN '0-14 days'
            WHEN julianday(e.start_date) - julianday(r.registered_on) <= 30 THEN '15-30 days'
            WHEN julianday(e.start_date) - julianday(r.registered_on) <= 60 THEN '31-60 days'
            WHEN julianday(e.start_date) - julianday(r.registered_on) <= 90 THEN '61-90 days'
            ELSE '91+ days'
        END AS lead_time_bucket
    FROM registrations AS r
    JOIN events AS e ON e.event_id = r.event_id
    JOIN scope  AS s ON s.event_id = r.event_id
    WHERE r.attended IS NOT NULL               -- only events that have happened
)
SELECT 'Ticket type'                                  AS breakdown,
       ticket_type                                    AS segment,
       COUNT(*)                                       AS registrations,
       SUM(1 - attended)                              AS no_shows,
       ROUND(100.0 * SUM(1 - attended) / COUNT(*), 1) AS no_show_rate_pct
FROM bucketed
GROUP BY ticket_type

UNION ALL

SELECT 'Lead time',
       lead_time_bucket,
       COUNT(*),
       SUM(1 - attended),
       ROUND(100.0 * SUM(1 - attended) / COUNT(*), 1)
FROM bucketed
GROUP BY lead_time_bucket

ORDER BY breakdown DESC, segment;
