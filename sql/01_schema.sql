
--  01_schema.sql
--  Creates the complete star schema for the ecommerce project.
--
--  HOW TO RUN (Windows CMD from project folder):
--  & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d ecommerce -f sql\01_schema.sql
--  (enter password: ecom_pass123 when prompted)



--  DIMENSION TABLES 

CREATE TABLE IF NOT EXISTS dim_customers (
    customer_id          VARCHAR(50) PRIMARY KEY,
    customer_unique_id   VARCHAR(50) NOT NULL,
    zip_code             VARCHAR(10),
    city                 VARCHAR(100),
    state                CHAR(2)
);

CREATE TABLE IF NOT EXISTS dim_sellers (
    seller_id   VARCHAR(50) PRIMARY KEY,
    zip_code    VARCHAR(10),
    city        VARCHAR(100),
    state       CHAR(2)
);

CREATE TABLE IF NOT EXISTS dim_products (
    product_id              VARCHAR(50) PRIMARY KEY,
    category_name_english   VARCHAR(100),
    name_length             INT,
    description_length      INT,
    photos_qty              INT,
    weight_g                NUMERIC(10,2),
    length_cm               NUMERIC(6,2),
    height_cm               NUMERIC(6,2),
    width_cm                NUMERIC(6,2)
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key     DATE PRIMARY KEY,
    year         INT,
    quarter      INT,
    month        INT,
    month_name   VARCHAR(15),
    week         INT,
    day_of_week  INT,       -- 0=Sunday, 6=Saturday
    is_weekend   BOOLEAN
);


--  FACT TABLES 

CREATE TABLE IF NOT EXISTS fact_orders (
    order_id                  VARCHAR(50) PRIMARY KEY,
    customer_id               VARCHAR(50)  REFERENCES dim_customers(customer_id),
    order_status              VARCHAR(30),
    purchase_date             TIMESTAMP,
    approved_date             TIMESTAMP,
    delivered_carrier_date    TIMESTAMP,
    delivered_customer_date   TIMESTAMP,
    estimated_delivery_date   TIMESTAMP,
    purchase_date_key         DATE         REFERENCES dim_date(date_key)
);

CREATE TABLE IF NOT EXISTS fact_order_items (
    item_id         SERIAL PRIMARY KEY,
    order_id        VARCHAR(50)  REFERENCES fact_orders(order_id),
    product_id      VARCHAR(50)  REFERENCES dim_products(product_id),
    seller_id       VARCHAR(50)  REFERENCES dim_sellers(seller_id),
    shipping_date   TIMESTAMP,
    price           NUMERIC(10,2),
    freight_value   NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS fact_payments (
    payment_id           SERIAL PRIMARY KEY,
    order_id             VARCHAR(50)  REFERENCES fact_orders(order_id),
    payment_sequential   INT,
    payment_type         VARCHAR(30),
    installments         INT,
    payment_value        NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS fact_reviews (
    review_id             VARCHAR(50) PRIMARY KEY,
    order_id              VARCHAR(50)  REFERENCES fact_orders(order_id),
    review_score          INT          CHECK (review_score BETWEEN 1 AND 5),
    review_created_date   TIMESTAMP,
    answer_date           TIMESTAMP
);


--  ML OUTPUT TABLES 

CREATE TABLE IF NOT EXISTS ml_churn_predictions (
    customer_unique_id   VARCHAR(50) PRIMARY KEY,
    rfm_segment          VARCHAR(30),
    recency_days         NUMERIC(10,2),
    frequency            INT,
    monetary             NUMERIC(10,2),
    churn_probability    NUMERIC(6,4),
    churn_label          VARCHAR(10),   -- Low / Medium / High
    predicted_at         TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ml_clv_predictions (
    customer_unique_id   VARCHAR(50) PRIMARY KEY,
    rfm_segment          VARCHAR(30),
    monetary             NUMERIC(10,2),
    predicted_clv        NUMERIC(10,2),
    clv_segment          VARCHAR(20),   -- Bronze / Silver / Gold / Platinum
    recency_days         NUMERIC(10,2),
    frequency            INT,
    predicted_at         TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS streaming_orders (
    id               SERIAL PRIMARY KEY,
    order_id         VARCHAR(50),
    product_category VARCHAR(100),
    order_value      NUMERIC(10,2),
    freight_value    NUMERIC(10,2),
    state            CHAR(2),
    payment_type     VARCHAR(30),
    review_score     INT,
    event_timestamp  TIMESTAMP,
    received_at      TIMESTAMP DEFAULT NOW()
);


--  PERFORMANCE INDEXES 

CREATE INDEX IF NOT EXISTS idx_orders_customer    ON fact_orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_date        ON fact_orders(purchase_date_key);
CREATE INDEX IF NOT EXISTS idx_orders_status      ON fact_orders(order_status);
CREATE INDEX IF NOT EXISTS idx_items_order        ON fact_order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_items_product      ON fact_order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_payments_order     ON fact_payments(order_id);
CREATE INDEX IF NOT EXISTS idx_reviews_order      ON fact_reviews(order_id);
CREATE INDEX IF NOT EXISTS idx_churn_segment      ON ml_churn_predictions(rfm_segment);
CREATE INDEX IF NOT EXISTS idx_churn_label        ON ml_churn_predictions(churn_label);
CREATE INDEX IF NOT EXISTS idx_clv_segment        ON ml_clv_predictions(clv_segment);


--  VERIFY 
SELECT table_name
FROM   information_schema.tables
WHERE  table_schema = 'public'
ORDER  BY table_name;