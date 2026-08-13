"""End-to-end pipeline test (requires running services or testcontainers)."""

import pytest

pytestmark = pytest.mark.skipif(True, reason="e2e requires full docker stack")


def test_full_pipeline():
    """SEC filing -> Kafka -> Feature -> Signal -> Timescale -> API -> UI."""
    pass
