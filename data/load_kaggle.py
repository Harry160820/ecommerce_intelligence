"""
Downloads the Olist Brazilian E-commerce dataset from Kaggle.
Saves temporarily to C:\Temp\olist (cleaned up when you want).
Loads all 9 tables into PostgreSQL — no permanent CSV files on your Desktop.

PREREQUISITES:
  1. .env must contain valid KAGGLE_USERNAME and KAGGLE_KEY
  2. sql\01_schema.sql must already be run (tables must exist)
"""

import os
import glob
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text
from src.db import engine

load_dotenv()

os.environ["KAGGLE_USERNAME"] = os.getenv("KAGGLE_USERNAME", "")
os.environ["KAGGLE_KEY"]      = os.getenv("KAGGLE_KEY", "")

DATASET       = "olistbr/brazilian-ecommerce"
DOWNLOAD_PATH = r"C:\Temp\olist"


#  Helpers 

def check_credentials():
    u = os.getenv("KAGGLE_USERNAME", "")
    k = os.getenv("KAGGLE_KEY", "")
    if not u or u == "your_kaggle_username":
        raise ValueError(
            "KAGGLE_USERNAME missing from .env\n"
            "Go to kaggle.com > Account > Create New API Token"
        )
    if not k or k == "your_kaggle_api_key":
        raise ValueError("KAGGLE_KEY missing from .env")
    print(f"Kaggle credentials OK  (user: {u})")


def download_dataset():
    from kaggle.api.kaggle_api_extended import KaggleApi
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    api = KaggleApi()
    api.authenticate()
    print(f"\nDownloading {DATASET} ...")
    api.dataset_download_files(DATASET, path=DOWNLOAD_PATH, unzip=True, quiet=False)
    print("Download complete.\n")


def load_raw_tables():
    """Load each CSV into a raw_* staging table in PostgreSQL."""
    files = glob.glob(os.path.join(DOWNLOAD_PATH, "*.csv"))
    if not files:
        raise FileNotFoundError(
            f"No CSV files found in {DOWNLOAD_PATH}\n"
            "Call download_dataset() first."
        )

    name_map = {
        "olist_customers_dataset":            "raw_customers",
        "olist_sellers_dataset":              "raw_sellers",
        "olist_products_dataset":             "raw_products",
        "olist_orders_dataset":               "raw_orders",
        "olist_order_items_dataset":          "raw_order_items",
        "olist_order_payments_dataset":       "raw_payments",
        "olist_order_reviews_dataset":        "raw_reviews",
        "olist_geolocation_dataset":          "raw_geolocation",
        "product_category_name_translation":  "raw_category_translation",
    }

    loaded = {}
    print("Loading CSVs into PostgreSQL raw tables:")
    for path in sorted(files):
        stem  = os.path.splitext(os.path.basename(path))[0]
        tname = name_map.get(stem, f"raw_{stem}")

        df = pd.read_csv(path, low_memory=False)

        # Parse date/timestamp columns automatically
        for col in df.columns:
            if "date" in col.lower() or "timestamp" in col.lower():
                df[col] = pd.to_datetime(df[col], errors="coerce")

        df.to_sql(tname, engine, if_exists="replace", index=False,
                  method="multi", chunksize=1000)
        print(f"  {tname:<38} {len(df):>10,} rows")
        loaded[stem] = df

    return loaded


