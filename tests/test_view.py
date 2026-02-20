"""Tests for ANALYTICS.LOADSTAR_RECOMMENDATIONS_V view correctness."""
import pytest


@pytest.mark.sql
@pytest.mark.live
class TestRecommendationsView:
    """Verify LOADSTAR_RECOMMENDATIONS_V is well-formed."""

    def test_view_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW VIEWS LIKE 'LOADSTAR_RECOMMENDATIONS_V' IN SCHEMA APEX_CAPITAL_DEMO.ANALYTICS"
        ).collect()
        assert len(result) > 0, "View ANALYTICS.LOADSTAR_RECOMMENDATIONS_V does not exist"

    def test_has_rows(self, sf_session):
        result = sf_session.sql(
            "SELECT COUNT(*) AS cnt FROM APEX_CAPITAL_DEMO.ANALYTICS.LOADSTAR_RECOMMENDATIONS_V"
        ).collect()
        assert result[0]["CNT"] > 0, "LOADSTAR_RECOMMENDATIONS_V is empty"

    def test_score_range(self, sf_session):
        """All scores should be in [0.0, 1.0]."""
        result = sf_session.sql("""
            SELECT MIN(RECOMMENDATION_SCORE) AS min_score, MAX(RECOMMENDATION_SCORE) AS max_score
            FROM APEX_CAPITAL_DEMO.ANALYTICS.LOADSTAR_RECOMMENDATIONS_V
        """).collect()
        min_score = result[0]["MIN_SCORE"]
        max_score = result[0]["MAX_SCORE"]
        if min_score is not None:
            assert min_score >= 0.0, f"Min score {min_score} is below 0"
        if max_score is not None:
            assert max_score <= 1.0, f"Max score {max_score} is above 1"

    def test_no_null_driver_ids(self, sf_session):
        result = sf_session.sql("""
            SELECT COUNT(*) AS cnt
            FROM APEX_CAPITAL_DEMO.ANALYTICS.LOADSTAR_RECOMMENDATIONS_V
            WHERE DRIVER_ID IS NULL
        """).collect()
        assert result[0]["CNT"] == 0, "Found rows with NULL DRIVER_ID"

    def test_no_null_load_ids(self, sf_session):
        result = sf_session.sql("""
            SELECT COUNT(*) AS cnt
            FROM APEX_CAPITAL_DEMO.ANALYTICS.LOADSTAR_RECOMMENDATIONS_V
            WHERE LOAD_ID IS NULL
        """).collect()
        assert result[0]["CNT"] == 0, "Found rows with NULL LOAD_ID"
