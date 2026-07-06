"""
Orchestrateur local des pipelines Bronze.

UN SEUL pipeline dlt, chemin DuckDB absolu passé directement dans l'objet
destination (duckdb_destination) — aucune env var, aucun cache consulté.

Usage :
    python -m dlt_pipelines.pipelines.run_all_bronze
    python -m dlt_pipelines.pipelines.run_all_bronze --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import dlt
import duckdb
from dlt.destinations import duckdb as duckdb_destination

from dlt_pipelines.config import DATASET_NAME
from dlt_pipelines.sources.exchange_rates import exchange_rates_source
from dlt_pipelines.sources.olist_csv import olist_csv_source
from dlt_pipelines.sources.olist_json import olist_json_source

# Chemin absolu calculé depuis l'emplacement de CE fichier.
# Intentionnellement après les imports : Path(__file__) est résolu à l'exécution,
# aucune dépendance avec les imports locaux ci-dessus.
# run_all_bronze.py → pipelines/ → dlt_pipelines/ → mlops-dataops-platform/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DUCKDB_ABSOLUTE_PATH = str(_PROJECT_ROOT / "warehouse" / "duckdb" / "olist.duckdb")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("run_all_bronze")


@dataclass
class ResourceResult:
    name: str
    table: str
    success: bool
    rows: int = 0
    elapsed_s: float = 0.0
    error: str = ""


def _count_rows(table: str) -> int:
    """Connexion read-only, COUNT, fermeture immédiate."""
    try:
        con = duckdb.connect(DUCKDB_ABSOLUTE_PATH, read_only=True)
        n = con.execute(f'SELECT COUNT(*) FROM bronze."{table}"').fetchone()[0]
        con.close()
        return n
    except Exception as exc:
        log.warning("Count failed for %s: %s", table, exc)
        return -1


def _make_pipeline() -> dlt.Pipeline:
    """
    Crée le pipeline dlt avec le chemin DuckDB absolu injecté directement
    dans l'objet duckdb_destination — aucune résolution par env var ni état.
    """
    dest = duckdb_destination(credentials=DUCKDB_ABSOLUTE_PATH)
    pipeline = dlt.pipeline(
        pipeline_name="bronze_olist",
        destination=dest,
        dataset_name=DATASET_NAME,
    )
    # Vérification immédiate du chemin résolu
    log.info("Pipeline name      : %s", pipeline.pipeline_name)
    log.info("Destination type   : %s", type(dest).__name__)
    log.info("DuckDB path (abs)  : %s", DUCKDB_ABSOLUTE_PATH)
    log.info("Path exists now    : %s", Path(DUCKDB_ABSOLUTE_PATH).exists())
    return pipeline


def run_all(dry_run: bool = False) -> list[ResourceResult]:
    batch_id = str(uuid.uuid4())
    log.info("=" * 60)
    log.info("Bronze ingestion -- batch_id=%s", batch_id)
    log.info("DuckDB absolute   : %s", DUCKDB_ABSOLUTE_PATH)
    log.info("Dry run           : %s", dry_run)
    log.info("=" * 60)

    if dry_run:
        log.info("[DRY-RUN] no data written.")
        return []

    csv_src  = olist_csv_source(batch_id=batch_id)
    json_src = olist_json_source(batch_id=batch_id)
    exch_src = exchange_rates_source(batch_id=batch_id)

    tasks: list[tuple[str, object, str]] = [
        ("customers",            csv_src.raw_customers,            "raw_customers"),
        ("orders",               csv_src.raw_orders,               "raw_orders"),
        ("order_items",          csv_src.raw_order_items,          "raw_order_items"),
        ("payments",             csv_src.raw_payments,             "raw_payments"),
        ("reviews",              csv_src.raw_reviews,              "raw_reviews"),
        ("products",             csv_src.raw_products,             "raw_products"),
        ("sellers",              csv_src.raw_sellers,              "raw_sellers"),
        ("geolocation",          csv_src.raw_geolocation,          "raw_geolocation"),
        ("category_translation", csv_src.raw_category_translation, "raw_category_translation"),
        ("products_json",        json_src.raw_products_json,       "raw_products_json"),
        ("exchange_rates",       exch_src.raw_exchange_rates,      "raw_exchange_rates"),
    ]

    pipeline = _make_pipeline()

    results: list[ResourceResult] = []
    for label, resource, table_name in tasks:
        log.info(">> Loading %s ...", label)
        t0 = time.perf_counter()
        res = ResourceResult(name=label, table=table_name, success=False)
        try:
            pipeline.run(resource)
            res.elapsed_s = round(time.perf_counter() - t0, 2)
            res.success = True
            log.info("   [OK] %s -- %.2fs", label, res.elapsed_s)
        except Exception as exc:
            res.elapsed_s = round(time.perf_counter() - t0, 2)
            res.error = str(exc)
            log.error("   [FAIL] %s -- %s", label, exc)
        results.append(res)

    return results


def _print_summary(results: list[ResourceResult]) -> None:
    log.info("=" * 65)
    log.info("SUMMARY")
    log.info("%-30s %-6s %12s %8s", "Resource", "Status", "Rows (DB)", "Time(s)")
    log.info("-" * 65)
    failures = 0
    for r in results:
        status = "OK  " if r.success else "FAIL"
        if r.success:
            r.rows = _count_rows(r.table)
        log.info("%-30s %-6s %12d %8.2f", r.name, status, r.rows, r.elapsed_s)
        if not r.success:
            failures += 1
            log.error("    -> %s", r.error)
    log.info("-" * 65)
    log.info("Failures : %d / %d", failures, len(results))
    log.info("=" * 65)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    results = run_all(dry_run=args.dry_run)
    _print_summary(results)
    sys.exit(sum(1 for r in results if not r.success))
