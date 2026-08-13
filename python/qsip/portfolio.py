from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class Portfolio:
    strategy: str
    cash: float
    positions: dict[str, dict[str, Any]]
    value_history: list[tuple[datetime, float]]


class PortfolioEngine:
    """Equal-weight portfolio simulation with weekly rebalance."""

    def __init__(self, initial_cash: float = 1_000_000.0, max_positions: int = 20):
        self.initial_cash = initial_cash
        self.max_positions = max_positions

    def build_portfolio(self, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Select top N long signals equal weight."""
        longs = [s for s in signals if s.get("direction") == "long"]
        longs.sort(key=lambda s: s.get("score", 0) * s.get("ml_score", 0.5), reverse=True)
        selected = longs[: self.max_positions]
        if not selected:
            return []
        weight = 1.0 / len(selected)
        holdings = []
        for s in selected:
            holdings.append({
                "ticker": s["ticker"],
                "weight": weight,
                "signal_id": s.get("signal_id"),
                "entry_score": s.get("score"),
            })
        return holdings

    def simulate(
        self,
        signals: list[dict[str, Any]],
        price_lookup: dict[str, pl.DataFrame],
        rebalance_days: int = 7,
    ) -> dict[str, Any]:
        """Simple walk-forward simulation."""
        start_date = datetime.utcnow() - timedelta(days=180)
        end_date = datetime.utcnow()
        cash = self.initial_cash
        positions: dict[str, dict[str, Any]] = {}
        nav_history: list[tuple[datetime, float]] = []

        current_date = start_date
        while current_date <= end_date:
            day_signals = [s for s in signals if datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00")).date() == current_date.date()]
            if day_signals and (len(nav_history) == 0 or (current_date - nav_history[-1][0]).days >= rebalance_days):
                new_holdings = self.build_portfolio(day_signals)
                positions = {}
                portfolio_value = cash
                for h in new_holdings:
                    ticker = h["ticker"]
                    df = price_lookup.get(ticker)
                    if df is None or df.height == 0:
                        continue
                    price = self._price_on(df, current_date)
                    if price is None or price <= 0:
                        continue
                    allocation = portfolio_value * h["weight"]
                    shares = allocation / price
                    positions[ticker] = {"shares": shares, "entry_price": price, "weight": h["weight"]}
                # mark cash as residual
                invested = sum(pos[ticker]["shares"] * pos[ticker]["entry_price"] for ticker in positions)
                cash = portfolio_value - invested

            # mark-to-market
            total = cash
            for ticker, pos in positions.items():
                df = price_lookup.get(ticker)
                if df is None or df.height == 0:
                    continue
                price = self._price_on(df, current_date)
                if price:
                    total += pos["shares"] * price
            nav_history.append((current_date, total))
            current_date += timedelta(days=1)

        returns = self._returns_from_nav(nav_history)
        metrics = self._compute_metrics(returns)
        latest_holdings = []
        for ticker, pos in positions.items():
            df = price_lookup.get(ticker)
            price = self._price_on(df, nav_history[-1][0]) if df is not None and df.height > 0 else pos["entry_price"]
            latest_holdings.append({
                "ticker": ticker,
                "shares": pos["shares"],
                "weight": pos["weight"],
                "entry_price": pos["entry_price"],
                "market_price": price,
                "pnl": (price - pos["entry_price"]) * pos["shares"],
            })

        return {
            "strategy": "equal_weight_top20",
            "nav": nav_history[-1][1] if nav_history else self.initial_cash,
            "cash": cash,
            "total_value": nav_history[-1][1] if nav_history else self.initial_cash,
            "return_1d": metrics.get("return_1d", 0.0),
            "return_1w": metrics.get("return_1w", 0.0),
            "return_1m": metrics.get("return_1m", 0.0),
            "sharpe": metrics.get("sharpe", 0.0),
            "sortino": metrics.get("sortino", 0.0),
            "max_drawdown": metrics.get("max_drawdown", 0.0),
            "alpha": metrics.get("alpha", 0.0),
            "beta": metrics.get("beta", 0.0),
            "holdings": latest_holdings,
            "nav_history": [(t.isoformat(), v) for t, v in nav_history[-30:]],
        }

    def _price_on(self, df: pl.DataFrame, dt: datetime) -> float | None:
        if df.height == 0:
            return None
        if "time" not in df.columns:
            return None
        row = df.filter(pl.col("time").cast(pl.Date) == dt.date()).tail(1)
        if row.height == 0:
            return None
        return float(row["close"][0])

    def _returns_from_nav(self, nav_history: list[tuple[datetime, float]]) -> np.ndarray:
        if len(nav_history) < 2:
            return np.array([])
        vals = np.array([v for _, v in nav_history])
        return np.diff(vals) / vals[:-1]

    def _compute_metrics(self, returns: np.ndarray) -> dict[str, float]:
        if len(returns) == 0:
            return {}
        total = np.prod(1 + returns) - 1
        sharpe = (np.mean(returns) * 252) / (np.std(returns) * np.sqrt(252) + 1e-9)
        downside = returns[returns < 0]
        sortino = (np.mean(returns) * 252) / (np.std(downside) * np.sqrt(252) + 1e-9) if len(downside) > 0 else 0.0
        cum = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(cum)
        dd = (cum - peak) / peak
        max_dd = float(np.min(dd))
        return {
            "return_1d": float(returns[-1]),
            "return_1w": float(np.prod(1 + returns[-5:]) - 1) if len(returns) >= 5 else 0.0,
            "return_1m": float(np.prod(1 + returns[-20:]) - 1) if len(returns) >= 20 else 0.0,
            "total_return": float(total),
            "sharpe": float(sharpe),
            "sortino": float(sortino),
            "max_drawdown": float(max_dd),
            "alpha": 0.0,
            "beta": 1.0,
        }