def build_clean_tables():
    """
    Transform raw staging tables into the clean star-schema tables
    defined in sql\01_schema.sql using INSERT ... SELECT.
    """
    print("\nBuilding clean tables ...")

    with engine.begin() as c:

        c.execute(text("""
            INSERT INTO dim_customers
                (customer_id, customer_unique_id, zip_code, city, state)
            SELECT customer_id, customer_unique_id,
                   customer_zip_code_prefix::VARCHAR,
                   customer_city, customer_state
            FROM raw_customers
            ON CONFLICT (customer_id) DO NOTHING
        """))
        print("  dim_customers      OK")

        c.execute(text("""
            INSERT INTO dim_sellers (seller_id, zip_code, city, state)
            SELECT seller_id,
                   seller_zip_code_prefix::VARCHAR,
                   seller_city, seller_state
            FROM raw_sellers
            ON CONFLICT (seller_id) DO NOTHING
        """))
        print("  dim_sellers        OK")

        c.execute(text("""
            INSERT INTO dim_products
                (product_id, category_name_english, name_length,
                 description_length, photos_qty,
                 weight_g, length_cm, height_cm, width_cm)
            SELECT
                p.product_id,
                COALESCE(t.product_category_name_english,
                         p.product_category_name),
                p.product_name_lenght,
                p.product_description_lenght,
                p.product_photos_qty,
                p.product_weight_g,
                p.product_length_cm,
                p.product_height_cm,
                p.product_width_cm
            FROM raw_products p
            LEFT JOIN raw_category_translation t
                ON t.product_category_name = p.product_category_name
            ON CONFLICT (product_id) DO NOTHING
        """))
        print("  dim_products       OK")

        c.execute(text("""
            INSERT INTO dim_date
                (date_key, year, quarter, month, month_name, week, day_of_week, is_weekend)
            SELECT DISTINCT
                order_purchase_timestamp::DATE,
                EXTRACT(YEAR    FROM order_purchase_timestamp),
                EXTRACT(QUARTER FROM order_purchase_timestamp),
                EXTRACT(MONTH   FROM order_purchase_timestamp),
                TO_CHAR(order_purchase_timestamp, 'Month'),
                EXTRACT(WEEK    FROM order_purchase_timestamp),
                EXTRACT(DOW     FROM order_purchase_timestamp),
                EXTRACT(DOW     FROM order_purchase_timestamp) IN (0,6)
            FROM raw_orders
            WHERE order_purchase_timestamp IS NOT NULL
            ON CONFLICT (date_key) DO NOTHING
        """))
        print("  dim_date           OK")

        c.execute(text("""
            INSERT INTO fact_orders
                (order_id, customer_id, order_status, purchase_date,
                 approved_date, delivered_carrier_date,
                 delivered_customer_date, estimated_delivery_date,
                 purchase_date_key)
            SELECT order_id, customer_id, order_status,
                order_purchase_timestamp::timestamp,
                order_approved_at::timestamp,
                order_delivered_carrier_date::timestamp,
                order_delivered_customer_date::timestamp,
                order_estimated_delivery_date::timestamp,
                order_purchase_timestamp::DATE
            FROM raw_orders
            ON CONFLICT (order_id) DO NOTHING
        """))
        print("  fact_orders        OK")

        c.execute(text("""
            INSERT INTO fact_order_items
                (order_id, product_id, seller_id, shipping_date, price, freight_value)
            SELECT order_id, product_id, seller_id,
                   shipping_limit_date, price, freight_value
            FROM raw_order_items
        """))
        print("  fact_order_items   OK")

        c.execute(text("""
            INSERT INTO fact_payments
                (order_id, payment_sequential, payment_type, installments, payment_value)
            SELECT order_id, payment_sequential, payment_type,
                   payment_installments, payment_value
            FROM raw_payments
        """))
        print("  fact_payments      OK")

        c.execute(text("""
            INSERT INTO fact_reviews
                (review_id, order_id, review_score, review_created_date, answer_date)
            SELECT review_id, order_id, review_score,
                   review_creation_date, review_answer_timestamp
            FROM raw_reviews
            ON CONFLICT (review_id) DO NOTHING
        """))
        print("  fact_reviews       OK")


def print_summary():
    tables = ["dim_customers","dim_sellers","dim_products","dim_date",
              "fact_orders","fact_order_items","fact_payments","fact_reviews"]
    print("\n Final row counts ")
    with engine.connect() as conn:
        for t in tables:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"  {t:<28} {n:>10,}")
    print("───────────────────────────────────────────────────")


if __name__ == "__main__":
    print("=" * 52)
    print("  OLIST DATA LOADER")
    print("=" * 52)
    check_credentials()
    download_dataset()
    load_raw_tables()
    build_clean_tables()
    print_summary()
    print("\nAll data loaded successfully!")