"""
Source dlt pour le fichier JSON produits (products_sample.json).

Le fichier contient un tableau JSON d'objets produits venant d'un système
complémentaire (catalogue interne), distinct du CSV Olist principal.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Iterator

import dlt

from dlt_pipelines.config import JSON_PRODUCTS_FILE


@dlt.source(name="olist_json")
def olist_json_source(batch_id: str = "") -> list:
    """
    Source dlt pour products_sample.json.

    Parameters
    ----------
    batch_id : UUID unique du run (généré automatiquement si vide).
    """
    if not batch_id:
        batch_id = str(uuid.uuid4())

    @dlt.resource(
        name="raw_products_json",
        write_disposition="append",
        primary_key="product_id",
    )
    def raw_products_json() -> Iterator[dict]:
        loaded_at = datetime.now(tz=timezone.utc).isoformat()
        filename = JSON_PRODUCTS_FILE.name

        with open(JSON_PRODUCTS_FILE, encoding="utf-8") as fh:
            records = json.load(fh)

        if isinstance(records, dict):
            records = [records]

        for record in records:
            record["_loaded_at"] = loaded_at
            record["_source_file"] = filename
            record["_batch_id"] = batch_id
            yield record

    return [raw_products_json]
