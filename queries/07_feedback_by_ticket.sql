-- 07 Feedback by ticket type
-- Business question: How satisfied is each type of ticket buyer, and what
--   do they talk about most? If one group keeps raising price, that is a
--   pricing signal, not an event-quality problem.
-- Technique: A CTE counts survey mentions per ticket type and theme, with
--   ROW_NUMBER() OVER (PARTITION BY ticket_type ORDER BY mentions DESC) to
--   pick the most common theme; a second CTE gets the average rating and
--   the share of comments about pricing. A JOIN on rank = 1 combines them.
-- Filters: :event_id, :city, :speciality (NULL means "all").

WITH scope AS (
    SELECT event_id
    FROM events
    WHERE (:event_id   IS NULL OR event_id   = :event_id)
      AND (:city       IS NULL OR city       = :city)
      AND (:speciality IS NULL OR speciality = :speciality)
),
responses AS (
    SELECT r.ticket_type, f.rating, f.comment_theme
    FROM feedback AS f
    JOIN registrations AS r ON r.registration_id = f.registration_id
    JOIN scope         AS s ON s.event_id        = r.event_id
),
theme_ranked AS (
    SELECT ticket_type, comment_theme, COUNT(*) AS mentions,
           ROW_NUMBER() OVER (PARTITION BY ticket_type
                              ORDER BY COUNT(*) DESC, comment_theme) AS theme_rank
    FROM responses
    GROUP BY ticket_type, comment_theme
),
by_ticket AS (
    SELECT ticket_type,
           COUNT(*)                                                    AS responses,
           ROUND(AVG(rating), 2)                                       AS avg_rating,
           ROUND(100.0 * SUM(comment_theme = 'Pricing') / COUNT(*), 1) AS pricing_share_pct
    FROM responses
    GROUP BY ticket_type
)
SELECT b.ticket_type,
       b.responses,
       b.avg_rating,
       t.comment_theme                                  AS top_theme,
       ROUND(100.0 * t.mentions / b.responses, 1)       AS top_theme_share_pct,
       b.pricing_share_pct
FROM by_ticket AS b
JOIN theme_ranked AS t ON t.ticket_type = b.ticket_type AND t.theme_rank = 1
ORDER BY b.pricing_share_pct DESC;
