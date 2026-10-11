-- 05 Top 3 countries per event
-- Business question: Where do each event's delegates come from? Knowing the
--   top source countries tells us where to focus visa letters, partner
--   societies and paid advertising.
-- Technique: Count registrations per event and country, then ROW_NUMBER()
--   OVER (PARTITION BY event ORDER BY count DESC) ranks countries within
--   each event; a windowed SUM() gives each country's share of the event.
--   Keeping rank <= 3 returns the top three per event.
-- Filters: :event_id, :city, :speciality (NULL means "all").

WITH scope AS (
    SELECT event_id
    FROM events
    WHERE (:event_id   IS NULL OR event_id   = :event_id)
      AND (:city       IS NULL OR city       = :city)
      AND (:speciality IS NULL OR speciality = :speciality)
),
country_counts AS (
    SELECT r.event_id, a.country, COUNT(*) AS registrations
    FROM registrations AS r
    JOIN attendees AS a ON a.attendee_id = r.attendee_id
    JOIN scope     AS s ON s.event_id    = r.event_id
    GROUP BY r.event_id, a.country
),
ranked AS (
    SELECT event_id, country, registrations,
           ROUND(100.0 * registrations / SUM(registrations) OVER (PARTITION BY event_id), 1) AS share_pct,
           ROW_NUMBER() OVER (PARTITION BY event_id
                              ORDER BY registrations DESC, country) AS country_rank
    FROM country_counts
)
SELECT e.event_id,
       e.name AS event_name,
       k.country_rank,
       k.country,
       k.registrations,
       k.share_pct
FROM ranked AS k
JOIN events AS e ON e.event_id = k.event_id
WHERE k.country_rank <= 3
ORDER BY e.start_date, k.country_rank;
