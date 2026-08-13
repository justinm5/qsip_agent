"""Train XGBoost/LightGBM alpha model on feature vectors."""

import argparse
import json
import logging
import os
import pickle

import numpy as np
import polars as pl
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

from qsip.config import Config
from qsip.db import TimescaleDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FEATURE_KEYS = [
    "return_1d", "return_5d", "return_20d", "return_60d",
    "volatility_20d", "volume_ratio", "rsi_14", "macd", "macd_signal",
    "bb_position", "zscore_20d",
    "insider_buys_30d", "insider_sells_30d", "insider_buy_ratio",
    "insider_buy_dollars_30d", "insider_sell_dollars_30d", "insider_net_dollars_30d",
    "news_sentiment_mean", "news_sentiment_std", "news_count_24h",
]


def load_data(db: TimescaleDB, min_rows: int = 1000) -> pl.DataFrame:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT timestamp, ticker, features, target_return_20d
            FROM feature_vectors
            WHERE target_return_20d IS NOT NULL
            ORDER BY timestamp ASC
            """
        )
        rows = cur.fetchall()
    logger.info("loaded %d labeled feature vectors", len(rows))
    if len(rows) < min_rows:
        raise ValueError(f"need at least {min_rows} labeled rows")

    parsed = []
    for r in rows:
        features = r["features"] if isinstance(r["features"], dict) else json.loads(r["features"])
        row = {"timestamp": r["timestamp"], "ticker": r["ticker"], "target": r["target_return_20d"]}
        row.update({k: float(features.get(k, 0.0)) for k in FEATURE_KEYS})
        parsed.append(row)
    return pl.DataFrame(parsed)


def train(df: pl.DataFrame, model_type: str = "xgboost"):
    X = df.select(FEATURE_KEYS).to_numpy()
    y = df["target"].to_numpy()

    tscv = TimeSeriesSplit(n_splits=5)
    scores = []
    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        if model_type == "xgboost":
            model = xgb.XGBRegressor(
                n_estimators=500,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                objective="reg:squarederror",
                eval_metric="rmse",
                early_stopping_rounds=20,
            )
            model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
        elif model_type == "lightgbm":
            import lightgbm as lgb
            model = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.05, max_depth=6)
            model.fit(X_train, y_train)
        elif model_type == "random_forest":
            model = RandomForestRegressor(n_estimators=200, max_depth=10, n_jobs=-1)
            model.fit(X_train, y_train)
        else:
            raise ValueError(f"unknown model type {model_type}")

        preds = model.predict(X_test)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        r2 = r2_score(y_test, preds)
        scores.append({"rmse": rmse, "r2": r2})
        logger.info("fold rmse=%.4f r2=%.4f", rmse, r2)

    # Train final model on all data
    if model_type == "xgboost":
        final = xgb.XGBRegressor(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
        )
    elif model_type == "lightgbm":
        import lightgbm as lgb
        final = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.05, max_depth=6)
    elif model_type == "random_forest":
        final = RandomForestRegressor(n_estimators=300, max_depth=12, n_jobs=-1)

    final.fit(X, y)
    return final, scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="xgboost", choices=["xgboost", "lightgbm", "random_forest"])
    parser.add_argument("--output", default="/models/xgb_model.pkl")
    args = parser.parse_args()

    cfg = Config.from_env()
    db = TimescaleDB(cfg.db_dsn)
    df = load_data(db)

    model, scores = train(df, args.model)
    logger.info("final CV scores: %s", scores)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "wb") as f:
        pickle.dump(model, f)
    logger.info("model saved to %s", args.output)


if __name__ == "__main__":
    main()
