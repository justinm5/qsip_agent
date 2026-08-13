import hashlib
import html
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any

import feedparser
import httpx
from bs4 import BeautifulSoup
from prometheus_client import Counter, Histogram, start_http_server
from transformers import pipeline

from qsip.config import Config
from qsip.db import TimescaleDB
from qsip.kafka_client import KafkaProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ARTICLES_PROCESSED = Counter("news_articles_processed_total", "News articles processed", ["source"])
ARTICLE_LATENCY = Histogram("news_article_process_seconds", "News article processing latency")

RSS_FEEDS = [
    "https://www.marketwatch.com/rss/topstories",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&start=0&count=100&output=atom",
    "https://seekingalpha.com/feed.xml",
]


class NewsService:
    def __init__(self):
        self.cfg = Config.from_env()
        self.db = TimescaleDB(self.cfg.db_dsn)
        self.producer = KafkaProducer(self.cfg.kafka_brokers)
        self.client = httpx.Client(timeout=30.0, headers={"User-Agent": "QSIP/0.1"})
        try:
            self.sentiment = pipeline("sentiment-analysis", model="ProsusAI/finbert", device=-1)
        except Exception as e:
            logger.warning("FinBERT load failed, using fallback: %s", e)
            self.sentiment = None

    def run(self):
        start_http_server(int(os.getenv("METRICS_PORT", "9091")))
        while True:
            self._fetch_rss()
            self._fetch_newsapi()
            self._fetch_finnhub()
            time.sleep(120)

    def _fetch_rss(self):
        for url in RSS_FEEDS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:50]:
                    self._process_article(entry.get("link", ""), entry.get("title", ""), entry.get("summary", ""), "rss")
                ARTICLES_PROCESSED.labels(source="rss").inc(len(feed.entries))
            except Exception as e:
                logger.error("rss fetch failed %s: %s", url, e)

    def _fetch_newsapi(self):
        if not self.cfg.newsapi_key:
            return
        try:
            r = self.client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": "stock market OR earnings OR insider trading",
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 100,
                    "apiKey": self.cfg.newsapi_key,
                },
            )
            r.raise_for_status()
            for a in r.json().get("articles", []):
                self._process_article(a.get("url"), a.get("title"), a.get("description"), "newsapi")
            ARTICLES_PROCESSED.labels(source="newsapi").inc(len(r.json().get("articles", [])))
        except Exception as e:
            logger.error("newsapi fetch failed: %s", e)

    def _fetch_finnhub(self):
        if not self.cfg.finnhub_key:
            return
        try:
            r = self.client.get(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": self.cfg.finnhub_key},
            )
            r.raise_for_status()
            for a in r.json():
                self._process_article(a.get("url"), a.get("headline"), a.get("summary"), "finnhub")
            ARTICLES_PROCESSED.labels(source="finnhub").inc(len(r.json()))
        except Exception as e:
            logger.error("finnhub fetch failed: %s", e)

    def _process_article(self, url: str, title: str, summary: str, source: str):
        if not url:
            return
        url = url.split("?")[0]
        article_id = hashlib.sha256(url.encode()).hexdigest()[:16]
        text = f"{title} {summary}"
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        tickers = self._extract_tickers(text)
        sentiment = self._analyze(text)

        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO news_articles (url, title, source, published_at, ticker, content, sentiment_score, sentiment_label)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE SET
                    sentiment_score = EXCLUDED.sentiment_score,
                    sentiment_label = EXCLUDED.sentiment_label
                """,
                (
                    url,
                    title,
                    source,
                    datetime.utcnow(),
                    tickers[0] if tickers else None,
                    text,
                    sentiment["score"],
                    sentiment["label"],
                ),
            )

        for ticker in tickers:
            event = {
                "event_id": article_id,
                "source": "news-service",
                "event_type": "news_article",
                "ticker": ticker,
                "timestamp": datetime.utcnow().isoformat(),
                "payload": {
                    "url": url,
                    "title": title,
                    "sentiment_score": sentiment["score"],
                    "sentiment_label": sentiment["label"],
                },
            }
            self.producer.send("raw-events", ticker, event)

    def _extract_tickers(self, text: str) -> list[str]:
        # Naive ticker extraction; in production use NER or mapping
        return list(set(re.findall(r"\b[A-Z]{1,5}\b", text)))[:5]

    def _analyze(self, text: str) -> dict[str, Any]:
        with ARTICLE_LATENCY.time():
            if not self.sentiment or not text:
                return {"label": "neutral", "score": 0.0}
            try:
                result = self.sentiment(text[:512])[0]
                label = result["label"].lower()
                score = float(result["score"])
                if label == "negative":
                    score = -score
                return {"label": label, "score": score}
            except Exception as e:
                logger.warning("sentiment analysis failed: %s", e)
                return {"label": "neutral", "score": 0.0}


if __name__ == "__main__":
    NewsService().run()
