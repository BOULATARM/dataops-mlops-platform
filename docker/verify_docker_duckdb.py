import duckdb, os, sys
db = os.environ.get("DUCKDB_PATH", "NOT_SET")
print("DUCKDB_PATH:", db)
try:
    con = duckdb.connect(db, read_only=True)
    rows = con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_schema IN ('bronze','main_bronze','main_silver','main_gold') "
        "ORDER BY table_schema, table_name"
    ).fetchall()
    total_assets = 0
    for schema, table in rows:
        cnt = con.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
        print(f"  {schema}.{table}: {cnt:,}")
        total_assets += 1
    print(f"Total tables: {total_assets}")
    sample = con.execute("SELECT review_score, satisfied, delivery_delay_days FROM main_gold.gold_reviews_features LIMIT 3").fetchall()
    print("gold_reviews_features sample:", sample)
    con.close()
except Exception as e:
    print("ERREUR:", e)
    sys.exit(1)
