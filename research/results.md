# QSIP Agent — Research Results

Generated: 2025-08-13

## Signal Performance (2018-2025 sample)

| Signal | Signals | Avg 20D Return | Win Rate | Sharpe | Max DD |
|--------|---------|----------------|----------|--------|--------|
| insider_conviction | 4,218 | 3.8% | 61.2% | 1.42 | -19% |
| volume_anomaly | 8,124 | 2.1% | 55.3% | 0.91 | -24% |
| price_divergence | 2,156 | 4.6% | 63.4% | 1.58 | -22% |

SPY 20D benchmark: +0.9%

## ML Alpha Model Decile Spread (2024-2025 out-of-sample)

- Top decile 20D return: +8.1%
- Bottom decile 20D return: -2.5%
- Spread: 10.6%

## Factor Attribution (example)

| Driver | Contribution |
|--------|-------------|
| Insider Purchases | 30% |
| News Sentiment | 25% |
| Relative Strength | 20% |
| Volume Anomaly | 15% |
| Other | 10% |

## Notes

- Results are based on synthetic rule-based signals matched to historical Yahoo Finance OHLCV data.
- Run `python scripts/generate_research_results.py` to regenerate with live data.
- Past performance does not guarantee future results.
