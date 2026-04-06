
--  Monthly revenue, AOV, delivery performance, payment breakdown.
--  These queries feed directly into Power BI via DirectQuery.
--  Run AFTER data is loaded.
-- & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d ecommerce -f sql\04_revenue_rollup.sql

-- Monthly revenue rollup
SELECT
    d.year,
    d.month,
    d.month_name,
    COUNT(DISTINCT o.order_id)                           AS total_orders,
    COUNT(DISTINCT c.customer_unique_id)                 AS unique_customers,
    ROUND(SUM(p.payment_value)::NUMERIC, 2)              AS gross_revenue,
    ROUND(AVG(p.payment_value)::NUMERIC, 2)              AS avg_order_value,
    ROUND(SUM(i.freight_value)::NUMERIC, 2)              AS total_freight,
    ROUND((SUM(p.payment_value) - SUM(i.freight_value))
          ::NUMERIC, 2)                                  AS net_revenue,
    ROUND(
        (SUM(p.payment_value)
         - LAG(SUM(p.payment_value)) OVER (ORDER BY d.year, d.month))
        * 100.0
        / NULLIF(LAG(SUM(p.payment_value)) OVER (ORDER BY d.year, d.month), 0)
    ::NUMERIC, 1)                                        AS mom_growth_pct
FROM fact_orders         o
JOIN dim_date            d  ON d.date_key    = o.purchase_date_key
JOIN dim_customers       c  ON c.customer_id = o.customer_id
JOIN fact_payments       p  ON p.order_id    = o.order_id
JOIN fact_order_items    i  ON i.order_id    = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- Revenue by state
SELECT
    c.state,
    COUNT(DISTINCT o.order_id)               AS orders,
    COUNT(DISTINCT c.customer_unique_id)     AS customers,
    ROUND(SUM(p.payment_value)::NUMERIC, 2)  AS revenue,
    ROUND(AVG(p.payment_value)::NUMERIC, 2)  AS avg_order_value
FROM fact_orders    o
JOIN dim_customers  c ON c.customer_id = o.customer_id
JOIN fact_payments  p ON p.order_id    = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.state
ORDER BY revenue DESC;

-- Revenue by product category (top 20)
SELECT
    COALESCE(p.category_name_english, 'unknown')   AS category,
    COUNT(DISTINCT o.order_id)                      AS orders,
    COUNT(i.item_id)                                AS items_sold,
    ROUND(SUM(i.price)::NUMERIC, 2)                 AS revenue,
    ROUND(AVG(i.price)::NUMERIC, 2)                 AS avg_item_price,
    ROUND(AVG(r.review_score)::NUMERIC, 2)          AS avg_review_score
FROM fact_orders         o
JOIN fact_order_items    i ON i.order_id   = o.order_id
JOIN dim_products        p ON p.product_id = i.product_id
LEFT JOIN fact_reviews   r ON r.order_id   = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY p.category_name_english
ORDER BY revenue DESC
LIMIT 20;

-- Delivery performance by month
SELECT
    d.year,
    d.month,
    COUNT(o.order_id)                              AS delivered_orders,
    ROUND(AVG(
        EXTRACT(DAY FROM o.delivered_customer_date
                       - o.purchase_date))
    ::NUMERIC, 1)                                  AS avg_delivery_days,
    ROUND(SUM(CASE
        WHEN o.delivered_customer_date <= o.estimated_delivery_date
        THEN 1 ELSE 0 END) * 100.0
        / COUNT(o.order_id)
    ::NUMERIC, 1)                                  AS on_time_pct,
    ROUND(AVG(r.review_score)::NUMERIC, 2)         AS avg_review_score
FROM fact_orders    o
JOIN dim_date       d  ON d.date_key   = o.purchase_date_key
LEFT JOIN fact_reviews r ON r.order_id = o.order_id
WHERE o.order_status = 'delivered'
  AND o.delivered_customer_date IS NOT NULL
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- Payment method breakdown
SELECT
    payment_type,
    COUNT(*)                                      AS transactions,
    ROUND(AVG(payment_value)::NUMERIC, 2)         AS avg_payment,
    ROUND(SUM(payment_value)::NUMERIC, 2)         AS total_value,
    ROUND(AVG(installments)::NUMERIC, 1)          AS avg_installments,
    ROUND(COUNT(*) * 100.0
          / SUM(COUNT(*)) OVER ()
    ::NUMERIC, 1)                                 AS pct_of_transactions
FROM fact_payments
GROUP BY payment_type
ORDER BY total_value DESC;