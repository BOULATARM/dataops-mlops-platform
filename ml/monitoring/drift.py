"""Numeric PSI monitoring. Run: python -m ml.monitoring.drift reference.csv current.csv."""

import argparse
import json
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def alert_if_drift(report):
    if report["drift_detected"] or report["severity"] != "stable":
        logger.warning("model_drift_alert %s", json.dumps(report))
    return report


def check_drift(reference, current):
    if reference.empty or current.empty:
        raise ValueError("Reference and current samples must be non-empty")
    scores = {}
    for column in reference.select_dtypes(include="number").columns:
        ref = reference[column].dropna().to_numpy()
        cur = current[column].dropna().to_numpy()
        if not len(ref) or not len(cur) or not np.isfinite(ref).all() or not np.isfinite(cur).all():
            raise ValueError(f"Invalid finite observations: {column}")
        cuts = np.unique(np.quantile(ref, np.linspace(0, 1, 11)))
        edges = np.r_[-np.inf, cuts, np.inf]
        a = np.histogram(ref, bins=edges)[0] / len(ref)
        b = np.histogram(cur, bins=edges)[0] / len(cur)
        a, b = np.clip(a, 1e-6, None), np.clip(b, 1e-6, None)
        scores[column] = float(np.sum((b - a) * np.log(b / a)))
    if not scores:
        raise ValueError("No numeric features to monitor")
    maximum = max(scores.values())
    severity = "high" if maximum >= 0.2 else "moderate" if maximum >= 0.1 else "stable"
    return alert_if_drift({"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                           "drift_detected": maximum >= 0.2,
                           "severity": severity, "psi": scores})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference")
    parser.add_argument("current")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(check_drift(pd.read_csv(args.reference), pd.read_csv(args.current))))
