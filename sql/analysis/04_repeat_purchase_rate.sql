-- Full observed dataset window. Denominator = distinct identified customers with >=1 order.
-- Repeat customer = customer_unique_id with at least two distinct orders in the observation window.
WITH customer_orders AS (
 SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) order_count
 FROM stg_orders o JOIN stg_customers c ON c.customer_id=o.customer_id
 WHERE c.customer_unique_id IS NOT NULL AND TRIM(c.customer_unique_id)<>''
   AND o.order_purchase_timestamp IS NOT NULL
 GROUP BY c.customer_unique_id
)
SELECT COUNT(*) identified_customers,
       SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END) repeat_customers,
       ROUND(100.0*SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0),2) repeat_purchase_rate_pct,
       MIN(order_count) min_orders_per_customer, MAX(order_count) max_orders_per_customer
FROM customer_orders;
