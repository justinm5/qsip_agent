from qsip.earnings import EarningsTranscriptClient


def test_guidance_change():
    client = EarningsTranscriptClient()
    text = "We are raising guidance due to strong demand and confident outlook."
    assert client._guidance_change(text) == "raised"


def test_sentiment_word_ratio():
    client = EarningsTranscriptClient()
    text = "strong growth confident robust opportunity"
    score = client._sentiment_word_ratio(text, positive=True)
    assert score > 0


def test_parse_transcript():
    client = EarningsTranscriptClient()
    t = client._parse_transcript("AAPL", "2024-08-13T12:00:00", "We beat earnings and raised guidance.", "test")
    assert t["guidance_change"] == "raised"
