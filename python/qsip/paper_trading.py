from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AlpacaPaperClient:
    """Alpaca paper trading client. Falls back to simulated fills if no keys."""

    def __init__(self, api_key: str = "", secret_key: str = "", paper: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        self.simulated = not (api_key and secret_key)
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": secret_key,
            } if not self.simulated else {},
            timeout=30.0,
        )

    def place_order(self, symbol: str, qty: float, side: str, order_type: str = "market", limit_price: float | None = None) -> dict[str, Any]:
        if self.simulated:
            return self._simulated_order(symbol, qty, side, order_type, limit_price)
        body = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": "day",
        }
        if limit_price and order_type == "limit":
            body["limit_price"] = str(limit_price)
        r = self.client.post("/v2/orders", json=body)
        r.raise_for_status()
        return r.json()

    def get_account(self) -> dict[str, Any]:
        if self.simulated:
            return self._simulated_account()
        r = self.client.get("/v2/account")
        r.raise_for_status()
        return r.json()

    def get_positions(self) -> list[dict[str, Any]]:
        if self.simulated:
            return []
        r = self.client.get("/v2/positions")
        r.raise_for_status()
        return r.json()

    def _simulated_order(self, symbol: str, qty: float, side: str, order_type: str, limit_price: float | None = None) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "client_order_id": f"sim-{uuid.uuid4().hex[:8]}",
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "status": "filled",
            "filled_qty": str(qty),
            "filled_avg_price": str(limit_price or 100.0),
        }

    def _simulated_account(self) -> dict[str, Any]:
        return {
            "cash": "100000.00",
            "equity": "100000.00",
            "buying_power": "200000.00",
            "daytrading_buying_power": "200000.00",
            "status": "ACTIVE",
        }


class PaperTradingEngine:
    """Convert signals into paper trades and track positions/PnL."""

    def __init__(self, db: Any, alpaca: AlpacaPaperClient, initial_cash: float = 100_000.0):
        self.db = db
        self.alpaca = alpaca
        self.initial_cash = initial_cash
        self.strategy = "default"

    def sync_account(self):
        acc = self.alpaca.get_account()
        self.db.upsert_paper_account({
            "strategy": self.strategy,
            "cash": float(acc.get("cash", 0)),
            "equity": float(acc.get("equity", 0)),
            "buying_power": float(acc.get("buying_power", 0)),
            "day_trading_buying_power": float(acc.get("daytrading_buying_power", 0)),
        })

    def on_signal(self, signal: dict[str, Any]):
        """Receive a signal and place a paper order."""
        ticker = signal["ticker"]
        direction = signal.get("direction", "long")
        side = "buy" if direction == "long" else "sell"

        # Simple sizing: 5% of current equity per signal
        account = self.db.get_paper_account(self.strategy)
        equity = account["equity"] if account else self.initial_cash
        risk_pct = 0.05
        notional = equity * risk_pct

        # Use latest market price to size qty (fallback to 100)
        price = self._last_price(ticker) or 100.0
        qty = notional / price
        if qty <= 0:
            return

        order = self.alpaca.place_order(ticker, qty, side)
        self.db.insert_paper_order({
            "order_id": order.get("id") or order.get("client_order_id"),
            "ticker": ticker,
            "side": side,
            "qty": float(order.get("qty", qty)),
            "order_type": order.get("type", "market"),
            "limit_price": None,
            "status": order.get("status", "filled"),
            "filled_qty": float(order.get("filled_qty", 0)),
            "filled_avg_price": float(order.get("filled_avg_price", price) or price),
            "broker": "alpaca" if not self.alpaca.simulated else "simulated",
            "strategy": self.strategy,
            "signal_id": signal.get("signal_id"),
        })

        if order.get("status") == "filled":
            self._update_position(ticker, side, float(order.get("filled_qty", qty)), float(order.get("filled_avg_price", price)))
            self.db.insert_paper_trade({
                "trade_id": str(uuid.uuid4()),
                "order_id": order.get("id"),
                "ticker": ticker,
                "side": side,
                "qty": float(order.get("filled_qty", qty)),
                "price": float(order.get("filled_avg_price", price)),
                "total_value": float(order.get("filled_qty", qty)) * float(order.get("filled_avg_price", price)),
                "strategy": self.strategy,
                "signal_id": signal.get("signal_id"),
            })
        self.sync_account()

    def _update_position(self, ticker: str, side: str, qty: float, price: float):
        pos = self.db.get_paper_positions(self.strategy)
        existing = next((p for p in pos if p["ticker"] == ticker), None)
        if not existing:
            self.db.upsert_paper_position({
                "ticker": ticker,
                "qty": qty if side == "buy" else -qty,
                "avg_entry_price": price,
                "market_price": price,
                "market_value": qty * price,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "side": "long" if side == "buy" else "short",
                "strategy": self.strategy,
            })
            return
        old_qty = existing["qty"]
        old_avg = existing["avg_entry_price"] or price
        if side == "buy":
            new_qty = old_qty + qty
            new_avg = (old_qty * old_avg + qty * price) / new_qty if new_qty else old_avg
        else:
            new_qty = old_qty - qty
            realized = (price - old_avg) * min(old_qty, qty)
            new_avg = old_avg if new_qty > 0 else 0.0
            existing["realized_pnl"] = (existing.get("realized_pnl", 0) or 0) + realized
        self.db.upsert_paper_position({
            "ticker": ticker,
            "qty": new_qty,
            "avg_entry_price": new_avg,
            "market_price": price,
            "market_value": abs(new_qty) * price,
            "unrealized_pnl": (price - new_avg) * new_qty if new_qty > 0 else 0,
            "realized_pnl": existing.get("realized_pnl", 0),
            "side": "long" if new_qty > 0 else "short" if new_qty < 0 else "flat",
            "strategy": self.strategy,
        })

    def _last_price(self, ticker: str) -> float | None:
        # Try DB first
        rows = self.db.get_market_data(ticker, days=1)
        if rows:
            return float(rows[-1]["close"])
        return None

    def mark_to_market(self):
        positions = self.db.get_paper_positions(self.strategy)
        total_value = 0.0
        for pos in positions:
            price = self._last_price(pos["ticker"]) or pos["market_price"]
            qty = pos["qty"]
            market_value = abs(qty) * price
            unrealized = (price - pos["avg_entry_price"]) * qty if qty > 0 else (pos["avg_entry_price"] - price) * abs(qty)
            self.db.upsert_paper_position({
                "ticker": pos["ticker"],
                "qty": qty,
                "avg_entry_price": pos["avg_entry_price"],
                "market_price": price,
                "market_value": market_value,
                "unrealized_pnl": unrealized,
                "realized_pnl": pos.get("realized_pnl", 0),
                "side": pos.get("side"),
                "strategy": self.strategy,
            })
            total_value += market_value
        account = self.db.get_paper_account(self.strategy)
        if account:
            self.db.upsert_paper_account({
                "strategy": self.strategy,
                "cash": account["cash"],
                "equity": account["cash"] + total_value,
                "buying_power": account["buying_power"],
                "day_trading_buying_power": account.get("day_trading_buying_power"),
            })
