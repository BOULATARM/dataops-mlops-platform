"""
Script d'extraction des fixtures CI depuis le DuckDB local.
Génère 100 commandes cohérentes (delivered) pour que dlt + dbt passent en CI.

Usage (depuis la racine du projet) :
    python -m tests.fixtures.make_fixtures
"""
import csv
import json
from pathlib import Path

import duckdb

FIXTURE_DIR = Path(__file__).resolve().parent
DB = str(Path(__file__).resolve().parent.parent.parent / "warehouse" / "duckdb" / "olist.duckdb")


def _cols(con, table):
    return [d[0] for d in con.execute(f"SELECT * FROM {table} LIMIT 0").description]


def export_csv(con, query, filename):
    rows = con.execute(query).fetchall()
    cols = [d[0] for d in con.execute(f"SELECT * FROM ({query}) _t LIMIT 0").description]
    path = FIXTURE_DIR / "csv" / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f"  {filename}: {len(rows)} rows")


def main():
    (FIXTURE_DIR / "csv").mkdir(parents=True, exist_ok=True)
    (FIXTURE_DIR / "json").mkdir(parents=True, exist_ok=True)
    (FIXTURE_DIR / "api").mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(DB, read_only=True)

    # 100 order_ids avec toutes les tables jointes non-nulles
    order_ids = [r[0] for r in con.execute("""
        SELECT DISTINCT o.order_id
        FROM bronze.raw_orders o
        JOIN bronze.raw_order_items oi  ON o.order_id = oi.order_id
        JOIN bronze.raw_payments p      ON o.order_id = p.order_id
        JOIN bronze.raw_reviews r       ON o.order_id = r.order_id
        JOIN bronze.raw_customers c     ON o.customer_id = c.customer_id
        WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_estimated_delivery_date IS NOT NULL
        LIMIT 100
    """).fetchall()]

    print(f"Orders: {len(order_ids)}")
    oid = "'" + "','".join(order_ids) + "'"

    export_csv(con, f"SELECT * FROM bronze.raw_orders WHERE order_id IN ({oid})",
               "olist_orders_dataset.csv")

    export_csv(con, f"""
        SELECT DISTINCT c.*
        FROM bronze.raw_customers c
        JOIN bronze.raw_orders o ON c.customer_id = o.customer_id
        WHERE o.order_id IN ({oid})
    """, "olist_customers_dataset.csv")

    export_csv(con, f"SELECT * FROM bronze.raw_order_items WHERE order_id IN ({oid})",
               "olist_order_items_dataset.csv")

    export_csv(con, f"SELECT * FROM bronze.raw_payments WHERE order_id IN ({oid})",
               "olist_order_payments_dataset.csv")

    export_csv(con, f"SELECT * FROM bronze.raw_reviews WHERE order_id IN ({oid})",
               "olist_order_reviews_dataset.csv")

    product_ids = [r[0] for r in con.execute(
        f"SELECT DISTINCT product_id FROM bronze.raw_order_items WHERE order_id IN ({oid})"
    ).fetchall()]
    pid = "'" + "','".join(product_ids) + "'"

    export_csv(con, f"SELECT * FROM bronze.raw_products WHERE product_id IN ({pid})",
               "olist_products_dataset.csv")

    seller_ids = [r[0] for r in con.execute(
        f"SELECT DISTINCT seller_id FROM bronze.raw_order_items WHERE order_id IN ({oid})"
    ).fetchall()]
    sid = "'" + "','".join(seller_ids) + "'"

    export_csv(con, f"SELECT * FROM bronze.raw_sellers WHERE seller_id IN ({sid})",
               "olist_sellers_dataset.csv")

    export_csv(con, "SELECT * FROM bronze.raw_category_translation",
               "product_category_name_translation.csv")

    export_csv(con, "SELECT * FROM bronze.raw_geolocation LIMIT 500",
               "olist_geolocation_dataset.csv")

    # JSON products_sample (5 produits des commandes sélectionnées)
    prod_cols = _cols(con, "bronze.raw_products")
    prods = con.execute(
        f"SELECT * FROM bronze.raw_products WHERE product_id IN ({pid}) LIMIT 5"
    ).fetchall()
    prod_list = [dict(zip(prod_cols, r)) for r in prods]
    with open(FIXTURE_DIR / "json" / "products_sample.json", "w", encoding="utf-8") as f:
        json.dump(prod_list, f, indent=2, default=str)
    print(f"  products_sample.json: {len(prod_list)} records")

    # Fixture exchange rates
    exch = {
        "base": "USD",
        "fetched_at": "2024-01-01T00:00:00Z",
        "rates": {"BRL": 4.97, "EUR": 0.92, "USD": 1.0, "GBP": 0.79},
    }
    with open(FIXTURE_DIR / "api" / "exchange_rates_fixture.json", "w", encoding="utf-8") as f:
        json.dump(exch, f, indent=2)
    print("  exchange_rates_fixture.json: 4 rates")

    con.close()
    print("Fixtures générés avec succès.")


if __name__ == "__main__":
    main()
