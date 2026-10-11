-- 08 Headline KPIs (supports the Overview page)
-- Business question: What are the headline numbers for the selected events:
--   tickets sold, ticket revenue, attendance rate and average rating, and how
--   many of the events are completed versus still upcoming?
-- Technique: Three independent aggregate CTEs (events, tickets, survey answers)
--   combined with CROSS JOIN, because each returns exactly one row. Events are
--   counted from the filter scope, not from tickets, so an event with no sales
--   yet is still counted. Attendance divides by COUNT(attended), which skips
--   the NULL outcomes of upcoming events. "Events below break-even" comes from 06.
-- Filters: :event_id, :city, :speciality (NULL means "all").

WITH as_of AS (
    SELECT value AS as_of_date FROM dataset_info WHERE key = 'as_of_date'
),
scope AS (
    SELECT event_id, start_date
    FROM events
    WHERE (:event_id   IS NULL OR event_id   = :event_id)
      AND (:city       IS NULL OR city       = :city)
      AND (:speciality IS NULL OR speciality = :speciality)
),
event_counts AS (
    SELECT COUNT(*)                                            AS events,
           SUM(start_date <  (SELECT as_of_date FROM as_of))   AS completed_events,
           SUM(start_date >= (SELECT as_of_date FROM as_of))   AS upcoming_events
    FROM scope
),
ticket_totals AS (
    SELECT COUNT(r.registration_id)                                        AS registrations,
           COALESCE(SUM(r.price_paid), 0)                                  AS revenue_aed,
           SUM(r.attended)                                                 AS attended,
           COUNT(r.registration_id) - COUNT(r.attended)                    AS upcoming_tickets,
           ROUND(100.0 * SUM(r.attended) / NULLIF(COUNT(r.attended), 0), 1) AS attendance_rate_pct
    FROM registrations AS r
    JOIN scope AS s ON s.event_id = r.event_id
),
rating_totals AS (
    SELECT COUNT(*)                AS responses,
           ROUND(AVG(f.rating), 2) AS avg_rating
    FROM feedback AS f
    JOIN registrations AS r ON r.registration_id = f.registration_id
    JOIN scope         AS s ON s.event_id        = r.event_id
)
SELECT c.events, c.completed_events, c.upcoming_events,
       t.registrations, t.revenue_aed, t.attended, t.upcoming_tickets, t.attendance_rate_pct,
       g.responses, g.avg_rating
FROM event_counts AS c
CROSS JOIN ticket_totals AS t
CROSS JOIN rating_totals AS g;
