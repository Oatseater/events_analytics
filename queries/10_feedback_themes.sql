-- 10 Feedback themes (supports the Event Deep-Dive page)
-- Business question: What did attendees comment on most, and how did they
--   rate the event within each theme?
-- Technique: JOIN feedback to registrations, GROUP BY theme, and a windowed
--   SUM() OVER () to turn counts into each theme's share of all comments.
-- Filters: :event_id, :city, :speciality (NULL means "all").

WITH scope AS (
    SELECT event_id
    FROM events
    WHERE (:event_id   IS NULL OR event_id   = :event_id)
      AND (:city       IS NULL OR city       = :city)
      AND (:speciality IS NULL OR speciality = :speciality)
)
SELECT f.comment_theme,
       COUNT(*)                                             AS mentions,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS share_pct,
       ROUND(AVG(f.rating), 2)                              AS avg_rating
FROM feedback AS f
JOIN registrations AS r ON r.registration_id = f.registration_id
JOIN scope         AS s ON s.event_id        = r.event_id
GROUP BY f.comment_theme
ORDER BY mentions DESC;
