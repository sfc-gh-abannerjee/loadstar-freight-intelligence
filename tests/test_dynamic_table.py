"""Tests for ANALYTICS.BROKER_360 dynamic table health."""
import pytest


@pytest.mark.sql
@pytest.mark.live
class TestDynamicTable:
    """Verify BROKER_360 dynamic table is healthy."""

    def test_has_expected_columns(self, sf_session):
        result = sf_session.sql(
            "DESCRIBE TABLE APEX_CAPITAL_DEMO.ANALYTICS.BROKER_360"
        ).collect()
        col_count = len(result)
        assert col_count >= 25, f"Expected >= 25 columns, got {col_count}"

    def test_has_rows(self, sf_session):
        result = sf_session.sql(
            "SELECT COUNT(*) AS cnt FROM APEX_CAPITAL_DEMO.ANALYTICS.BROKER_360"
        ).collect()
        assert result[0]["CNT"] > 0, "BROKER_360 has no rows"

    def test_refresh_status(self, sf_session):
        result = sf_session.sql(
            "SHOW DYNAMIC TABLES LIKE 'BROKER_360' IN SCHEMA APEX_CAPITAL_DEMO.ANALYTICS"
        ).collect()
        assert len(result) > 0, "Dynamic table not found"
        row_dict = result[0].as_dict()
        scheduling_state = row_dict.get("scheduling_state", "UNKNOWN")
        assert scheduling_state in ("ACTIVE", "RUNNING"), (
            f"BROKER_360 scheduling state is {scheduling_state}, expected ACTIVE or RUNNING"
        )

    def test_no_null_primary_keys(self, sf_session):
        """Broker ID should never be NULL in the golden record."""
        result = sf_session.sql(
            "SELECT COUNT(*) AS cnt FROM APEX_CAPITAL_DEMO.ANALYTICS.BROKER_360 WHERE BROKER_ID IS NULL"
        ).collect()
        assert result[0]["CNT"] == 0, "Found rows with NULL BROKER_ID in BROKER_360"
