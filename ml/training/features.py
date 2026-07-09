import duckdb
import pandas as pd
from sklearn.model_selection import train_test_split

from ml.training.config import (
    DUCKDB_PATH,
    GOLD_TABLE,
    NUMERIC_FEATURES,
    RANDOM_STATE,
    TARGET_COLUMN,
    TEST_SIZE,
)


def load_features() -> pd.DataFrame:
    """
    Charge les features depuis main_gold.gold_reviews_features (lecture seule).

    Features utilisées : 4 colonnes numériques dérivées du texte/livraison/paiement.
    Ces colonnes sont identiques à celles attendues par l'API /predict, ce qui
    garantit la cohérence entraînement ↔ inférence.
    """
    cols = NUMERIC_FEATURES + [TARGET_COLUMN]
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        df = con.execute(f"SELECT {', '.join(cols)} FROM {GOLD_TABLE}").df()
    finally:
        con.close()

    # Booléen DuckDB → int pour SimpleImputer/StandardScaler
    df["has_comment"] = df["has_comment"].astype(int)

    # delivery_delay_days peut être NULL (commandes non encore livrées) —
    # SimpleImputer(strategy="median") dans la pipeline le gère.

    print(
        f"Dataset charge : {len(df):,} lignes | "
        f"satisfied=1 : {df[TARGET_COLUMN].sum():,} ({df[TARGET_COLUMN].mean()*100:.1f}%)"
    )
    return df


def prepare_splits(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Split stratifie 80/20 sur la target `satisfied`."""
    X = df.drop(columns=[TARGET_COLUMN])
    y = df[TARGET_COLUMN].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )
    print(
        f"Train : {len(X_train):,} | Test : {len(X_test):,} | "
        f"Balance test — 0:{(y_test==0).sum()} 1:{(y_test==1).sum()}"
    )
    return X_train, X_test, y_train, y_test
