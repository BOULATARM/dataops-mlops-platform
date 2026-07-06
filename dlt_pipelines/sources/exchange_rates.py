"""
Source dlt pour les fichiers JSON de taux de change (data/raw/api/).

Itère sur TOUS les fichiers exchange_rates*.json présents dans le répertoire API,
normalise leur structure (deux formats coexistent : openexchangerates et
exchangerate-api) et yield une ligne par paire (devise, taux).

Colonnes produites :
    currency_code   code ISO 4217 de la devise cible
    rate            taux par rapport à la devise de base
    base_currency   devise de référence (EUR ou BRL selon le fichier)
    fetched_at      horodatage du snapshot (extrait du fichier)
    _loaded_at      timestamp d'ingestion dlt (UTC)
    _source_file    nom du fichier JSON source
    _batch_id       UUID unique par run
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import dlt

from dlt_pipelines.config import API_DIR


def _parse_exchange_file(filepath: Path) -> tuple[str, str, dict[str, float]]:
    """
    Parse un fichier JSON de taux de change, quel que soit son format.

    Retourne (base_currency, fetched_at_iso, {currency_code: rate}).
    """
    with open(filepath, encoding="utf-8") as fh:
        data = json.load(fh)

    rates: dict[str, float] = {}

    # Format openexchangerates : clés "base" et "fetched_at"
    if "base" in data and "fetched_at" in data:
        base = data["base"]
        fetched_at = data["fetched_at"]
        rates = {k: float(v) for k, v in data.get("rates", {}).items()}

    # Format exchangerate-api : clés "base_code" et "time_last_update_utc"
    elif "base_code" in data:
        base = data["base_code"]
        fetched_at = data.get("time_last_update_utc", "")
        rates = {k: float(v) for k, v in data.get("rates", {}).items()}

    # Fallback générique
    else:
        base = data.get("base", data.get("base_code", "UNKNOWN"))
        fetched_at = data.get("fetched_at", data.get("time_last_update_utc", ""))
        rates = {k: float(v) for k, v in data.get("rates", {}).items()}

    return base, fetched_at, rates


@dlt.source(name="exchange_rates")
def exchange_rates_source(batch_id: str = "") -> list:
    """
    Source dlt pour tous les fichiers exchange_rates*.json.

    Parcourt API_DIR et charge chaque fichier correspondant au pattern.
    Le _source_file distingue les snapshots entre eux.
    """
    if not batch_id:
        batch_id = str(uuid.uuid4())

    @dlt.resource(
        name="raw_exchange_rates",
        write_disposition="append",
    )
    def raw_exchange_rates() -> Iterator[dict]:
        loaded_at = datetime.now(tz=timezone.utc).isoformat()

        json_files = sorted(API_DIR.glob("exchange_rates*.json"))
        if not json_files:
            return

        for filepath in json_files:
            base_currency, fetched_at, rates = _parse_exchange_file(filepath)
            for currency_code, rate in rates.items():
                yield {
                    "currency_code": currency_code,
                    "rate": rate,
                    "base_currency": base_currency,
                    "fetched_at": fetched_at,
                    "_loaded_at": loaded_at,
                    "_source_file": filepath.name,
                    "_batch_id": batch_id,
                }

    return [raw_exchange_rates]
