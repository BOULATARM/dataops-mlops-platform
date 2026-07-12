"""Pipeline DataOps, monitoring et MLOps complet."""

from dagster import (
    AssetSelection,
    define_asset_job,
    in_process_executor,
)

full_pipeline_job = define_asset_job(
    name="full_pipeline_job",
    selection=AssetSelection.groups(
        "bronze",
        "silver",
        "gold",
        "monitoring",
        "ml",
    ),
    executor_def=in_process_executor,
    description=(
        "Pipeline séquentiel : Bronze, Silver, Gold, "
        "détection de dérive, entraînement MLflow "
        "et rechargement FastAPI."
    ),
    tags={
        "pipeline": "medallion",
        "team": "data-engineering",
        "includes_ml": "true",
        "includes_drift": "true",
    },
)
