from types import SimpleNamespace
from unittest.mock import patch

from api.model_loader import ModelLoader


def test_registry_loads_exact_version_and_clears_failed_reload(monkeypatch):
    monkeypatch.delenv("MLFLOW_MODEL_ALIAS", raising=False)
    loader = ModelLoader()
    version = SimpleNamespace(version="19", run_id="run-19")
    with patch("mlflow.tracking.MlflowClient") as client, patch("mlflow.sklearn.load_model") as load:
        client.return_value.get_latest_versions.return_value = [version]
        loader.reload()
        load.assert_called_once_with("models:/SatisfactionClassifier/19")
        assert (loader.model_version, loader.run_id) == ("19", "run-19")
        load.side_effect = RuntimeError("unavailable")
        loader.reload()
        assert not loader.is_loaded
        assert loader.model is loader.model_version is loader.run_id is None


def test_registry_alias(monkeypatch):
    monkeypatch.setenv("MLFLOW_MODEL_ALIAS", "champion")
    with patch("mlflow.tracking.MlflowClient") as client, patch("mlflow.sklearn.load_model"):
        client.return_value.get_model_version_by_alias.return_value = SimpleNamespace(version="19", run_id="r")
        loader = ModelLoader()
        loader.reload()
        client.return_value.get_model_version_by_alias.assert_called_once_with("SatisfactionClassifier", "champion")
        assert loader.run_id == "r"
