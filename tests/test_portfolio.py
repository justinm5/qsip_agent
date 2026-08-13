from datetime import datetime, timedelta

import polars as pl

from qsip.portfolio import PortfolioEngine


def test_build_portfolio():
    engine = PortfolioEngine(initial_cash=100_000, max_positions=3)
    signals = [
        {"ticker": "A", "direction": "long", "score": 0.9, "ml_score": 0.8, "timestamp": datetime.utcnow().isoformat()},
        {"ticker": "B", "direction": "long", "score": 0.8, "ml_score": 0.7, "timestamp": datetime.utcnow().isoformat()},
        {"ticker": "C", "direction": "long", "score": 0.7, "ml_score": 0.6, "timestamp": datetime.utcnow().isoformat()},
        {"ticker": "D", "direction": "short", "score": 0.9, "ml_score": 0.8, "timestamp": datetime.utcnow().isoformat()},
    ]
    holdings = engine.build_portfolio(signals)
    assert len(holdings) == 3
    assert all(h["weight"] == 1.0 / 3 for h in holdings)


def test_simulate():
    engine = PortfolioEngine(initial_cash=100_000, max_positions=2)
    start = datetime.utcnow() - timedelta(days=30)
    times = [start + timedelta(days=i) for i in range(30)]
    price_lookup = {
        "A": pl.DataFrame({
            "time": times,
            "close": [100.0 + i for i in range(30)],
        }),
        "B": pl.DataFrame({
            "time": times,
            "close": [100.0 - i * 0.5 for i in range(30)],
        }),
    }
    signals = [
        {"ticker": "A", "direction": "long", "score": 0.9, "ml_score": 0.8, "timestamp": start.isoformat()},
        {"ticker": "B", "direction": "long", "score": 0.8, "ml_score": 0.7, "timestamp": start.isoformat()},
    ]
    result = engine.simulate(signals, price_lookup)
    assert result["total_value"] != 0
    assert "sharpe" in result
