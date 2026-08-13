from qsip.signals import SignalEngine


def test_insider_conviction_signal():
    engine = SignalEngine(model_path="/tmp")
    features = {
        "insider_buy_ratio": 0.9,
        "insider_buy_dollars_30d": 2_000_000,
        "return_20d": -0.02,
        "volume_ratio": 1.0,
        "news_sentiment_mean": 0.0,
    }
    signals = engine.generate("AAPL", features)
    assert any(s["signal_type"] == "insider_conviction" for s in signals)


def test_volume_anomaly_signal():
    engine = SignalEngine(model_path="/tmp")
    features = {
        "volume_ratio": 5.0,
        "return_1d": 0.02,
        "insider_buy_ratio": 0.0,
    }
    signals = engine.generate("TSLA", features)
    assert any(s["signal_type"] == "volume_anomaly" for s in signals)


def test_price_divergence_signal():
    engine = SignalEngine(model_path="/tmp")
    features = {
        "insider_net_dollars_30d": 1_000_000,
        "return_20d": -0.20,
    }
    signals = engine.generate("MSFT", features)
    assert any(s["signal_type"] == "price_divergence" for s in signals)


def test_earnings_guidance_signal():
    engine = SignalEngine(model_path="/tmp")
    features = {"guidance_change": 1.0, "earnings_sentiment": 0.8}
    signals = engine.generate("NVDA", features)
    assert any(s["signal_type"] == "earnings_guidance" for s in signals)


def test_options_activity_signal():
    engine = SignalEngine(model_path="/tmp")
    features = {"options_activity_score": 8.0, "call_put_ratio": 5.0}
    signals = engine.generate("AMD", features)
    assert any(s["signal_type"] == "options_activity" for s in signals)


def test_ml_alpha_signal():
    engine = SignalEngine(model_path="/tmp")
    # No rules triggered, no model -> no signals
    features = {"volume_ratio": 1.0, "insider_buy_ratio": 0.0, "guidance_change": 0.0}
    signals = engine.generate("SPY", features)
    assert not any(s["signal_type"] == "ml_alpha" for s in signals)
