"""
Assets Dagster pour la couche Bronze.

Chaque asset appelle la source dlt correspondante.
On ne duplique PAS la logique d'ingestion depuis dlt_pipelines/.
DUCKDB_PATH env var prioritaire sur le chemin local calcule depuis __file__.
"""

import os
from pathlib import Path

from dagster import asset, AssetExecutionContext, Output, MetadataValue

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_path() -> str:
    return os.environ.get("DUCKDB_PATH") or str(
        _PROJECT_ROOT / "warehouse" / "duckdb" / "olist.duckdb"
    )


def _get_pipeline():
    """Pipeline dlt bronze avec chemin DuckDB absolu (env var ou calcule)."""
    import dlt
    from dlt.destinations import duckdb as duckdb_destination

    return dlt.pipeline(
        pipeline_name="bronze_olist",
        destination=duckdb_destination(credentials=_get_db_path()),
        dataset_name="bronze",
    )


def _row_count(schema: str, table: str) -> int:
    import duckdb
    con = duckdb.connect(_get_db_path(), read_only=True)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Assets CSV
# ---------------------------------------------------------------------------

@asset(
    group_name="bronze",
    description="Ingestion CSV olist_customers_dataset.csv vers bronze.raw_customers",
    kinds={"dlt", "duckdb"},
)
def bronze_raw_customers(context: AssetExecutionContext):
    from dlt_pipelines.sources.olist_csv import olist_csv_source
    info = _get_pipeline().run(olist_csv_source().raw_customers, write_disposition="append")
    context.log.info(str(info))
    n = _row_count("bronze", "raw_customers")
    return Output(value=None, metadata={"row_count": MetadataValue.int(n)})


@asset(
    group_name="bronze",
    description="Ingestion CSV olist_orders_dataset.csv vers bronze.raw_orders",
    kinds={"dlt", "duckdb"},
)
def bronze_raw_orders(context: AssetExecutionContext):
    from dlt_pipelines.sources.olist_csv import olist_csv_source
    info = _get_pipeline().run(olist_csv_source().raw_orders, write_disposition="append")
    context.log.info(str(info))
    n = _row_count("bronze", "raw_orders")
    return Output(value=None, metadata={"row_count": MetadataValue.int(n)})


@asset(
    group_name="bronze",
    description="Ingestion CSV olist_order_items_dataset.csv vers bronze.raw_order_items",
    kinds={"dlt", "duckdb"},
)
def bronze_raw_order_items(context: AssetExecutionContext):
    from dlt_pipelines.sources.olist_csv import olist_csv_source
    info = _get_pipeline().run(olist_csv_source().raw_order_items, write_disposition="append")
    context.log.info(str(info))
    n = _row_count("bronze", "raw_order_items")
    return Output(value=None, metadata={"row_count": MetadataValue.int(n)})


@asset(
    group_name="bronze",
    description="Ingestion CSV olist_order_payments_dataset.csv vers bronze.raw_payments",
    kinds={"dlt", "duckdb"},
)
def bronze_raw_payments(context: AssetExecutionContext):
    from dlt_pipelines.sources.olist_csv import olist_csv_source
    info = _get_pipeline().run(olist_csv_source().raw_payments, write_disposition="append")
    context.log.info(str(info))
    n = _row_count("bronze", "raw_payments")
    return Output(value=None, metadata={"row_count": MetadataValue.int(n)})


@asset(
    group_name="bronze",
    description="Ingestion CSV olist_order_reviews_dataset.csv vers bronze.raw_reviews",
    kinds={"dlt", "duckdb"},
)
def bronze_raw_reviews(context: AssetExecutionContext):
    from dlt_pipelines.sources.olist_csv import olist_csv_source
    info = _get_pipeline().run(olist_csv_source().raw_reviews, write_disposition="append")
    context.log.info(str(info))
    n = _row_count("bronze", "raw_reviews")
    return Output(value=None, metadata={"row_count": MetadataValue.int(n)})


