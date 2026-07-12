"""Job Dagster complet : Bronze -> Silver -> Gold."""

from dagster import AssetSelection, define_asset_job, in_process_executor

full_pipeline_job = define_asset_job(
    name="full_pipeline_job",
    selection=AssetSelection.groups(
        "bronze",
        "silver",
        "gold",
    ),
    executor_def=in_process_executor,
    description=(
        "Pipeline DataOps complet exécuté séquentiellement : "
        "ingestion Bronze, transformations Silver et modèles Gold."
    ),
    tags={
        "pipeline": "medallion",
        "team": "data-engineering",
    },
)
