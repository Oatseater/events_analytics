-- 04 Month-over-month registration growth by city
-- Business question: In each city, how fast do registrations build up from
--   one month to the next as an event approaches?
-- Technique: Group registrations by city and calendar month, then use the
--   LAG window function (PARTITION BY city, ORDER BY month) to fetch the
--   previous month's count on the same row. Growth is only calculated when
--   that previous row really is the previous calendar month (cities have gaps
--   between events) and had at least 20 registrations (so a near-empty first
--   month does not produce a meaningless +500%). A second window,
--   AVG() OVER (PARTITION BY city), gives each city's average monthly growth.
--   The month containing the as-of date is still in progress, so it is shown
--   but never used to compute growth (a part-month would look like a collapse).
-- Filters: :event_id, :city, :speciality (NULL means "all").

WITH as_of AS (
    SELECT value AS as_of_date FROM dataset_info WHERE key = 'as_of_date'
),
scope AS (
    SELECT event_id
    FROM events
    WHERE (:event_id   IS NULL OR event_id   = :event_id)
      AND (:city       IS NULL OR city       = :city)
      AND (:speciality IS NULL OR speciality = :speciality)
),
monthly AS (
    SELECT e.city,
           date(r.registered_on, 'start of month') AS month_start,
           COUNT(*)                                 AS registrations
    FROM registrations AS r
    JOIN events AS e ON e.event_id = r.event_id
    JOIN scope  AS s ON s.event_id = r.event_id
    GROUP BY e.city, month_start
),
with_previous AS (
    SELECT city, month_start, registrations,
           LAG(month_start)   OVER (PARTITION BY city ORDER BY month_start) AS prev_month_start,
           LAG(registrations) OVER (PARTITION BY city ORDER BY month_start) AS prev_registrations
    FROM monthly
),
growth AS (
    SELECT city, month_start, registrations,
           CASE WHEN prev_month_start = date(month_start, '-1 month')
                 AND prev_registrations >= 20
                 AND month_start < (SELECT date(as_of_date, 'start of month') FROM as_of)
                THEN ROUND(100.0 * (registrations - prev_registrations) / prev_registrations, 1)
           END AS mom_growth_pct          -- NULL when there is no previous month to compare
    FROM with_previous
)
SELECT city,
       substr(month_start, 1, 7)                                 AS month,
       registrations,
       mom_growth_pct,
       ROUND(AVG(mom_growth_pct) OVER (PARTITION BY city), 1)    AS city_avg_mom_growth_pct
FROM growth
ORDER BY city, month;
