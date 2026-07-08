"""
Job Dagster : pipeline complet Bronze → Silver → Gold.

L'ordre est garanti par les deps déclarés sur les assets (pas besoin
de les re-spécifier ici). Si une couche échoue, Dagster arrête le run
et ne matérialise pas les assets aval — comportement par défaut.
"""

from dagster import define_asset_job, AssetSelection

from dagster_project.assets.bronze_assets import BRONZE_ASSETS
from dagster_project.assets.silver_assets import SILVER_ASSETS
from dagster_project.assets.gold_assets import GOLD_ASSETS

# Sélection de tous les assets du pipeline par groupe
_ALL_PIPELINE_ASSETS = AssetSelection.groups("bronze", "silver", "gold")

full_pipeline_job = define_asset_job(
    name="full_pipeline_job",
    selection=_ALL_PIPELINE_ASSETS,
    description=(
        "Pipeline complet : ingestion dlt (Bronze) → "
        "nettoyage dbt (Silver) → marts + features ML (Gold). "
        "Si une couche échoue, les couches aval ne sont pas exécutées."
    ),
    tags={"pipeline": "medallion", "team": "data-engineering"},
)
