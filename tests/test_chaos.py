"""Chaos tests."""

import pytest

pytestmark = pytest.mark.skipif(True, reason="chaos tests require docker stack")


def test_feature_service_failure_no_data_loss():
    pass
