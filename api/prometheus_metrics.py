"""Serving metrics and cached, read-only MLflow monitoring observations.

Scrapes never contact MLflow. Missing or expired observations are omitted,
not replaced with zeros. The drift source is the existing monitoring run.
"""

import asyncio
import logging
import math
import os
import time

from prometheus_client import REGISTRY, Counter
from prometheus_client.core import GaugeMetricFamily

logger = logging.getLogger(__name__)

PREDICTIONS = Counter(
    "ml_predictions_total", "Successful predictions since process start.",
    ["prediction"],
)
for _prediction in ("0", "1"):
    PREDICTIONS.labels(prediction=_prediction)


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


class ModelMetrics:
    def __init__(self, loader):
        self.loader = loader
        self.snapshot = (0.0, None, {}, {})

    def describe(self):
        # Register names without performing any I/O during registration.
        for name in (
            "ml_model_loaded", "ml_model_info", "ml_model_accuracy",
            "ml_model_precision", "ml_model_recall", "ml_model_f1",
            "ml_decision_threshold", "ml_drift_score", "ml_drift_status",
            "ml_drift_last_check_timestamp", "ml_drift_current_rows",
            "ml_drift_warning_threshold", "ml_drift_high_threshold",
        ):
            yield GaugeMetricFamily(name, name)

    def collect(self):
        loader = self.loader
        yield GaugeMetricFamily(
            "ml_model_loaded", "Whether the API currently has a loaded model.",
            value=int(loader.is_loaded),
        )
        identity = (loader.model_name, loader.model_version, loader.run_id)
        labels = ["model_name", "model_version", "run_id"]
        if loader.is_loaded and all(identity):
            info = GaugeMetricFamily("ml_model_info", "Loaded registry model.", labels=labels)
            info.add_metric(list(identity), 1)
            yield info

        refreshed, cached_identity, quality, drift = self.snapshot
        if time.monotonic() - refreshed > 180:
            return
        if loader.is_loaded and identity == cached_identity and all(identity):
            for name, value in quality.items():
                metric = GaugeMetricFamily(name, "Loaded model run evaluation or parameter.", labels=labels)
                metric.add_metric(list(identity), value)
                yield metric
        for name, value in drift.items():
            yield GaugeMetricFamily(name, "Latest completed Gold drift comparison in MLflow.", value=value)

    def refresh(self):
        from mlflow.tracking import MlflowClient

        client = MlflowClient(tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-server:5000"))
        identity = (self.loader.model_name, self.loader.model_version, self.loader.run_id)
        quality, drift = {}, {}
        if self.loader.is_loaded and all(identity):
            try:
                run = client.get_run(identity[2])
                for key in ("accuracy", "precision", "recall", "f1"):
                    value = _number(run.data.metrics.get(key))
                    if value is not None and 0 <= value <= 1:
                        quality[f"ml_model_{key}"] = value
                threshold = _number(run.data.params.get("decision_threshold"))
                if threshold is not None and 0 <= threshold <= 1:
                    quality["ml_decision_threshold"] = threshold
            except Exception:
                logger.warning("Model quality metrics unavailable from MLflow", exc_info=True)
        try:
            experiment = client.get_experiment_by_name(
                os.getenv("MLFLOW_MONITORING_EXPERIMENT_NAME", "olist-monitoring")
            )
            if experiment is not None:
                runs = client.search_runs(
                    experiment_ids=[experiment.experiment_id],
                    filter_string="tags.monitoring_type = 'data_drift' AND attributes.status = 'FINISHED'",
                    order_by=["attributes.start_time DESC"], max_results=1,
                )
                if runs:
                    observed = runs[0].data.metrics
                    # Baseline creation and older runs lack this timestamp.
                    checked = _number(observed.get("drift_checked_timestamp"))
                    if checked is not None and checked > 0:
                        for source, target in (
                            ("max_psi", "ml_drift_score"),
                            ("warning_detected", "ml_drift_status"),
                            ("drift_checked_timestamp", "ml_drift_last_check_timestamp"),
                            ("current_rows", "ml_drift_current_rows"),
                        ):
                            value = _number(observed.get(source))
                            if value is not None:
                                drift[target] = value
                        for key in ("warning_threshold", "high_threshold"):
                            value = _number(runs[0].data.params.get(key))
                            if value is not None:
                                drift[f"ml_drift_{key}"] = value
        except Exception:
            logger.warning("Drift metrics unavailable from MLflow", exc_info=True)
        # Replace the snapshot atomically; no stale labels survive a reload.
        self.snapshot = (time.monotonic(), identity, quality, drift)

    async def poll(self):
        while True:
            try:
                await asyncio.to_thread(self.refresh)
            except Exception:
                logger.warning("MLflow metrics refresh failed", exc_info=True)
            await asyncio.sleep(60)


def register_model_metrics(loader):
    collector = ModelMetrics(loader)
    REGISTRY.register(collector)
    return collector
