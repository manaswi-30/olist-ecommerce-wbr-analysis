-- Gross item revenue (price only; excludes freight). Calendar spine retains zero-revenue months.
WITH RECURSIVE months(month) AS (
 SELECT strftime('%Y-%m', MIN(order_purchase_timestamp)) FROM mart_orders WHERE order_purchase_timestamp IS NOT NULL
 UNION ALL
 SELECT strftime('%Y-%m', date(month || '-01','+1 month')) FROM months
 WHERE month < (SELECT strftime('%Y-%m', MAX(order_purchase_timestamp)) FROM mart_orders WHERE order_purchase_timestamp IS NOT NULL)
), monthly AS (
 SELECT m.month, COALESCE(SUM(CASE WHEN o.order_status <> 'canceled' THEN o.item_total ELSE 0 END),0) revenue
 FROM months m LEFT JOIN mart_orders o ON strftime('%Y-%m',o.order_purchase_timestamp)=m.month
 GROUP BY m.month
), with_lag AS (
 SELECT month, revenue, LAG(revenue) OVER (ORDER BY month) previous_month_revenue FROM monthly
)
SELECT month, ROUND(revenue,2) revenue, ROUND(previous_month_revenue,2) previous_month_revenue,
 CASE WHEN previous_month_revenue IS NULL OR previous_month_revenue=0 THEN NULL
      ELSE ROUND(100.0*(revenue-previous_month_revenue)/previous_month_revenue,2) END mom_growth_pct
FROM with_lag ORDER BY month;
