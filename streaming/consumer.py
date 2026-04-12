"""
─────────────────────
Kafka consumer — reads from 'live_orders' topic
and writes batches to the streaming_orders table in PostgreSQL.

HOW TO RUN (in a separate CMD window while producer is running):
  conda activate ecom
  python streaming\consumer.py

"""

import json
import pandas as pd
from kafka import KafkaConsumer
from datetime import datetime
from src.db import engine

TOPIC  = "live_orders"
BROKER = "localhost:9092"
GROUP  = "ecommerce-analytics"
BATCH  = 10      # write to DB every N messages


def run():
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=[BROKER],
        group_id=GROUP,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    print(f"Listening on '{TOPIC}' — Ctrl+C to stop.\n")

    buffer = []
    total  = 0
    try:
        for msg in consumer:
            o = msg.value
            buffer.append({
                "order_id":         o.get("order_id"),
                "product_category": o.get("product_category"),
                "order_value":      o.get("order_value", 0),
                "freight_value":    o.get("freight_value", 0),
                "state":            o.get("state"),
                "payment_type":     o.get("payment_type"),
                "review_score":     o.get("review_score"),
                "event_timestamp":  o.get("timestamp"),
            })
            if len(buffer) >= BATCH:
                pd.DataFrame(buffer).to_sql(
                    "streaming_orders", engine,
                    if_exists="append", index=False, method="multi"
                )
                total  += len(buffer)
                buffer  = []
                print(f"  Flushed {BATCH} events to DB | Total: {total:,}")
    except KeyboardInterrupt:
        if buffer:
            pd.DataFrame(buffer).to_sql(
                "streaming_orders", engine,
                if_exists="append", index=False, method="multi"
            )
            total += len(buffer)
        print(f"\nStopped. Total events written: {total:,}")
    finally:
        consumer.close()


if __name__ == "__main__":
    run()