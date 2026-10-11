-- 06 Break-even analysis (completed events)
-- Business question: Did each completed event's income cover its fixed cost,
--   and how many paid tickets did it need to get there? No-shows have already
--   paid, so break-even is counted in tickets sold. Attendance is reported
--   next to it, because sponsors judge an event by who walks through the door.
-- Technique: A CTE totals tickets, revenue and attendance per event; the next
--   divides the fixed cost still to cover (after any recorded sponsorship)
--   by the average ticket price to get the break-even ticket count. SQLite has
--   no CEIL() by default, so we round up by hand. Because tickets_sold >=
--   ceil(x) exactly when revenue covers the cost, the status always agrees
--   with the margin. Sponsorship NULL means "not recorded", treated as zero.
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
event_totals AS (
    SELECT e.event_id, e.name AS event_name, e.city, e.start_date, e.fixed_cost,
           e.sponsorship_revenue,
           COUNT(r.registration_id) AS tickets_sold,
           SUM(r.attended)          AS attended,
           SUM(r.price_paid)        AS ticket_revenue
    FROM events AS e
    JOIN scope  AS s ON s.event_id = e.event_id
    JOIN registrations AS r ON r.event_id = e.event_id
    WHERE e.start_date < (SELECT as_of_date FROM as_of)     -- completed events only
    GROUP BY e.event_id, e.name, e.city, e.start_date, e.fixed_cost, e.sponsorship_revenue
),
break_even AS (
    SELECT *,
           1.0 * ticket_revenue / tickets_sold AS avg_ticket_aed,
           MAX(fixed_cost - COALESCE(sponsorship_revenue, 0), 0) * 1.0 * tickets_sold
               / NULLIF(ticket_revenue, 0)       AS breakeven_exact
    FROM event_totals
),
rounded AS (
    SELECT *,
           CAST(breakeven_exact AS INTEGER)
             + (breakeven_exact > CAST(breakeven_exact AS INTEGER)) AS breakeven_tickets
    FROM break_even
)
SELECT event_id,
       event_name,
       city,
       ticket_revenue                                  AS ticket_revenue_aed,
       sponsorship_revenue                             AS sponsorship_aed,     -- NULL = not recorded
       fixed_cost                                      AS fixed_cost_aed,
       ticket_revenue + COALESCE(sponsorship_revenue, 0) - fixed_cost AS margin_aed,
       ROUND(avg_ticket_aed, 0)                        AS avg_ticket_aed,
       breakeven_tickets,
       tickets_sold,
       tickets_sold - breakeven_tickets                AS ticket_gap,
       attended,
       CASE WHEN tickets_sold >= breakeven_tickets THEN 'Above break-even'
            ELSE 'Below break-even' END                AS status
FROM rounded
ORDER BY start_date;