@asset(
    group_name="bronze",
    description="Ingestion CSV olist_products_dataset.csv vers bronze.raw_products",
    kinds={"dlt", "duckdb"},
)
def bronze_raw_products(context: AssetExecutionContext):
    from dlt_pipelines.sources.olist_csv import olist_csv_source
    info = _get_pipeline().run(olist_csv_source().raw_products, write_disposition="append")
    context.log.info(str(info))
    n = _row_count("bronze", "raw_products")
    return Output(value=None, metadata={"row_count": MetadataValue.int(n)})


@asset(
    group_name="bronze",
    description="Ingestion CSV olist_sellers_dataset.csv vers bronze.raw_sellers",
    kinds={"dlt", "duckdb"},
)
def bronze_raw_sellers(context: AssetExecutionContext):
    from dlt_pipelines.sources.olist_csv import olist_csv_source
    info = _get_pipeline().run(olist_csv_source().raw_sellers, write_disposition="append")
    context.log.info(str(info))
    n = _row_count("bronze", "raw_sellers")
    return Output(value=None, metadata={"row_count": MetadataValue.int(n)})


@asset(
    group_name="bronze",
    description="Ingestion CSV olist_geolocation_dataset.csv vers bronze.raw_geolocation",
    kinds={"dlt", "duckdb"},
)
def bronze_raw_geolocation(context: AssetExecutionContext):
    from dlt_pipelines.sources.olist_csv import olist_csv_source
    info = _get_pipeline().run(olist_csv_source().raw_geolocation, write_disposition="append")
    context.log.info(str(info))
    n = _row_count("bronze", "raw_geolocation")
    return Output(value=None, metadata={"row_count": MetadataValue.int(n)})


@asset(
    group_name="bronze",
    description="Ingestion CSV product_category_name_translation.csv vers bronze.raw_category_translation",
    kinds={"dlt", "duckdb"},
)
def bronze_raw_category_translation(context: AssetExecutionContext):
    from dlt_pipelines.sources.olist_csv import olist_csv_source
    info = _get_pipeline().run(olist_csv_source().raw_category_translation, write_disposition="append")
    context.log.info(str(info))
    n = _row_count("bronze", "raw_category_translation")
    return Output(value=None, metadata={"row_count": MetadataValue.int(n)})


# ---------------------------------------------------------------------------
# Assets JSON
# ---------------------------------------------------------------------------

@asset(
    group_name="bronze",
    description="Ingestion JSON products_sample.json vers bronze.raw_products_json",
    kinds={"dlt", "duckdb"},
)
def bronze_raw_products_json(context: AssetExecutionContext):
    from dlt_pipelines.sources.olist_json import olist_json_source
    info = _get_pipeline().run(olist_json_source().raw_products_json, write_disposition="append")
    context.log.info(str(info))
    n = _row_count("bronze", "raw_products_json")
    return Output(value=None, metadata={"row_count": MetadataValue.int(n)})


@asset(
    group_name="bronze",
    description="Ingestion JSON exchange_rates*.json vers bronze.raw_exchange_rates",
    kinds={"dlt", "duckdb"},
)
def bronze_raw_exchange_rates(context: AssetExecutionContext):
    from dlt_pipelines.sources.exchange_rates import exchange_rates_source
    info = _get_pipeline().run(exchange_rates_source().raw_exchange_rates, write_disposition="append")
    context.log.info(str(info))
    n = _row_count("bronze", "raw_exchange_rates")
    return Output(value=None, metadata={"row_count": MetadataValue.int(n)})


BRONZE_ASSETS = [
    bronze_raw_customers,
    bronze_raw_orders,
    bronze_raw_order_items,
    bronze_raw_payments,
    bronze_raw_reviews,
    bronze_raw_products,
    bronze_raw_sellers,
    bronze_raw_geolocation,
    bronze_raw_category_translation,
    bronze_raw_products_json,
    bronze_raw_exchange_rates,
]
