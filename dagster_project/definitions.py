"""Définitions complètes Dagster."""

from dagster import Definitions

from dagster_project.assets.bronze_assets import (
    BRONZE_ASSETS,
)
from dagster_project.assets.gold_assets import (
    GOLD_ASSETS,
)
from dagster_project.assets.ml_assets import (
    ML_ASSETS,
)
from dagster_project.assets.silver_assets import (
    SILVER_ASSETS,
)
from dagster_project.jobs.full_pipeline_job import (
    full_pipeline_job,
)
from dagster_project.resources.duckdb_resource import (
    build_duckdb_resource,
)
from dagster_project.schedules.daily_schedule import (
    daily_pipeline_schedule,
)

defs = Definitions(
    assets=[
        *BRONZE_ASSETS,
        *SILVER_ASSETS,
        *GOLD_ASSETS,
        *ML_ASSETS,
    ],
    jobs=[
        full_pipeline_job,
    ],
    schedules=[
        daily_pipeline_schedule,
    ],
    resources={
        "duckdb": build_duckdb_resource(),
    },
)
