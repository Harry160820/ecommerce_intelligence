"""
Simulates live e-commerce orders using Faker (Brazilian locale).
Sends each event to:
  1. Kafka topic 'live_orders'          (internal consumers)
  2. Power BI REST streaming endpoint   (real-time dashboard tile)
 
HOW TO RUN (Kafka must be started first — see README):
  conda activate ecom
  python streaming\producer.py
 
STOP: press Ctrl + C
"""
# C:\Users\dell\OneDrive\Desktop\ecommerce_intelligence\streaming\producer.py
import os
import json
import time 
import random
import requests
from datetime import datetime
from dotenv import load_dotenv
from faker import Faker
from kafka import KafkaProducer

from kafka.errors import NoBrokersAvailable


load_dotenv()  # Load environment variables from .env file

fake = Faker('pt_BR')  # Brazilian Portuguese locale
TOPIC = "live_orders"
BROKER = "localhost:9092"
PBI_URL = os.getenv("POWERBI_PUSH_URL", "")


CATEGORIES = [
    "electronics", "furniture_decor", "health_beauty",
    "sports_leisure", "computers_accessories", "toys",
    "watches_gifts", "telephony", "auto", "housewares",
    "bed_bath_table", "food_drink",
]

STATES = ["SP","RJ","MG","RS","PR","SC","BA","GO","PE","CE","DF","ES"]
STATE_WEIGHTS = [35,15,12,8,7,6,4,3,3,2,2,3]

PRICE_RANGES = {
    "electronics":           (150, 3500),
    "computers_accessories": (80,  2500),
    "telephony":             (100, 2000),
    "furniture_decor":       (50,  1200),
    "health_beauty":         (20,   300),
    "sports_leisure":        (30,   800),
    "watches_gifts":         (60,  1500),
    "toys":                  (20,   400),
}

def generate_order() -> dict:
    """Generates a random e-commerce order event."""
    cat      = random.choice(CATEGORIES)
    lo, hi   = PRICE_RANGES.get(cat, (20, 500))
    price    = round(random.uniform(lo, hi), 2)
    items    = random.choices([1,2,3,4], weights=[65,20,10,5])[0]
    state    = random.choices(STATES, weights=STATE_WEIGHTS)[0]
    return {
        "order_id":         fake.uuid4(),
        "product_category": cat,
        "items":            items,
        "order_value":      round(price * items, 2),
        "freight_value":    round(random.uniform(8, min(price * 0.3, 120)), 2),
        "state":            state,
        "payment_type":     random.choice(["credit_card","boleto","debit_card","voucher"]),
        "review_score":     random.choices([1,2,3,4,5], weights=[3,5,10,25,57])[0],
        "timestamp":        datetime.now().isoformat(),
    }


def push_to_powerbi(order: dict):
    if not PBI_URL or "YOUR_WORKSPACE" in PBI_URL:
        print("⚠️  Power BI URL not set. Skipping Power BI push.")
        return
    payload = [{
        "order_id":         order["order_id"],
        "product_category": order["product_category"],
        "order_value":      order["order_value"],
        "state":            order["state"],
        "payment_type":     order["payment_type"],
        "timestamp":        order["timestamp"],
    }]

    try:
        requests.post(PBI_URL, headers={"Content-Type":"application/json"},
                      data=json.dumps(payload), timeout=5)
        

    except Exception:
        pass

def run(interval_min=0.5, interval_max=2.0):
    # Connect to Kafka with retries
    producer = None
    for attempt in range(5):
        try:
            producer = KafkaProducer(
                bootstrap_servers=[BROKER],
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
            )
            print(f"Connected to Kafka at {BROKER}")
            break
        except NoBrokersAvailable:
            print(f"Kafka not available (attempt {attempt+1}/5). Retrying in 3 s ...")
            time.sleep(3)
 
    if producer is None:
        print("ERROR: Could not connect to Kafka.")
        print("Make sure Kafka is running (see README for Windows Kafka start commands).")
        return
 
    pbi_status = "enabled" if (PBI_URL and "YOUR_WORKSPACE" not in PBI_URL) else "not configured"
    print(f"Power BI push: {pbi_status}")
    print(f"Streaming to topic '{TOPIC}' — Ctrl+C to stop.\n")
 
    count = 0
    total = 0.0
    try:
        while True:
            order = generate_order()
            producer.send(TOPIC, order)
            producer.flush()
            push_to_powerbi(order)
 
            count += 1
            total += order["order_value"]
            print(f"[{count:>5}] {order['timestamp'][11:19]}  "
                  f"{order['product_category']:<25}  "
                  f"R${order['order_value']:>8.2f}  "
                  f"{order['state']}  {order['payment_type']}")
 
            time.sleep(random.uniform(interval_min, interval_max))
 
    except KeyboardInterrupt:
        print(f"\nStopped.  Events: {count:,}  |  Total R${total:,.2f}")
    finally:
        producer.close()
 
 
if __name__ == "__main__":
    run()

    

