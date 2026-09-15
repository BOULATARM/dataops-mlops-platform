import json
import logging

import pandas as pd
import pytest

from ml.monitoring.drift import alert_if_drift, check_drift


@pytest.mark.parametrize("detected,severity", [(True, "stable"), (False, "moderate"), (True, "high")])
def test_alert_for_drift_or_nonstable(caplog, detected, severity):
    with caplog.at_level(logging.WARNING):
        alert_if_drift({"drift_detected": detected, "severity": severity})
    assert "model_drift_alert" in caplog.text


def test_stable_silent_and_shift_alerts(caplog):
    reference = pd.DataFrame({"delay": range(100)})
    assert check_drift(reference, reference)["severity"] == "stable"
    assert not caplog.records
    with caplog.at_level(logging.WARNING):
        assert check_drift(reference, reference + 1000)["drift_detected"]
    assert "model_drift_alert" in caplog.text


@pytest.mark.parametrize("code", [200, 422, 503, 500])
def test_latency_logs_success_and_failures(client, caplog, monkeypatch, code):
    from api.main import _loader
    payload = dict(delivery_delay_days=0, review_comment_length=0, has_comment=False, payment_type_encoded=0)
    if code == 422:
        payload = {}
    elif code == 503:
        monkeypatch.setattr(_loader, "is_loaded", False)
    elif code == 500:
        monkeypatch.setattr(_loader, "predict_one", lambda row: (_ for _ in ()).throw(ValueError("test")))
    with caplog.at_level(logging.INFO, logger="predict_audit"):
        assert client.post("/predict", json=payload).status_code == code
    event = next(json.loads(r.message) for r in caplog.records if r.message.startswith('{"event": "predict_latency"'))
    assert event["status_code"] == code
    assert event["latency_ms"] >= 0
