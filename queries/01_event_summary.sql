-- 01 Event summary
-- Business question: For each event, how many tickets were sold, how much
--   ticket revenue did we take, and what share of ticket holders came?
--   Upcoming events show sales so far; their attendance is not known yet.
-- Technique: LEFT JOIN from events to registrations (an event with no sales
--   still appears), GROUP BY, and conditional aggregation. attended is NULL
--   until an event happens, so SUM(attended) / COUNT(attended) is the
--   attendance rate over known outcomes only. Status comes from the as-of date.
-- Filters: :event_id, :city, :speciality (NULL means "all"), set by the dashboard.

WITH as_of AS (               -- the date this data describes
    SELECT value AS as_of_date FROM dataset_info WHERE key = 'as_of_date'
),
scope AS (                    -- events that match the dashboard filters
    SELECT event_id
    FROM events
    WHERE (:event_id   IS NULL OR event_id   = :event_id)
      AND (:city       IS NULL OR city       = :city)
      AND (:speciality IS NULL OR speciality = :speciality)
)
SELECT
    e.event_id,
    e.name                                    AS event_name,
    e.city,
    e.speciality,
    e.start_date,
    CASE WHEN e.start_date < a.as_of_date THEN 'Completed' ELSE 'Upcoming' END AS status,
    e.capacity,
    COUNT(r.registration_id)                  AS registrations,
    COALESCE(SUM(r.price_paid), 0)            AS revenue_aed,
    SUM(r.attended)                           AS attended,          -- NULL while upcoming
    ROUND(100.0 * SUM(r.attended) / NULLIF(COUNT(r.attended), 0), 1) AS attendance_rate_pct,
    ROUND(100.0 * COUNT(r.registration_id) / e.capacity, 1)        AS fill_rate_pct
FROM events AS e
JOIN scope  AS s ON s.event_id = e.event_id
CROSS JOIN as_of AS a
LEFT JOIN registrations AS r ON r.event_id = e.event_id
GROUP BY e.event_id, e.name, e.city, e.speciality, e.start_date, a.as_of_date, e.capacity
ORDER BY e.start_date;
