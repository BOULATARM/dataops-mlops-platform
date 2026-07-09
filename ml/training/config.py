import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DUCKDB_PATH: str = os.environ.get("DUCKDB_PATH") or str(
    _PROJECT_ROOT / "warehouse" / "duckdb" / "olist.duckdb"
)

MLFLOW_TRACKING_URI: str = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5100")
MLFLOW_EXPERIMENT_NAME: str = os.environ.get("MLFLOW_EXPERIMENT_NAME", "olist-satisfaction-v2")
MLFLOW_MODEL_NAME: str = os.environ.get("MLFLOW_MODEL_NAME", "SatisfactionClassifier")

GOLD_TABLE: str = "main_gold.gold_reviews_features"
TARGET_COLUMN: str = "satisfied"

# Features disponibles dans gold_reviews_features ET dans l'API /predict.
# review_comment_message est en silver uniquement — on utilise ses dérivées.
NUMERIC_FEATURES: list[str] = [
    "delivery_delay_days",
    "review_comment_length",
    "has_comment",
    "payment_type_encoded",
]

LR_C: float = 1.0
LR_MAX_ITER: int = 1000
TEST_SIZE: float = 0.2
RANDOM_STATE: int = 42
