"""
Vérification post-ingestion de la couche Bronze.

Ouvre olist.duckdb en LECTURE SEULE, inspecte le schéma bronze,
et ferme la connexion explicitement à la fin.
Ne modifie aucune donnée.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DUCKDB_PATH = str(_PROJECT_ROOT / "warehouse" / "duckdb" / "olist.duckdb")

EXPECTED_META_COLS = {"_loaded_at", "_source_file", "_batch_id"}


def _separator(char: str = "-", width: int = 70) -> None:
    print(char * width)


def main() -> int:
    print("=" * 70)
    print("verify_bronze.py — DuckDB read-only check")
    print(f"Path : {DUCKDB_PATH}")
    print(f"File exists : {Path(DUCKDB_PATH).exists()}")
    print("=" * 70)

    if not Path(DUCKDB_PATH).exists():
        print("ERROR: DuckDB file not found. Run the Bronze pipeline first.")
        return 1

    # Connexion lecture seule — ne crée pas de verrou en écriture
    con = duckdb.connect(DUCKDB_PATH, read_only=True)

    try:
        # ── 1. Lister toutes les tables du schéma bronze ─────────────────────
        tables_df = con.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'bronze'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """).df()

        table_names = tables_df["table_name"].tolist()
        print(f"\nTables found in schema 'bronze' : {len(table_names)}")
        for t in table_names:
            print(f"  - {t}")

        # ── 2. Détail par table raw_* ─────────────────────────────────────────
        print()
        _separator("=")
        print(f"{'Table':<35} {'Cols':>4} {'Rows':>10}  {'Meta cols OK'}")
        _separator()

        raw_tables = [t for t in table_names if t.startswith("raw_")]
        total_rows = 0

        for table in raw_tables:
            # Colonnes de la table
            cols_df = con.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'bronze'
                  AND table_name = '{table}'
                ORDER BY ordinal_position
            """).df()
            col_names = set(cols_df["column_name"].tolist())
            n_cols = len(col_names)

            # Nombre de lignes
            row_count = con.execute(
                f'SELECT COUNT(*) FROM bronze."{table}"'
            ).fetchone()[0]
            total_rows += row_count

            # Vérification colonnes métadonnées
            missing = EXPECTED_META_COLS - col_names
            meta_ok = "YES" if not missing else f"NO (missing: {missing})"

            print(f"{table:<35} {n_cols:>4} {row_count:>10}  {meta_ok}")

        _separator()
        print(f"{'TOTAL':<35} {'':>4} {total_rows:>10}")

        # ── 3. Sample raw_customers (villes brésiliennes + accents) ──────────
        print()
        _separator("=")
        print("SAMPLE — raw_customers (3 rows, accent check)")
        _separator()
        if "raw_customers" in table_names:
            sample = con.execute(
                "SELECT customer_id, customer_city, customer_state, _source_file, _batch_id "
                "FROM bronze.raw_customers LIMIT 3"
            ).df()
            print(sample.to_string(index=False))
        else:
            print("raw_customers not found.")

        # ── 4. Sample raw_reviews (commentaires + accents) ───────────────────
        print()
        _separator("=")
        print("SAMPLE — raw_reviews (3 rows, comment text check)")
        _separator()
        if "raw_reviews" in table_names:
            sample = con.execute(
                "SELECT review_id, review_score, "
                "LEFT(review_comment_message, 80) AS comment_preview, "
                "_loaded_at "
                "FROM bronze.raw_reviews "
                "WHERE review_comment_message != '' LIMIT 3"
            ).df()
            print(sample.to_string(index=False))
        else:
            print("raw_reviews not found.")

        # ── 5. Vérification des fichiers sources distincts (exchange_rates) ──
        print()
        _separator("=")
        print("SAMPLE — raw_exchange_rates (sources distinctes)")
        _separator()
        if "raw_exchange_rates" in table_names:
            src = con.execute(
                "SELECT _source_file, base_currency, COUNT(*) AS n_currencies "
                "FROM bronze.raw_exchange_rates "
                "GROUP BY _source_file, base_currency "
                "ORDER BY _source_file"
            ).df()
            print(src.to_string(index=False))

        print()
        _separator("=")
        print("Verification complete — connection closing.")

    finally:
        # Fermeture explicite — libère le fichier immédiatement
        con.close()
        print("Connection closed (read-only, no lock held).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
