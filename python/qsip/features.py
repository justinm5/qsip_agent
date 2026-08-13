from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)


def compute_price_features(df: pl.DataFrame) -> dict[str, float]:
    """Compute technical features from a Polars OHLCV frame."""
    if df.height < 60:
        return {}

    df = df.sort("time")
    close = df["close"].to_numpy()
    volume = df["volume"].to_numpy()

    returns = np.diff(close) / close[:-1]

    features: dict[str, float] = {
        "return_1d": float(returns[-1]),
        "return_5d": float(close[-1] / close[-5] - 1) if len(close) >= 5 else 0.0,
        "return_20d": float(close[-1] / close[-20] - 1) if len(close) >= 20 else 0.0,
        "return_60d": float(close[-1] / close[-60] - 1) if len(close) >= 60 else 0.0,
        "volatility_20d": float(np.std(returns[-20:]) * np.sqrt(252)) if len(returns) >= 20 else 0.0,
        "avg_volume_20d": float(np.mean(volume[-20:])),
        "volume_ratio": float(volume[-1] / np.mean(volume[-20:])) if len(volume) >= 20 and np.mean(volume[-20:]) > 0 else 1.0,
    }

    features["rsi_14"] = float(_rsi(close, 14)[-1]) if len(close) >= 14 else 50.0
    features["macd"], features["macd_signal"] = _macd(close)
    features["bb_position"] = float(_bollinger_position(close, 20))
    features["zscore_20d"] = float(_zscore(close, 20))

    return features


def compute_filing_features(filings: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate SEC filing signals into numeric features."""
    buys = sells = total_buy = total_sell = 0.0
    for f in filings:
        payload = f.get("payload", {}) if isinstance(f.get("payload"), dict) else {}
        shares = float(payload.get("shares", 0) or 0)
        price = float(payload.get("price", 0) or 0)
        trans = payload.get("transaction_code", "")
        if trans in ("P", "J"):
            buys += 1
            total_buy += shares * price
        elif trans in ("S", "M"):
            sells += 1
            total_sell += shares * price

    total = buys + sells if (buys + sells) > 0 else 1
    return {
        "insider_buys_30d": float(buys),
        "insider_sells_30d": float(sells),
        "insider_buy_ratio": float(buys / total),
        "insider_buy_dollars_30d": float(total_buy),
        "insider_sell_dollars_30d": float(total_sell),
        "insider_net_dollars_30d": float(total_buy - total_sell),
    }


def compute_news_features(articles: list[dict[str, Any]]) -> dict[str, float]:
    scores = [float(a.get("sentiment_score", 0) or 0) for a in articles]
    if not scores:
        return {"news_sentiment_mean": 0.0, "news_sentiment_std": 0.0, "news_count_24h": 0.0}
    return {
        "news_sentiment_mean": float(np.mean(scores)),
        "news_sentiment_std": float(np.std(scores)),
        "news_count_24h": float(len(scores)),
    }


def build_feature_vector(
    ticker: str,
    price_features: dict[str, float],
    filing_features: dict[str, float],
    news_features: dict[str, float],
    metadata: dict[str, float] | None = None,
) -> dict[str, Any]:
    vector = {"ticker": ticker, "timestamp": datetime.utcnow().isoformat()}
    vector.update(price_features)
    vector.update(filing_features)
    vector.update(news_features)
    if metadata:
        vector.update(metadata)
    return vector


def _rsi(prices: np.ndarray, window: int = 14) -> np.ndarray:
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.convolve(gains, np.ones(window) / window, mode="valid")
    avg_loss = np.convolve(losses, np.ones(window) / window, mode="valid")
    rs = np.where(avg_loss == 0, 1e9, avg_gain / avg_loss)
    rsi = 100 - (100 / (1 + rs))
    pad = np.full(window, 50.0)
    return np.concatenate([pad, rsi])


def _macd(prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[float, float]:
    if len(prices) < slow + signal:
        return 0.0, 0.0
    ema_fast = _ema(prices, fast)
    ema_slow = _ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    return float(macd_line[-1]), float(signal_line[-1])


def _ema(series: np.ndarray, span: int) -> np.ndarray:
    alpha = 2 / (span + 1)
    ema = np.empty_like(series)
    ema[0] = series[0]
    for i in range(1, len(series)):
        ema[i] = alpha * series[i] + (1 - alpha) * ema[i - 1]
    return ema


def _bollinger_position(prices: np.ndarray, window: int = 20) -> float:
    if len(prices) < window:
        return 0.5
    ma = np.mean(prices[-window:])
    std = np.std(prices[-window:])
    if std == 0:
        return 0.5
    return float((prices[-1] - ma) / (2 * std))


def _zscore(prices: np.ndarray, window: int = 20) -> float:
    if len(prices) < window:
        return 0.0
    ma = np.mean(prices[-window:])
    std = np.std(prices[-window:])
    if std == 0:
        return 0.0
    return float((prices[-1] - ma) / std)
