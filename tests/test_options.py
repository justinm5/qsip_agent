from qsip.options import OptionsFlowClient


def test_activity_score():
    client = OptionsFlowClient()
    assert client._activity_score(100, 50, 10) == 10.0
    assert client._activity_score(0, 50, 10) == 0.0
