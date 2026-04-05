"""
Single database connection point for the entire project.
Every other file imports get_engine() or engine from here.
Credentials come from .env — never hardcoded anywhere.
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv() # reads .env from the project root

def get_engine():
    """Return a SQLAlchemy engine using DB_URL from .env"""
    url = os.getenv("DB_URL")
    if not url:
        raise EnvironmentError(
            "\nDB_URL not found in .env\n"
            "Make sure .env exists and contains:\n"
            "DB_URL=postgresql://postgres:Harry%40160820@localhost:5432/ecommerce"
        )
    return create_engine(url, pool_size=5, max_overflow=10)


def test_connection():
    """Quick health-check. Prints PostgreSQL version."""
    eng = get_engine()
    with eng.connect() as conn:
        ver = conn.execute(text("SELECT version();")).fetchone()[0]
        print("Connection OK")
        print(f"PostgreSQL: {ver[:50]}")

    return True

# One shared engine imported by every module
engine = get_engine()

if __name__ == "__main__":
    test_connection()

