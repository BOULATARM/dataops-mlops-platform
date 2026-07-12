"""
Assets Dagster pour la couche Silver.

Un seul asset `silver_layer` qui exécute `dbt build --select tag:silver`.
Stratégie anti-verrou DuckDB : un seul processus dbt à la fois (pas de
parallélisme inter-modèles possible avec DuckDB en mode write).
"""

import os
import subprocess
from pathlib import Path

from dagster import AssetExecutionContext, MetadataValue, Output, asset

from dagster_project.assets.bronze_assets import (
    bronze_raw_category_translation,
    bronze_raw_customers,
    bronze_raw_exchange_rates,
    bronze_raw_geolocation,
    bronze_raw_order_items,
    bronze_raw_orders,
    bronze_raw_payments,
    bronze_raw_products,
    bronze_raw_products_json,
    bronze_raw_reviews,
    bronze_raw_sellers,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DBT_DIR = _PROJECT_ROOT / "dbt_project"
_DB_PATH = os.environ.get("DUCKDB_PATH") or str(
    _PROJECT_ROOT / "warehouse" / "duckdb" / "olist.duckdb"
)


def _dbt_build(select: str, context: AssetExecutionContext) -> str:
    """
    Exécute dbt build --select <select>.
    Retourne le stdout complet, lève RuntimeError si returncode != 0.
    """
    cmd = [
        "dbt", "build",
        "--profiles-dir", str(_DBT_DIR),
        "--project-dir", str(_DBT_DIR),
        "--select", select,
    ]
    env = {**os.environ, "DUCKDB_PATH": _DB_PATH, "PYTHONIOENCODING": "utf-8"}
    context.log.info(f"dbt build --select {select}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        # Ne pas décoder en text=True pour éviter UnicodeDecodeError sur Windows
        # On décode manuellement avec errors='replace'
        env=env,
        cwd=str(_DBT_DIR),
    )
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")

    if stdout:
        context.log.info(stdout[-5000:])
    if result.returncode != 0:
        context.log.error(stderr[-2000:])
        raise RuntimeError(f"dbt build failed (exit {result.returncode}) for selector '{select}'")
    return stdout


def _row_counts(tables: list[tuple[str, str]]) -> dict:
    """Retourne {table: n_rows} en read_only pour éviter le verrou."""
    import duckdb
    con = duckdb.connect(_DB_PATH, read_only=True)
    try:
        return {
            t: con.execute(f"SELECT COUNT(*) FROM {s}.{t}").fetchone()[0]
            for s, t in tables
        }
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Asset Silver — couche complète en un seul appel dbt
# ---------------------------------------------------------------------------

@asset(
    group_name="silver",
    description=(
        "Nettoyage, typage et déduplication : silver_orders, silver_customers, "
        "silver_products, silver_reviews, silver_payments, silver_sellers, "
        "silver_order_items. Exécute dbt build --select tag:silver."
    ),
    deps=[
        bronze_raw_orders,
        bronze_raw_customers,
        bronze_raw_order_items,
        bronze_raw_payments,
        bronze_raw_reviews,
        bronze_raw_products,
        bronze_raw_sellers,
        bronze_raw_category_translation,
        bronze_raw_exchange_rates,
        bronze_raw_products_json,
        bronze_raw_geolocation,
    ],
    kinds={"dbt", "duckdb"},
)
def silver_layer(context: AssetExecutionContext):
    _dbt_build("+tag:silver", context)

    counts = _row_counts([
        ("main_silver", "silver_orders"),
        ("main_silver", "silver_customers"),
        ("main_silver", "silver_products"),
        ("main_silver", "silver_reviews"),
        ("main_silver", "silver_payments"),
        ("main_silver", "silver_sellers"),
        ("main_silver", "silver_order_items"),
    ])

    metadata = {
        f"rows_{t}": MetadataValue.int(n) for t, n in counts.items()
    }
    metadata["models_built"] = MetadataValue.int(7)

    context.log.info("Silver layer OK — " + ", ".join(f"{t}:{n:,}" for t, n in counts.items()))
    return Output(value=None, metadata=metadata)


SILVER_ASSETS = [silver_layer]
