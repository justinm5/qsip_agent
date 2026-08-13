import numpy as np
import pytest

from qsip.explainability import explain_signal


class DummyModel:
    def predict_proba(self, X):
        return np.array([[0.4, 0.6]])


def test_explain_signal_fallback():
    model = DummyModel()
    features = {"volume_ratio": 5.0, "insider_buy_ratio": 0.9, "news_sentiment_mean": 0.3}
    keys = list(features.keys())
    explanation = explain_signal(model, features, keys)
    assert "top_features" in explanation
    assert len(explanation["top_features"]) <= len(features)
