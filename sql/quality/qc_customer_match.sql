-- Critical: order's customer_id must resolve to a cleaned customer.
SELECT o.order_id, o.customer_id
FROM stg_orders o LEFT JOIN stg_customers c ON o.customer_id=c.customer_id
WHERE c.customer_id IS NULL;
