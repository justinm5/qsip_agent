import logging
import os
from datetime import datetime

import polars as pl
from flask import Flask, jsonify, request
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from qsip.config import Config
from qsip.db import TimescaleDB
from qsip.portfolio import PortfolioEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
cfg = Config.from_env()
db = TimescaleDB(cfg.db_dsn)
engine = PortfolioEngine(initial_cash=1_000_000.0, max_positions=20)

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/metrics": make_wsgi_app()})


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/portfolio/build", methods=["POST"])
def build_portfolio():
    data = request.get_json() or {}
    signals = data.get("signals", [])
    price_lookup = {}
    for ticker in {s["ticker"] for s in signals}:
        rows = db.get_market_data(ticker, days=180)
        if rows:
            price_lookup[ticker] = pl.DataFrame(rows)
    result = engine.simulate(signals, price_lookup)
    snapshot_id = db.insert_portfolio_snapshot(result)
    if snapshot_id:
        db.insert_portfolio_holdings(snapshot_id, result["strategy"], result["holdings"])
    return jsonify(result)


@app.route("/portfolio/<strategy>")
def get_portfolio(strategy: str):
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM portfolio_snapshots WHERE strategy = %s ORDER BY timestamp DESC LIMIT 1",
            (strategy,),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "strategy": row["strategy"],
        "timestamp": row["timestamp"].isoformat(),
        "nav": row["nav"],
        "total_value": row["total_value"],
        "sharpe": row["sharpe"],
        "sortino": row["sortino"],
        "max_drawdown": row["max_drawdown"],
        "alpha": row["alpha"],
        "beta": row["beta"],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8086")))
