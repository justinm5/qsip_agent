import logging
import os
import threading
import time

from flask import Flask, jsonify, request
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from qsip.config import Config
from qsip.db import TimescaleDB
from qsip.kafka_client import KafkaConsumer
from qsip.paper_trading import AlpacaPaperClient, PaperTradingEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
cfg = Config.from_env()
db = TimescaleDB(cfg.db_dsn)
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/metrics": make_wsgi_app()})

alpaca = AlpacaPaperClient(
    api_key=os.getenv("ALPACA_API_KEY", ""),
    secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
    paper=True,
)
engine = PaperTradingEngine(db, alpaca, initial_cash=100_000.0)


def consume_signals():
    consumer = KafkaConsumer(cfg.kafka_brokers, "paper-trading-service", ["signal-events"])
    try:
        consumer.consume(engine.on_signal)
    finally:
        consumer.stop()


def mtm_loop():
    while True:
        try:
            engine.mark_to_market()
        except Exception as e:
            logger.error("mtm error: %s", e)
        time.sleep(60)


threading.Thread(target=consume_signals, daemon=True).start()
threading.Thread(target=mtm_loop, daemon=True).start()


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/paper/account")
def account():
    engine.sync_account()
    row = db.get_paper_account("default")
    return jsonify(row or {})


@app.route("/paper/positions")
def positions():
    return jsonify(db.get_paper_positions("default"))


@app.route("/paper/orders")
def orders():
    status = request.args.get("status")
    return jsonify(db.get_paper_orders(status=status, limit=100))


@app.route("/paper/trades")
def trades():
    return jsonify(db.get_paper_trades("default", limit=100))


@app.route("/paper/order", methods=["POST"])
def manual_order():
    data = request.get_json() or {}
    order = alpaca.place_order(
        data["ticker"],
        data["qty"],
        data["side"],
        order_type=data.get("order_type", "market"),
        limit_price=data.get("price"),
    )
    return jsonify(order)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8088")))
