
--  05_product_affinity.sql
--  Product analysis by customer segment.
--  *** Run LAST — needs ml_churn_predictions and ml_clv_predictions ***
--
--  HOW TO RUN:
--  & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d ecommerce -f sql\05_product_affinity.sql


-- Top 5 categories per RFM segment
WITH ranked AS (
    SELECT
        ch.rfm_segment,
        COALESCE(p.category_name_english, 'unknown')   AS category,
        COUNT(DISTINCT o.order_id)                      AS orders,
        ROUND(SUM(i.price)::NUMERIC, 2)                 AS revenue,
        RANK() OVER (
            PARTITION BY ch.rfm_segment
            ORDER BY SUM(i.price) DESC
        )                                               AS rnk
    FROM fact_orders             o
    JOIN dim_customers           c  ON c.customer_id  = o.customer_id
    JOIN fact_order_items        i  ON i.order_id     = o.order_id
    JOIN dim_products            p  ON p.product_id   = i.product_id
    JOIN ml_churn_predictions   ch  ON ch.customer_unique_id = c.customer_unique_id
    WHERE o.order_status = 'delivered'
      AND p.category_name_english IS NOT NULL
    GROUP BY ch.rfm_segment, p.category_name_english
)
SELECT rfm_segment, category, orders, revenue, rnk
FROM   ranked
WHERE  rnk <= 5
ORDER  BY rfm_segment, rnk;


-- Average predicted CLV per category (needs ml_clv_predictions)
SELECT
    COALESCE(p.category_name_english, 'unknown')   AS category,
    COUNT(DISTINCT c.customer_unique_id)            AS unique_buyers,
    ROUND(AVG(cl.predicted_clv)::NUMERIC, 2)        AS avg_predicted_clv,
    ROUND(AVG(ch.churn_probability)::NUMERIC, 4)    AS avg_churn_probability,
    ROUND(SUM(i.price)::NUMERIC, 2)                 AS total_revenue
FROM fact_order_items        i
JOIN fact_orders             o  ON o.order_id    = i.order_id
JOIN dim_customers           c  ON c.customer_id = o.customer_id
JOIN dim_products            p  ON p.product_id  = i.product_id
LEFT JOIN ml_clv_predictions    cl ON cl.customer_unique_id = c.customer_unique_id
LEFT JOIN ml_churn_predictions  ch ON ch.customer_unique_id = c.customer_unique_id
WHERE o.order_status = 'delivered'
  AND p.category_name_english IS NOT NULL
GROUP BY p.category_name_english
HAVING COUNT(DISTINCT c.customer_unique_id) >= 50
ORDER BY avg_predicted_clv DESC
LIMIT 15;