import numpy as np
import polars as pl

from qsip.features import compute_filing_features, compute_news_features, compute_price_features


def test_compute_price_features():
    n = 100
    df = pl.DataFrame({
        "time": ["2024-01-01"] * n,
        "close": np.cumsum(np.random.randn(n) * 0.5 + 100),
        "volume": np.random.randint(1_000_000, 10_000_000, n),
    })
    feats = compute_price_features(df)
    assert "return_1d" in feats
    assert "volume_ratio" in feats
    assert "rsi_14" in feats


def test_compute_filing_features():
    filings = [
        {"payload": {"transaction_code": "P", "shares": 10000, "price": 50}},
        {"payload": {"transaction_code": "S", "shares": 5000, "price": 55}},
    ]
    feats = compute_filing_features(filings)
    assert feats["insider_buy_ratio"] == 0.5
    assert feats["insider_buy_dollars_30d"] == 500_000


def test_compute_news_features():
    articles = [{"sentiment_score": 0.8}, {"sentiment_score": -0.2}]
    feats = compute_news_features(articles)
    assert feats["news_sentiment_mean"] == 0.3
