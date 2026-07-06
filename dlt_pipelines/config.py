"""
Configuration centralisée pour les pipelines dlt.

DATA_PATH  : répertoire racine des données sources Olist (lecture seule).
DUCKDB_PATH: fichier DuckDB cible (créé automatiquement s'il n'existe pas).

Les deux variables sont lues depuis l'environnement avec un fallback pour
le développement local (les deux projets côte-à-côte sur le système hôte).
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Chemins ───────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_PATH: Path = Path(
    os.getenv(
        "DATA_PATH",
        str(_PROJECT_ROOT.parent / "data-engineering-platform" / "data" / "raw"),
    )
)

DUCKDB_PATH: str = os.getenv(
    "DUCKDB_PATH",
    str(_PROJECT_ROOT / "warehouse" / "duckdb" / "olist.duckdb"),
)

# Injecte la variable d'environnement dlt pour la destination DuckDB
# (dlt la lit automatiquement si elle n'est pas déjà définie)
os.environ.setdefault("DESTINATION__DUCKDB__CREDENTIALS", DUCKDB_PATH)

# ── Répertoires sources ───────────────────────────────────────────────────────

CSV_DIR: Path = DATA_PATH / "csv"
JSON_DIR: Path = DATA_PATH / "json"
API_DIR: Path = DATA_PATH / "api"

# ── Noms de fichiers CSV attendus ─────────────────────────────────────────────

CSV_FILES: dict[str, str] = {
    "raw_customers":           "olist_customers_dataset.csv",
    "raw_orders":              "olist_orders_dataset.csv",
    "raw_order_items":         "olist_order_items_dataset.csv",
    "raw_payments":            "olist_order_payments_dataset.csv",
    "raw_reviews":             "olist_order_reviews_dataset.csv",
    "raw_products":            "olist_products_dataset.csv",
    "raw_sellers":             "olist_sellers_dataset.csv",
    "raw_geolocation":         "olist_geolocation_dataset.csv",
    "raw_category_translation":"product_category_name_translation.csv",
}

# ── Noms de fichiers JSON ─────────────────────────────────────────────────────

JSON_PRODUCTS_FILE: Path = JSON_DIR / "products_sample.json"

# ── Paramètres dlt ────────────────────────────────────────────────────────────

DATASET_NAME: str = "bronze"
CHUNK_SIZE: int = int(os.getenv("DLT_BATCH_SIZE", "10000"))
