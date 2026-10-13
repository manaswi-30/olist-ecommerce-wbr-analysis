-- Calendar spine ensures days with zero orders appear. Dates span observed purchase dates.
WITH RECURSIVE calendar(day) AS (
 SELECT date(MIN(order_purchase_timestamp)) FROM mart_orders WHERE order_purchase_timestamp IS NOT NULL
 UNION ALL
 SELECT date(day,'+1 day') FROM calendar
 WHERE day < (SELECT date(MAX(order_purchase_timestamp)) FROM mart_orders WHERE order_purchase_timestamp IS NOT NULL)
), daily AS (
 SELECT c.day, COUNT(m.order_id) order_count
 FROM calendar c LEFT JOIN mart_orders m ON date(m.order_purchase_timestamp)=c.day
 GROUP BY c.day
), rolling AS (
 SELECT day, order_count,
        AVG(order_count) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) rolling_7day_avg,
        COUNT(*) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) days_in_window
 FROM daily
)
SELECT day, order_count, ROUND(rolling_7day_avg,2) rolling_7day_avg, days_in_window
FROM rolling ORDER BY day;
