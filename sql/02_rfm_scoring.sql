--  02_rfm_scoring.sql
--  RFM analysis — Recency, Frequency, Monetary scoring
--  Run AFTER data is loaded (python data\load_kaggle.py)
--  HOW TO RUN:
--  & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d ecommerce -f sql\02_rfm_scoring.sql

WITH order_totals AS (
    SELECT
        o.order_id,
        c.customer_unique_id,
        o.purchase_date,
        SUM(p.payment_value)   AS order_value
    FROM fact_orders         o
    JOIN dim_customers       c  ON c.customer_id = o.customer_id
    JOIN fact_payments       p  ON p.order_id    = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY o.order_id, c.customer_unique_id, o.purchase_date
),
 
rfm_raw AS (
    SELECT
        customer_unique_id,
        EXTRACT(DAY FROM NOW() - MAX(purchase_date))::INT   AS recency_days,
        COUNT(DISTINCT order_id)                             AS frequency,
        ROUND(SUM(order_value)::NUMERIC, 2)                 AS monetary,
        ROUND(AVG(order_value)::NUMERIC, 2)                 AS avg_order_value,
        ROUND(MAX(order_value)::NUMERIC, 2)                 AS max_order_value,
        MAX(purchase_date)                                   AS last_purchase,
        MIN(purchase_date)                                   AS first_purchase
    FROM order_totals
    GROUP BY customer_unique_id
),
 
rfm_scored AS (
    SELECT *,
        NTILE(5) OVER (ORDER BY recency_days DESC)   AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC)       AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC)        AS m_score
    FROM rfm_raw
),
 
rfm_labelled AS (
    SELECT *,
        CASE
            WHEN r_score >= 4 AND f_score >= 4       THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3       THEN 'Loyal Customers'
            WHEN r_score >= 4 AND f_score <= 2       THEN 'Recent Customers'
            WHEN r_score >= 3 AND f_score <= 2       THEN 'Potential Loyalists'
            WHEN r_score <= 2 AND f_score >= 3       THEN 'At Risk'
            WHEN r_score <= 2 AND m_score >= 4       THEN 'Cannot Lose Them'
            WHEN r_score = 1  AND f_score = 1        THEN 'Lost'
            ELSE                                          'Needs Attention'
        END AS rfm_segment
    FROM rfm_scored
)


-- Top 20 customers by monetary value

SELECT
    customer_unique_id,
    recency_days,
    frequency,
    monetary,
    avg_order_value,
    r_score, f_score, m_score,
    rfm_segment,
    last_purchase
FROM rfm_labelled
ORDER BY monetary DESC
LIMIT 20;

-- Segment summary — connect this to Power BI
SELECT
    rfm_segment,
    COUNT(*)                                AS customers,
    ROUND(COUNT(*) * 100.0
          / SUM(COUNT(*)) OVER (), 1)       AS pct_customers,
    ROUND(AVG(monetary)::NUMERIC, 2)        AS avg_monetary,
    ROUND(SUM(monetary)::NUMERIC, 2)        AS total_monetary,
    ROUND(SUM(monetary) * 100.0
          / SUM(SUM(monetary)) OVER (), 1)  AS pct_revenue,
    ROUND(AVG(recency_days)::NUMERIC, 0)    AS avg_recency_days,
    ROUND(AVG(frequency)::NUMERIC, 2)       AS avg_frequency
FROM rfm_labelled
GROUP BY rfm_segment
ORDER BY avg_monetary DESC;