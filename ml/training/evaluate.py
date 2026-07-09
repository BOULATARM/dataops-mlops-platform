import io

import mlflow
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_metrics(pipeline, X_test, y_test) -> dict[str, float]:
    """Calcule accuracy, F1, precision, recall, ROC-AUC sur le jeu de test."""
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]
    return {
        "accuracy":  round(accuracy_score(y_test, y_pred), 4),
        "f1":        round(f1_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred), 4),
        "recall":    round(recall_score(y_test, y_pred), 4),
        "roc_auc":   round(roc_auc_score(y_test, y_proba), 4),
    }


def log_artifacts(pipeline, X_test, y_test) -> None:
    """
    Logue vers le run MLflow actif :
      - classification_report.txt  (rapport complet + matrice de confusion)
    """
    y_pred = pipeline.predict(X_test)
    cm = confusion_matrix(y_test, y_pred)
    report = classification_report(
        y_test, y_pred, target_names=["insatisfait (0)", "satisfait (1)"]
    )

    buf = io.StringIO()
    buf.write("=== Matrice de confusion ===\n")
    buf.write("         pred 0   pred 1\n")
    buf.write(f"reel 0   {cm[0,0]:<8} {cm[0,1]}\n")
    buf.write(f"reel 1   {cm[1,0]:<8} {cm[1,1]}\n")
    buf.write("\n=== Rapport de classification ===\n")
    buf.write(report)
    content = buf.getvalue()

    mlflow.log_text(content, "classification_report.txt")
    print(content)
