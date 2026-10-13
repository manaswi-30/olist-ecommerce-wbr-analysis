-- Warning: compare order-level payments with item + freight total.
-- Differences can be legitimate (vouchers, interest, rounding, partial/cancelled flows); flag, don't auto-correct.
WITH items AS (
 SELECT order_id, SUM(COALESCE(price,0)+COALESCE(freight_value,0)) expected_total
 FROM stg_items GROUP BY order_id
), payments AS (
 SELECT order_id, SUM(payment_value) paid_total FROM stg_payments GROUP BY order_id
), ids AS (
 SELECT order_id FROM items UNION SELECT order_id FROM payments
)
SELECT ids.order_id, ROUND(COALESCE(i.expected_total,0),2) expected_total,
       ROUND(COALESCE(p.paid_total,0),2) paid_total,
       ROUND(COALESCE(p.paid_total,0)-COALESCE(i.expected_total,0),2) difference
FROM ids LEFT JOIN items i ON ids.order_id=i.order_id
         LEFT JOIN payments p ON ids.order_id=p.order_id
WHERE ABS(COALESCE(p.paid_total,0)-COALESCE(i.expected_total,0)) > 0.05;
