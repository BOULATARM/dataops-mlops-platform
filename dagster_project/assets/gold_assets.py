"""
Assets Dagster pour la couche Gold.

Un seul asset `gold_layer` qui exécute `dbt build --select tag:gold`.
Même stratégie anti-verrou que silver_assets.py.
"""

import subprocess
import os
from pathlib import Path

from dagster import asset, AssetExecutionContext, Output, MetadataValue

from dagster_project.assets.silver_assets import silver_layer

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DBT_DIR = _PROJECT_ROOT / "dbt_project"
_DB_PATH = str(_PROJECT_ROOT / "warehouse" / "duckdb" / "olist.duckdb")


def _dbt_build(select: str, context: AssetExecutionContext) -> str:
    cmd = [
        "dbt", "build",
        "--profiles-dir", str(_DBT_DIR),
        "--project-dir", str(_DBT_DIR),
        "--select", select,
    ]
    env = {**os.environ, "DUCKDB_PATH": _DB_PATH, "PYTHONIOENCODING": "utf-8"}
    context.log.info(f"dbt build --select {select}")

    result = subprocess.run(cmd, capture_output=True, env=env, cwd=str(_DBT_DIR))
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")

    if stdout:
        context.log.info(stdout[-5000:])
    if result.returncode != 0:
        context.log.error(stderr[-2000:])
        raise RuntimeError(f"dbt build failed (exit {result.returncode}) for selector '{select}'")
    return stdout


def _row_counts(tables: list[tuple[str, str]]) -> dict:
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
# Asset Gold — couche complète en un seul appel dbt
# ---------------------------------------------------------------------------

@asset(
    group_name="gold",
    description=(
        "Marts métier et feature store ML : gold_orders_summary, "
        "gold_customer_rfm, gold_product_performance, gold_seller_ranking, "
        "gold_reviews_features. Exécute dbt build --select tag:gold."
    ),
    deps=[silver_layer],
    kinds={"dbt", "duckdb"},
)
def gold_layer(context: AssetExecutionContext):
    _dbt_build("tag:gold", context)

    counts = _row_counts([
        ("main_gold", "gold_orders_summary"),
        ("main_gold", "gold_customer_rfm"),
        ("main_gold", "gold_product_performance"),
        ("main_gold", "gold_seller_ranking"),
        ("main_gold", "gold_reviews_features"),
    ])

    metadata = {
        f"rows_{t}": MetadataValue.int(n) for t, n in counts.items()
    }
    metadata["models_built"] = MetadataValue.int(5)

    context.log.info("Gold layer OK — " + ", ".join(f"{t}:{n:,}" for t, n in counts.items()))
    return Output(value=None, metadata=metadata)


GOLD_ASSETS = [gold_layer]
