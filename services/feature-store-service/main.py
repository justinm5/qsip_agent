"""Feature Store serving API for training/serving parity."""
import json
import logging
import os
from datetime import datetime

import polars as pl
from flask import Flask, jsonify, request
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from qsip.config import Config
from qsip.db import TimescaleDB
from qsip.feature_store import FeatureStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
cfg = Config.from_env()
db = TimescaleDB(cfg.db_dsn)
store = FeatureStore(db)

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/metrics": make_wsgi_app()})


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/features/<ticker>")
def get_features(ticker: str):
    version = request.args.get("version", "v1")
    row = db.get_latest_feature_vector(ticker, version)
    if not row:
        return jsonify({"error": "not found"}), 404
    features = row["features"] if isinstance(row["features"], dict) else json.loads(row["features"])
    return jsonify({
        "ticker": ticker,
        "version": version,
        "timestamp": row["timestamp"].isoformat(),
        "features": features,
        "signature": store.feature_signature(features),
    })


@app.route("/features/<ticker>/history")
def get_history(ticker: str):
    version = request.args.get("version", "v1")
    with db.cursor() as cur:
        cur.execute(
            "SELECT timestamp, features FROM feature_store WHERE ticker = %s AND feature_version = %s ORDER BY timestamp DESC LIMIT 100",
            (ticker, version),
        )
        rows = cur.fetchall()
    return jsonify([{"timestamp": r["timestamp"].isoformat(), "features": r["features"]} for r in rows])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8085")))
