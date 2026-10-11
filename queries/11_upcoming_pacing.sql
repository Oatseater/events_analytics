-- 11 Upcoming event pacing (an estimate, not a fact)
-- Business question: Is each upcoming event selling fast enough to cover its
--   fixed cost? We compare tickets sold so far with how far similar past
--   events had got at the same number of days before they opened.
-- Technique: For each upcoming event, ROW_NUMBER() picks the three most
--   recent completed events in the same city (any city, for a new one), and
--   measures what share of their final sales had arrived by the same
--   days-to-go. Recent editions reflect today's demand, and capping the
--   comparison at three keeps the query fast at scale. Projected tickets =
--   sold so far / average share, with a low-high range from the fastest and
--   slowest comparable event, capped at capacity. Break-even uses the base
--   price times the average price ratio those comparable events achieved.
-- Filters: :event_id, :city, :speciality (NULL means "all").

WITH as_of AS (
    SELECT value AS as_of_date FROM dataset_info WHERE key = 'as_of_date'
),
upcoming AS (
    SELECT e.*, CAST(julianday(e.start_date) - julianday(a.as_of_date) AS INTEGER) AS days_to_go
    FROM events AS e CROSS JOIN as_of AS a
    WHERE e.start_date >= a.as_of_date
      AND (:event_id IS NULL OR e.event_id = :event_id) AND (:city IS NULL OR e.city = :city)
      AND (:speciality IS NULL OR e.speciality = :speciality)
),
completed AS (                -- every completed event is a candidate comparison
    SELECT e.event_id, e.city, e.start_date, COUNT(*) AS final_sold,
           SUM(r.price_paid) * 1.0 / (COUNT(*) * e.base_ticket_price) AS price_ratio
    FROM events AS e JOIN registrations AS r ON r.event_id = e.event_id
    WHERE e.start_date < (SELECT as_of_date FROM as_of)
    GROUP BY e.event_id, e.city, e.start_date, e.base_ticket_price
),
pairs AS (                    -- the three most recent comparable events for each upcoming one
    SELECT u.event_id, u.days_to_go, c.event_id AS comp_id, c.start_date AS comp_start,
           c.final_sold, c.price_ratio,
           ROW_NUMBER() OVER (PARTITION BY u.event_id ORDER BY c.start_date DESC) AS recency
    FROM upcoming AS u
    JOIN completed AS c
      ON c.city = u.city OR NOT EXISTS (SELECT 1 FROM completed AS c2 WHERE c2.city = u.city)
),
shares AS (                   -- share of each comparable event's final sales sold by now
    SELECT p.event_id, p.price_ratio,
           1.0 * SUM(julianday(p.comp_start) - julianday(r.registered_on) >= p.days_to_go)
               / p.final_sold AS share_by_now
    FROM pairs AS p
    JOIN registrations AS r ON r.event_id = p.comp_id
    WHERE p.recency <= 3
    GROUP BY p.event_id, p.comp_id, p.price_ratio, p.final_sold
),
projection AS (
    SELECT u.event_id, u.name, u.city, u.start_date, u.days_to_go, u.capacity,
           (SELECT COUNT(*) FROM registrations AS r WHERE r.event_id = u.event_id) AS sold_so_far,
           COUNT(sh.event_id) AS comparables,
           AVG(sh.share_by_now) AS avg_share, MIN(sh.share_by_now) AS min_share,
           MAX(sh.share_by_now) AS max_share,
           MAX(u.fixed_cost - COALESCE(u.sponsorship_revenue, 0), 0)
               / (u.base_ticket_price * AVG(sh.price_ratio)) AS breakeven_exact
    FROM upcoming AS u LEFT JOIN shares AS sh ON sh.event_id = u.event_id
    GROUP BY u.event_id
)
SELECT event_id, name AS event_name, city, start_date, days_to_go, capacity, sold_so_far,
       comparables,
       ROUND(100 * avg_share, 1)                                      AS typical_share_by_now_pct,
       MIN(capacity, CAST(ROUND(sold_so_far / NULLIF(avg_share, 0)) AS INTEGER)) AS projected_tickets,
       MIN(capacity, CAST(ROUND(sold_so_far / NULLIF(max_share, 0)) AS INTEGER)) AS projected_low,
       CASE WHEN sold_so_far > 0 AND avg_share > 0   -- slowest comparable at 0 means "up to capacity"
            THEN COALESCE(MIN(capacity, CAST(ROUND(sold_so_far / NULLIF(min_share, 0)) AS INTEGER)), capacity)
       END                                                            AS projected_high,
       CAST(breakeven_exact AS INTEGER) + (breakeven_exact > CAST(breakeven_exact AS INTEGER))
                                                                      AS breakeven_tickets,
       CASE                   -- projections are capped at capacity: you cannot sell more seats than exist
           WHEN sold_so_far = 0 THEN 'No sales yet'
           WHEN COALESCE(avg_share, 0) = 0 THEN 'Too early to project'
           WHEN MIN(capacity, sold_so_far / max_share) >= breakeven_exact THEN 'On track'
           WHEN MIN(capacity, sold_so_far / avg_share) <  breakeven_exact THEN 'At risk'
           ELSE 'Watch'
       END                                                            AS pacing_status
FROM projection
ORDER BY start_date;
