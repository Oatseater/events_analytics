-- 02 Marketing funnel by channel
-- Business question: For each marketing channel, how many leads did we
--   contact, how many registered, and how many of those actually turned up?
--   Which channels bring people who show up, not just people who sign up?
-- Technique: Two CTEs aggregate leads and registrations separately (they
--   live in different tables). A UNION of their channel lists keeps channels
--   that exist on only one side, such as website sign-ups with no sales lead,
--   so no registration silently drops out. Attendance uses COUNT(attended),
--   which skips upcoming events whose outcome is not known yet.
-- Filters: :event_id, :city, :speciality (NULL means "all").

WITH as_of AS (
    SELECT value AS as_of_date FROM dataset_info WHERE key = 'as_of_date'
),
scope AS (
    SELECT event_id, start_date < (SELECT as_of_date FROM as_of) AS completed
    FROM events
    WHERE (:event_id   IS NULL OR event_id   = :event_id)
      AND (:city       IS NULL OR city       = :city)
      AND (:speciality IS NULL OR speciality = :speciality)
),
lead_counts AS (              -- stage 1: everyone we contacted
    SELECT l.channel, COUNT(*) AS leads, SUM(s.completed) AS leads_completed
    FROM leads AS l
    JOIN scope AS s ON s.event_id = l.event_id
    GROUP BY l.channel
),
registration_counts AS (      -- stages 2 and 3: registered, then attended
    SELECT r.channel,
           COUNT(*)          AS registered,
           SUM(r.attended)   AS attended,
           COUNT(r.attended) AS outcome_known      -- tickets for events that have happened
    FROM registrations AS r
    JOIN scope AS s ON s.event_id = r.event_id
    GROUP BY r.channel
),
channels AS (
    SELECT channel FROM lead_counts
    UNION
    SELECT channel FROM registration_counts
)
SELECT
    c.channel,
    COALESCE(lc.leads, 0)                                                AS leads,
    COALESCE(rc.registered, 0)                                           AS registered,
    rc.attended,
    ROUND(100.0 * rc.registered / NULLIF(lc.leads, 0), 1)                AS lead_to_registration_pct,
    ROUND(100.0 * rc.attended / NULLIF(rc.outcome_known, 0), 1)          AS attendance_rate_pct,
    ROUND(100.0 * rc.attended / NULLIF(lc.leads_completed, 0), 1)        AS lead_to_attendance_pct
FROM channels AS c
LEFT JOIN lead_counts         AS lc ON lc.channel = c.channel
LEFT JOIN registration_counts AS rc ON rc.channel = c.channel
ORDER BY attendance_rate_pct DESC, registered DESC;
