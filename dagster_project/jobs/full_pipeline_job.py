"""Pipeline DataOps et MLOps complet."""

from dagster import AssetSelection, define_asset_job, in_process_executor

full_pipeline_job = define_asset_job(
    name="full_pipeline_job",
    selection=AssetSelection.groups(
        "bronze",
        "silver",
        "gold",
        "ml",
    ),
    executor_def=in_process_executor,
    description=(
        "Pipeline complet exécuté séquentiellement : "
        "ingestion Bronze, transformations Silver et Gold, "
        "entraînement MLflow et rechargement FastAPI."
    ),
    tags={
        "pipeline": "medallion",
        "team": "data-engineering",
        "includes_ml": "true",
    },
)
