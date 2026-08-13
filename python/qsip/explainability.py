from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def explain_signal(model, features: dict[str, float], feature_keys: list[str]) -> dict[str, Any]:
    """Generate SHAP-based explanation for a signal."""
    try:
        import shap
        x = np.array([[float(features.get(k, 0.0)) for k in feature_keys]])
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(x)
        if isinstance(shap_values, list):
            vals = shap_values[1][0]
        else:
            vals = shap_values[0]

        mapping = {k: float(v) for k, v in zip(feature_keys, vals)}
        top = sorted(mapping.items(), key=lambda kv: abs(kv[1]), reverse=True)[:10]
        summary_parts = []
        for k, v in top[:5]:
            direction = "+" if v > 0 else "-"
            summary_parts.append(f"{direction} {k.replace('_', ' ').title()}")

        return {
            "shap_values": mapping,
            "top_features": [{"feature": k, "impact": v} for k, v in top],
            "summary": ", ".join(summary_parts),
        }
    except Exception as e:
        logger.warning("shap explain failed: %s", e)
        # Fallback to feature rank by magnitude
        top = sorted(features.items(), key=lambda kv: abs(kv[1]), reverse=True)[:10]
        return {
            "shap_values": {},
            "top_features": [{"feature": k, "impact": float(v)} for k, v in top],
            "summary": "feature-driven signal (SHAP unavailable)",
        }
