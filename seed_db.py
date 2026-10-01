import random
import sqlite3
from datetime import date, timedelta

DB_PATH = "retail.db"

CATEGORIES = ["Beverages", "Snacks", "Household", "Personal Care", "Frozen Foods"]
REGIONS = ["Bangkok", "Chiang Mai", "Phuket", "Khon Kaen"]

random.seed(7)


def build():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript(
        """
        DROP TABLE IF EXISTS sales;
        DROP TABLE IF EXISTS products;

        CREATE TABLE products (
            sku TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            unit_price REAL NOT NULL
        );

        CREATE TABLE sales (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL REFERENCES products(sku),
            region TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            returned INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    products = []
    for i in range(1, 41):
        category = random.choice(CATEGORIES)
        sku = f"SKU-{1000 + i}"
        products.append((sku, f"{category[:-1]} Item {i}", category, round(random.uniform(15, 450), 2)))
    cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", products)

    start = date(2026, 1, 1)
    rows = []
    for _ in range(2000):
        sku = random.choice(products)[0]
        region = random.choice(REGIONS)
        qty = random.randint(1, 12)
        day = start + timedelta(days=random.randint(0, 270))
        returned = 1 if random.random() < 0.06 else 0
        rows.append((sku, region, qty, day.isoformat(), returned))
    cur.executemany(
        "INSERT INTO sales (sku, region, quantity, order_date, returned) VALUES (?, ?, ?, ?, ?)", rows
    )

    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH}: {len(products)} products, {len(rows)} sales rows")


if __name__ == "__main__":
    build()
