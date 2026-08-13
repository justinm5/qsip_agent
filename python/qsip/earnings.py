from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EarningsTranscriptClient:
    """Fetch earnings transcripts and extract guidance / sentiment signals."""

    def __init__(self, alpha_vantage_key: str = "", fmp_key: str = ""):
        self.alpha_vantage_key = alpha_vantage_key
        self.fmp_key = fmp_key
        self.client = httpx.Client(timeout=30.0)

    def fetch(self, ticker: str) -> list[dict[str, Any]]:
        if self.fmp_key:
            return self._fetch_fmp(ticker)
        if self.alpha_vantage_key:
            return self._fetch_alpha_vantage(ticker)
        return []

    def _fetch_fmp(self, ticker: str) -> list[dict[str, Any]]:
        try:
            url = "https://financialmodelingprep.com/api/v4/earning_call_transcript"
            r = self.client.get(url, params={"symbol": ticker, "quarter": "1", "year": "2024", "apikey": self.fmp_key})
            r.raise_for_status()
            data = r.json()
            results = []
            for d in data:
                text = d.get("content", "")
                results.append(self._parse_transcript(ticker, d.get("date"), text, "fmp"))
            return results
        except Exception as e:
            logger.error("fmp earnings fetch failed: %s", e)
            return []

    def _fetch_alpha_vantage(self, ticker: str) -> list[dict[str, Any]]:
        try:
            url = "https://www.alphavantage.co/query"
            r = self.client.get(url, params={"function": "EARNINGS_CALL_TRANSCRIPT", "symbol": ticker, "apikey": self.alpha_vantage_key})
            r.raise_for_status()
            data = r.json()
            text = data.get("transcript", "")
            return [self._parse_transcript(ticker, datetime.utcnow().isoformat(), text, "alphavantage")]
        except Exception as e:
            logger.error("alpha vantage earnings fetch failed: %s", e)
            return []

    def _parse_transcript(self, ticker: str, call_date: str | None, text: str, source: str) -> dict[str, Any]:
        guidance = self._guidance_change(text)
        optimism = self._sentiment_word_ratio(text, positive=True)
        risk = self._sentiment_word_ratio(text, positive=False)
        return {
            "ticker": ticker,
            "call_date": call_date,
            "transcript_text": text[:50000],
            "guidance_change": guidance,
            "management_optimism_score": optimism,
            "risk_discussion_score": risk,
            "source": source,
        }

    def _guidance_change(self, text: str) -> str:
        lowered = text.lower()
        raised = len(re.findall(r"\b(raised|increased|upward|above prior|better than expected|strong guidance)\b", lowered))
        lowered_count = len(re.findall(r"\b(lowered|decreased|downward|below prior|weak guidance|cut guidance)\b", lowered))
        if raised > lowered_count:
            return "raised"
        if lowered_count > raised:
            return "lowered"
        return "unchanged"

    def _sentiment_word_ratio(self, text: str, positive: bool = True) -> float:
        words = text.lower().split()
        if not words:
            return 0.0
        if positive:
            markers = ["strong", "growth", "confident", "robust", "momentum", "opportunity", "exceeded", "beat"]
        else:
            markers = ["risk", "uncertainty", "challenge", "headwind", "decline", "pressure", "weak", "miss"]
        count = sum(1 for w in words if any(m in w for m in markers))
        return count / len(words)
