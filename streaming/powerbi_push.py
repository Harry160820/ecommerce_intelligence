"""
Push test events directly to Power BI streaming dataset
without needing Kafka. Use this to test your PBI live tile.

HOW TO RUN:
  python streaming\powerbi_push.py --mode test    (sends 20 events)
  python streaming\powerbi_push.py --mode live    (streams continuously)

REQUIREMENT: Set POWERBI_PUSH_URL in your .env file first.
"""

import os
import json
import time
import random
import argparse
import requests
from datetime import datetime
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

fake    = Faker("pt_BR")
PBI_URL = os.getenv("POWERBI_PUSH_URL", "")

CATEGORIES = ["electronics","furniture_decor","health_beauty",
              "sports_leisure","computers_accessories","toys"]
STATES     = ["SP","RJ","MG","RS","PR","SC","BA"]


def _event():
    return {
        "order_id":         fake.uuid4()[:8],
        "product_category": random.choice(CATEGORIES),
        "order_value":      round(random.uniform(30, 800), 2),
        "state":            random.choice(STATES),
        "payment_type":     random.choice(["credit_card","boleto","debit_card"]),
        "timestamp":        datetime.now().isoformat(),
    }


def _push(ev: dict) -> bool:
    if not PBI_URL or "YOUR_WORKSPACE" in PBI_URL:
        print("  POWERBI_PUSH_URL not set in .env — skipping push.")
        return False
    r = requests.post(PBI_URL,
                      headers={"Content-Type":"application/json"},
                      data=json.dumps([ev]), timeout=10)
    return r.status_code == 200


def test_mode(n=20):
    print(f"Sending {n} test events ...")
    ok = 0
    for i in range(n):
        ev     = _event()
        status = "OK  " if _push(ev) else "FAIL"
        ok    += (status == "OK  ")
        print(f"  [{i+1:>3}/{n}] {status} | "
              f"{ev['product_category']:<25} R${ev['order_value']}")
        time.sleep(0.3)
    print(f"\nResult: {ok}/{n} pushed successfully.")


def live_mode(interval=1.5):
    print("Live mode — Ctrl+C to stop.")
    count = 0
    try:
        while True:
            ev     = _event()
            status = "OK  " if _push(ev) else "FAIL"
            count += 1
            print(f"[{count:>4}] {status} | {ev['state']} | "
                  f"{ev['product_category']:<25} R${ev['order_value']}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\nStopped after {count} events.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode",     choices=["test","live"], default="test")
    ap.add_argument("--n",        type=int,   default=20)
    ap.add_argument("--interval", type=float, default=1.5)
    args = ap.parse_args()
    if args.mode == "test":
        test_mode(args.n)
    else:
        live_mode(args.interval)