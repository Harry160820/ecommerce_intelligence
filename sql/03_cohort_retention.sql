--  Monthly cohort retention analysis.
--  Each cohort = customers whose FIRST order was in a given month.
--  Run AFTER data is loaded.
-- & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d ecommerce -f sql\03_cohort_retention.sql

WITH first_purchase AS (
    SELECT
        c.customer_unique_id,
        DATE_TRUNC('month', MIN(o.purchase_date))::DATE   AS cohort_month
    FROM fact_orders    o
    JOIN dim_customers  c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
),

monthly_activity AS (
    SELECT
        c.customer_unique_id,
        DATE_TRUNC('month', o.purchase_date)::DATE        AS activity_month,
        ROUND(SUM(p.payment_value)::NUMERIC, 2)           AS monthly_revenue
    FROM fact_orders    o
    JOIN dim_customers  c ON c.customer_id = o.customer_id
    JOIN fact_payments  p ON p.order_id    = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id,
             DATE_TRUNC('month', o.purchase_date)
),

cohort_data AS (
    SELECT
        fp.cohort_month,
        (EXTRACT(YEAR  FROM AGE(ma.activity_month, fp.cohort_month)) * 12 +
         EXTRACT(MONTH FROM AGE(ma.activity_month, fp.cohort_month)))::INT  AS month_number,
        COUNT(DISTINCT fp.customer_unique_id)                                AS active_customers,
        ROUND(SUM(ma.monthly_revenue)::NUMERIC, 2)                           AS cohort_revenue
    FROM first_purchase   fp
    JOIN monthly_activity ma
        ON  ma.customer_unique_id = fp.customer_unique_id
        AND ma.activity_month    >= fp.cohort_month
    GROUP BY fp.cohort_month, month_number
),

cohort_sizes AS (
    SELECT cohort_month,
           active_customers AS cohort_size
    FROM cohort_data
    WHERE month_number = 0
)

SELECT
    cd.cohort_month,
    cs.cohort_size,
    cd.month_number,
    cd.active_customers,
    ROUND(cd.active_customers * 100.0 / cs.cohort_size, 1)  AS retention_pct,
    ROUND(cd.cohort_revenue, 2)                               AS cohort_revenue
FROM cohort_data   cd
JOIN cohort_sizes  cs ON cs.cohort_month = cd.cohort_month
WHERE cd.month_number <= 6
ORDER BY cd.cohort_month, cd.month_number;