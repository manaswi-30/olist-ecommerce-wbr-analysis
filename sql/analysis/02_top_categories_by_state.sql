-- Category revenue from item rows, avoiding order-level payment/review join fan-out.
WITH category_state AS (
 SELECT c.customer_state, COALESCE(t.product_category_name_english,p.product_category_name,'unknown') category,
        SUM(i.price) revenue
 FROM stg_items i
 JOIN stg_orders o ON o.order_id=i.order_id
 JOIN stg_customers c ON c.customer_id=o.customer_id
 LEFT JOIN stg_products p ON p.product_id=i.product_id
 LEFT JOIN stg_category_translation t ON t.product_category_name=p.product_category_name
 WHERE o.order_status <> 'canceled'
 GROUP BY c.customer_state, COALESCE(t.product_category_name_english,p.product_category_name,'unknown')
), ranked AS (
 SELECT customer_state, category, revenue,
        DENSE_RANK() OVER (PARTITION BY customer_state ORDER BY revenue DESC) revenue_rank
 FROM category_state
)
SELECT customer_state, category, ROUND(revenue,2) revenue, revenue_rank
FROM ranked WHERE revenue_rank <= 3 ORDER BY customer_state, revenue_rank, category;
