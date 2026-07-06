"""Pipeline Bronze — exchange_rates (tous les fichiers JSON API)."""

from __future__ import annotations

import logging
import uuid

import dlt

from dlt_pipelines.config import DATASET_NAME
from dlt_pipelines.sources.exchange_rates import exchange_rates_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def run() -> dlt.Pipeline:
    batch_id = str(uuid.uuid4())
    pipeline = dlt.pipeline(
        pipeline_name="bronze_exchange",
        destination="duckdb",
        dataset_name=DATASET_NAME,
    )
    source = exchange_rates_source(batch_id=batch_id)
    load_info = pipeline.run(source.raw_exchange_rates)
    log.info("bronze_exchange — %s", load_info)
    return pipeline


if __name__ == "__main__":
    run()
