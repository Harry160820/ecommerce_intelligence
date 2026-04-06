"""
Pulls customer data from PostgreSQL, builds the ML feature matrix.
Imported by train_churn.py, train_clv.py, and all three notebooks.
 
The two public functions are:
  build_feature_matrix()  →  returns DataFrame of all customer features
  get_rfm_segments(df)    →  adds RFM scores and segment labels
"""


import pandas as pd
import numpy as np
from src.db import engine

#SQL: customer-level feature extraction

_FEATURE_SQL = """

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
rfm AS (
    SELECT
        customer_unique_id,
        EXTRACT(DAY FROM NOW() - MAX(purchase_date))::FLOAT  AS recency_days,
        COUNT(DISTINCT order_id)                              AS frequency,
        ROUND(SUM(order_value)::NUMERIC, 2)                  AS monetary,
        ROUND(AVG(order_value)::NUMERIC, 2)                  AS avg_order_value,
        ROUND(MAX(order_value)::NUMERIC, 2)                  AS max_order_value,
        ROUND(MIN(order_value)::NUMERIC, 2)                  AS min_order_value,
        ROUND(STDDEV(order_value)::NUMERIC, 2)               AS std_order_value,
        MAX(purchase_date)                                    AS last_purchase_date,
        MIN(purchase_date)                                    AS first_purchase_date
    FROM order_totals
    GROUP BY customer_unique_id
)
SELECT * FROM rfm
"""
 
_REVIEW_SQL = """
SELECT
    c.customer_unique_id,
    COUNT(r.review_id)              AS review_count,
    ROUND(AVG(r.review_score), 2)   AS avg_review_score
FROM fact_orders    o
JOIN dim_customers  c ON c.customer_id = o.customer_id
JOIN fact_reviews   r ON r.order_id    = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_unique_id
"""
 
_CATEGORY_SQL = """
SELECT
    c.customer_unique_id,
    COUNT(DISTINCT p.category_name_english)   AS unique_categories
FROM fact_orders         o
JOIN dim_customers       c  ON c.customer_id = o.customer_id
JOIN fact_order_items    i  ON i.order_id    = o.order_id
JOIN dim_products        p  ON p.product_id  = i.product_id
WHERE o.order_status = 'delivered'
  AND p.category_name_english IS NOT NULL
GROUP BY c.customer_unique_id
"""

def build_feature_matrix():
    """
    Pull all customer features from PostgreSQL.
    Returns a clean DataFrame ready for ML training.
    """

    print("Pulling RFM features ...")
    df = pd.read_sql(_FEATURE_SQL, engine)

    print("Pulling review features ...")
    reviews = pd.read_sql(_REVIEW_SQL, engine)

    print("Pulling category features ...")
    cats = pd.read_sql(_CATEGORY_SQL, engine)

     # Join everything on customer_unique_id
    df = df.merge(reviews, on="customer_unique_id", how="left")
    df = df.merge(cats,    on="customer_unique_id", how="left")


    # fill missing values
    df["review_count"]      = df["review_count"].fillna(0).astype(int)
    df["avg_review_score"]  = df["avg_review_score"].fillna(3.0)
    df["unique_categories"] = df["unique_categories"].fillna(1).astype(int)
    df["std_order_value"]   = df["std_order_value"].fillna(0)

    # Derived features

    df["customer_age_days"] = (
        pd.to_datetime(df["last_purchase_date"]) -
        pd.to_datetime(df["first_purchase_date"])
    ).dt.days.fillna(0)
 
    df["orders_per_month"] = np.where(
        df["customer_age_days"] > 0,
        df["frequency"] / (df["customer_age_days"] / 30),
        df["frequency"]
    ).round(4)
 
    df["revenue_per_day"] = np.where(
        df["customer_age_days"] > 0,
        df["monetary"] / df["customer_age_days"],
        df["monetary"]
    ).round(4)
 
    # Churn label: last purchase > 180 days ago = churned
    threshold = df["recency_days"].quantile(0.75)
    df["churned"] = (df["recency_days"] > threshold).astype(int)
 
    print(f"Feature matrix: {df.shape[0]:,} customers | "
          f"churn rate {df['churned'].mean():.1%}")
    return df


def get_rfm_segments(df: pd.DataFrame) -> pd.DataFrame:

    """Add RFM quintile scores (1–5) and business segment labels."""
    df = df.copy()
    df["r_score"] = pd.qcut(df["recency_days"],             q=5, labels=[5,4,3,2,1]).astype(int)
    df["f_score"] = pd.qcut(df["frequency"].rank(method="first"), q=5, labels=[1,2,3,4,5]).astype(int)
    df["m_score"] = pd.qcut(df["monetary"].rank(method="first"),  q=5, labels=[1,2,3,4,5]).astype(int)
 
    def _label(row):
        r, f, m = row["r_score"], row["f_score"], row["m_score"]
        if   r >= 4 and f >= 4:  return "Champions"
        elif r >= 3 and f >= 3:  return "Loyal Customers"
        elif r >= 4 and f <= 2:  return "Recent Customers"
        elif r >= 3 and f <= 2:  return "Potential Loyalists"
        elif r <= 2 and f >= 3:  return "At Risk"
        elif r <= 2 and m >= 4:  return "Cannot Lose Them"
        elif r == 1 and f == 1:  return "Lost"
        else:                    return "Needs Attention"
 
    df["rfm_segment"] = df.apply(_label, axis=1)
    return df


#  Constants used by model training files 
 
FEATURE_COLS = [
    "recency_days",
    "frequency",
    "monetary",
    "avg_order_value",
    "max_order_value",
    "min_order_value",
    "std_order_value",
    "review_count",
    "avg_review_score",
    "unique_categories",
    "customer_age_days",
    "orders_per_month",
    "revenue_per_day",
]
 
CHURN_TARGET = "churned"
CLV_TARGET   = "monetary"

