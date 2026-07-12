"""
Ressource Dagster encapsulant la connexion DuckDB.

Stratégie anti-verrou : on n'ouvre jamais une connexion en écriture
pendant qu'une autre est active. Chaque asset qui a besoin de lire
DuckDB crée une connexion read_only locale, courte-durée, qu'il ferme
immédiatement. La ressource ne garde pas de connexion longue ouverte —
elle expose uniquement le chemin absolu et une factory read_only.
"""

from contextlib import contextmanager
from pathlib import Path

import duckdb
from dagster import ConfigurableResource


class DuckDBResource(ConfigurableResource):
    """Chemin absolu vers le fichier DuckDB du warehouse."""

    db_path: str

    @contextmanager
    def get_connection(self, read_only: bool = True):
        """Context-manager : ouvre, yield, ferme. Toujours read_only par défaut."""
        con = duckdb.connect(self.db_path, read_only=read_only)
        try:
            yield con
        finally:
            con.close()

    def query(self, sql: str) -> list:
        """Raccourci pour une requête read_only ponctuelle."""
        with self.get_connection(read_only=True) as con:
            return con.execute(sql).fetchall()


def build_duckdb_resource() -> DuckDBResource:
    """
    Construit la resource.
    Priorité : env var DUCKDB_PATH > chemin absolu résolu depuis ce fichier.
    L'env var permet de pointer vers le volume Docker /data/duckdb/olist.duckdb.
    """
    import os
    _project_root = Path(__file__).resolve().parent.parent.parent
    db_path = os.environ.get("DUCKDB_PATH") or str(
        _project_root / "warehouse" / "duckdb" / "olist.duckdb"
    )
    return DuckDBResource(db_path=db_path)
