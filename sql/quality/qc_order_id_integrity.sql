-- Critical: missing/blank IDs and duplicate IDs in cleaned orders.
SELECT order_id, 'NULL_OR_BLANK' AS issue FROM stg_orders WHERE order_id IS NULL OR TRIM(order_id)=''
UNION ALL
SELECT order_id, 'DUPLICATE' AS issue FROM (SELECT order_id FROM stg_orders GROUP BY order_id HAVING COUNT(*)>1);
