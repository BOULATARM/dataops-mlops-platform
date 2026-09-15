"""Serializable fitted classifier keeping the validated decision threshold."""

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin


class ThresholdClassifier(ClassifierMixin, BaseEstimator):
    def __init__(self, estimator, threshold=0.5):
        self.estimator = estimator
        self.threshold = threshold

    @property
    def classes_(self):
        return self.estimator.classes_

    @property
    def feature_names_in_(self):
        return self.estimator.feature_names_in_

    def __sklearn_is_fitted__(self):
        return hasattr(self.estimator, "classes_")

    def predict_proba(self, X):
        return self.estimator.predict_proba(X)

    def predict(self, X):
        index = list(self.classes_).index(1)
        return np.where(self.predict_proba(X)[:, index] >= self.threshold, 1, 0)
