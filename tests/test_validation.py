import pytest

from qsip.validation import DataValidator


@pytest.fixture
def validator():
    return DataValidator(db=None, redis=None)


def test_valid_event(validator):
    event = {
        "event_id": "1",
        "source": "sec",
        "event_type": "4",
        "ticker": "AAPL",
        "timestamp": "2024-08-13T12:00:00",
        "payload": {"accession": "0001"},
    }
    ok, issues = validator.validate(event)
    assert ok
    assert not issues


def test_duplicate_event(validator):
    event = {
        "event_id": "dup",
        "source": "sec",
        "event_type": "4",
        "ticker": "AAPL",
        "timestamp": "2024-08-13T12:00:00",
        "payload": {},
    }
    ok, _ = validator.validate(event)
    ok2, issues2 = validator.validate(event)
    assert ok2
    assert any(i["issue_type"] == "duplicate" for i in issues2)


def test_bad_timestamp(validator):
    event = {
        "event_id": "2",
        "source": "sec",
        "event_type": "4",
        "ticker": "AAPL",
        "timestamp": "2099-08-13T12:00:00",
        "payload": {},
    }
    ok, issues = validator.validate(event)
    assert not ok
    assert any(i["issue_type"] == "bad_timestamp" for i in issues)


def test_price_outlier(validator):
    import polars as pl
    df = pl.DataFrame({
        "time": ["2024-08-13"] * 30,
        "close": [100.0] * 30,
        "high": [101.0] * 30,
        "low": [99.0] * 30,
        "volume": [1_000_000] * 29 + [500_000_000],
    })
    cleaned, issues = validator.validate_price_frame(df)
    assert any(i["issue_type"] == "volume_outlier" for i in issues)


def test_bad_ohlc(validator):
    import polars as pl
    df = pl.DataFrame({
        "time": ["2024-08-13"],
        "close": [-1.0],
        "high": [90.0],
        "low": [100.0],
        "volume": [1000],
    })
    cleaned, issues = validator.validate_price_frame(df)
    assert any(i["issue_type"] == "bad_ohlc" for i in issues)
    assert cleaned.height == 0
