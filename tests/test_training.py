import numpy as np
import pytest
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV

from ml.training.train_v2 import select_threshold
from ml.training.threshold_model import ThresholdClassifier


def test_threshold_improves_class_zero_recall_with_precision_constraint():
    y = np.array([0, 0, 0, 1, 1, 1])
    p = np.array([0.1, 0.55, 0.6, 0.8, 0.9, 0.95])
    threshold, sweep = select_threshold(y, p, min_precision=0.8)
    assert 0.6 < threshold <= 0.8
    assert np.array_equal((p >= threshold).astype(int), y)
    assert len(sweep) == 91


def test_infeasible_precision_rejects_candidate():
    with pytest.raises(ValueError, match="precision floor"):
        select_threshold(np.array([1, 0]), np.array([0.1, 0.99]), min_precision=1.0)


def test_serialized_model_preserves_calibration_and_threshold(tmp_path):
    import mlflow.sklearn
    X, y = make_classification(n_samples=90, n_features=4, random_state=42)
    calibrated = CalibratedClassifierCV(LogisticRegression(), cv=3).fit(X, y)
    model = ThresholdClassifier(calibrated, 0.7)
    mlflow.sklearn.save_model(model, str(tmp_path / "model"))
    restored = mlflow.sklearn.load_model(str(tmp_path / "model"))
    np.testing.assert_allclose(restored.predict_proba(X), model.predict_proba(X))
    np.testing.assert_array_equal(restored.predict(X), (restored.predict_proba(X)[:, 1] >= 0.7).astype(int))
