"""Pipeline Bronze — products (CSV Olist + JSON catalogue interne)."""

from __future__ import annotations

import logging
import uuid

import dlt

from dlt_pipelines.config import DATASET_NAME
from dlt_pipelines.sources.olist_csv import olist_csv_source
from dlt_pipelines.sources.olist_json import olist_json_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def run() -> dlt.Pipeline:
    batch_id = str(uuid.uuid4())

    # CSV produits Olist
    pipeline_csv = dlt.pipeline(
        pipeline_name="bronze_products_csv",
        destination="duckdb",
        dataset_name=DATASET_NAME,
    )
    source_csv = olist_csv_source(batch_id=batch_id)
    info_csv = pipeline_csv.run(source_csv.raw_products)
    log.info("bronze_products (CSV) — %s", info_csv)

    # JSON catalogue interne
    pipeline_json = dlt.pipeline(
        pipeline_name="bronze_products_json",
        destination="duckdb",
        dataset_name=DATASET_NAME,
    )
    source_json = olist_json_source(batch_id=batch_id)
    info_json = pipeline_json.run(source_json.raw_products_json)
    log.info("bronze_products_json — %s", info_json)

    return pipeline_csv


if __name__ == "__main__":
    run()
