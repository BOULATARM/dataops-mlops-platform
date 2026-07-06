"""Pipeline Bronze — geolocation."""

from __future__ import annotations

import logging
import uuid

import dlt

from dlt_pipelines.config import DATASET_NAME
from dlt_pipelines.sources.olist_csv import olist_csv_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def run() -> dlt.Pipeline:
    batch_id = str(uuid.uuid4())
    pipeline = dlt.pipeline(
        pipeline_name="bronze_geolocation",
        destination="duckdb",
        dataset_name=DATASET_NAME,
    )
    source = olist_csv_source(batch_id=batch_id)
    load_info = pipeline.run(source.raw_geolocation)
    log.info("bronze_geolocation — %s", load_info)
    return pipeline


if __name__ == "__main__":
    run()
