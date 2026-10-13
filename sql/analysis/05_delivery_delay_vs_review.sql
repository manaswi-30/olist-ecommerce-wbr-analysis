-- Delay = actual delivered timestamp minus estimated delivery timestamp (days).
-- Positive means late; negative means early. Group by order-level mean review score.
SELECT CAST(ROUND(review_score) AS INTEGER) review_score,
       COUNT(*) delivered_orders,
       ROUND(AVG(delivery_delay_days),2) avg_delay_days,
       ROUND(100.0*AVG(CASE WHEN delivery_delay_days > 0 THEN 1.0 ELSE 0.0 END),2) pct_delivered_late,
       ROUND(AVG(item_total),2) avg_item_revenue
FROM mart_orders
WHERE review_score IS NOT NULL
  AND delivery_delay_days IS NOT NULL
  AND order_delivered_customer_date IS NOT NULL
GROUP BY CAST(ROUND(review_score) AS INTEGER)
ORDER BY review_score;
