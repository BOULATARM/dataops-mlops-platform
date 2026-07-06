"""
Source dlt pour les fichiers CSV Olist.

Expose un @dlt.source nommé ``olist_csv_source`` contenant un @dlt.resource
par fichier CSV.  Chaque resource lit le CSV en chunks pandas et injecte
trois colonnes de métadonnées d'ingestion :

    _loaded_at   datetime UTC au moment du run
    _source_file nom du fichier CSV source
    _batch_id    UUID unique par exécution du pipeline (passé en paramètre)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import dlt
import pandas as pd

from dlt_pipelines.config import CHUNK_SIZE, CSV_DIR, CSV_FILES


def _iter_csv(
    table_key: str,
    batch_id: str,
    chunk_size: int = CHUNK_SIZE,
) -> Iterator[dict]:
    """Lit le CSV associé à *table_key* et yield des dicts enrichis de métadonnées."""
    filename: str = CSV_FILES[table_key]
    filepath: Path = CSV_DIR / filename
    loaded_at: str = datetime.now(tz=timezone.utc).isoformat()

    for chunk in pd.read_csv(
        filepath,
        chunksize=chunk_size,
        dtype=str,          # tout en str → dlt infère les types en aval
        na_filter=False,    # garde les chaînes vides plutôt que NaN
    ):
        for row in chunk.to_dict(orient="records"):
            row["_loaded_at"] = loaded_at
            row["_source_file"] = filename
            row["_batch_id"] = batch_id
            yield row


@dlt.source(name="olist_csv")
def olist_csv_source(batch_id: str = "") -> list:
    """
    Source dlt pour tous les CSV Olist.

    Parameters
    ----------
    batch_id : UUID unique du run (généré automatiquement si vide).
    """
    if not batch_id:
        batch_id = str(uuid.uuid4())

    @dlt.resource(
        name="raw_customers",
        write_disposition="append",
        primary_key="customer_id",
    )
    def raw_customers() -> Iterator[dict]:
        yield from _iter_csv("raw_customers", batch_id)

    @dlt.resource(
        name="raw_orders",
        write_disposition="append",
        primary_key="order_id",
    )
    def raw_orders() -> Iterator[dict]:
        yield from _iter_csv("raw_orders", batch_id)

    @dlt.resource(
        name="raw_order_items",
        write_disposition="append",
    )
    def raw_order_items() -> Iterator[dict]:
        yield from _iter_csv("raw_order_items", batch_id)

    @dlt.resource(
        name="raw_payments",
        write_disposition="append",
    )
    def raw_payments() -> Iterator[dict]:
        yield from _iter_csv("raw_payments", batch_id)

    @dlt.resource(
        name="raw_reviews",
        write_disposition="append",
        primary_key="review_id",
    )
    def raw_reviews() -> Iterator[dict]:
        yield from _iter_csv("raw_reviews", batch_id)

    @dlt.resource(
        name="raw_products",
        write_disposition="append",
        primary_key="product_id",
    )
    def raw_products() -> Iterator[dict]:
        yield from _iter_csv("raw_products", batch_id)

    @dlt.resource(
        name="raw_sellers",
        write_disposition="append",
        primary_key="seller_id",
    )
    def raw_sellers() -> Iterator[dict]:
        yield from _iter_csv("raw_sellers", batch_id)

    @dlt.resource(
        name="raw_geolocation",
        write_disposition="append",
    )
    def raw_geolocation() -> Iterator[dict]:
        yield from _iter_csv("raw_geolocation", batch_id)

    @dlt.resource(
        name="raw_category_translation",
        write_disposition="append",
        primary_key="product_category_name",
    )
    def raw_category_translation() -> Iterator[dict]:
        yield from _iter_csv("raw_category_translation", batch_id)

    return [
        raw_customers,
        raw_orders,
        raw_order_items,
        raw_payments,
        raw_reviews,
        raw_products,
        raw_sellers,
        raw_geolocation,
        raw_category_translation,
    ]
