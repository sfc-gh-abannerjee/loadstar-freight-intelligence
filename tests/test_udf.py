"""Tests for ML.GET_RECOMMENDATION_SCORE UDF edge cases."""
import pytest


@pytest.mark.sql
@pytest.mark.live
class TestUDF:
    """Verify GET_RECOMMENDATION_SCORE returns valid values for various inputs."""

    def _call_udf(self, sf_session, driver_id, load_id):
        result = sf_session.sql(
            f"SELECT APEX_CAPITAL_DEMO.ML.GET_RECOMMENDATION_SCORE({driver_id}, {load_id}) AS score"
        ).collect()
        return result[0]["SCORE"]

    def test_basic_call(self, sf_session):
        score = self._call_udf(sf_session, 1, 1)
        assert score is not None, "UDF returned NULL for (1, 1)"
        assert 0.0 <= score <= 1.0, f"Score {score} out of range [0, 1]"

    def test_high_ids(self, sf_session):
        score = self._call_udf(sf_session, 999, 999)
        assert score is not None, "UDF returned NULL for (999, 999)"
        assert 0.0 <= score <= 1.0, f"Score {score} out of range [0, 1]"

    def test_mixed_ids(self, sf_session):
        score = self._call_udf(sf_session, 1, 100)
        assert score is not None, "UDF returned NULL for (1, 100)"
        assert 0.0 <= score <= 1.0, f"Score {score} out of range [0, 1]"

    def test_returns_float(self, sf_session):
        score = self._call_udf(sf_session, 5, 5)
        assert isinstance(score, float), f"Expected float, got {type(score)}"
