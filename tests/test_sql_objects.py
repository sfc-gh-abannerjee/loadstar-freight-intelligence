"""Tests for Snowflake object existence and basic data integrity."""
import pytest


@pytest.mark.sql
@pytest.mark.live
class TestObjectExistence:
    """Verify all deployed objects exist in APEX_CAPITAL_DEMO."""

    def test_dynamic_table_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW DYNAMIC TABLES LIKE 'BROKER_360' IN SCHEMA APEX_CAPITAL_DEMO.ANALYTICS"
        ).collect()
        assert len(result) > 0, "Dynamic table ANALYTICS.BROKER_360 does not exist"

    def test_semantic_view_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW SEMANTIC VIEWS LIKE 'APEX_BROKER_360_SV' IN SCHEMA APEX_CAPITAL_DEMO.ANALYTICS"
        ).collect()
        assert len(result) > 0, "Semantic view ANALYTICS.APEX_BROKER_360_SV does not exist"

    def test_agent_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW AGENTS LIKE 'APEX_BROKER_AGENT' IN SCHEMA APEX_CAPITAL_DEMO.ANALYTICS"
        ).collect()
        assert len(result) > 0, "Agent ANALYTICS.APEX_BROKER_AGENT does not exist"

    def test_udf_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW USER FUNCTIONS LIKE 'GET_RECOMMENDATION_SCORE' IN SCHEMA APEX_CAPITAL_DEMO.ML"
        ).collect()
        assert len(result) > 0, "UDF ML.GET_RECOMMENDATION_SCORE does not exist"

    def test_procedure_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW PROCEDURES LIKE 'POPULATE_RECOMMENDATIONS' IN SCHEMA APEX_CAPITAL_DEMO.ML"
        ).collect()
        assert len(result) > 0, "Procedure ML.POPULATE_RECOMMENDATIONS does not exist"

    def test_model_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW MODELS LIKE 'BROKER_RISK_NET' IN SCHEMA APEX_CAPITAL_DEMO.ML"
        ).collect()
        assert len(result) > 0, "Model ML.BROKER_RISK_NET does not exist"

    def test_stream_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW STREAMS LIKE 'INVOICE_JSON_STREAM' IN SCHEMA APEX_CAPITAL_DEMO.RAW"
        ).collect()
        assert len(result) > 0, "Stream RAW.INVOICE_JSON_STREAM does not exist"

    def test_task_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW TASKS LIKE 'SIMULATE_STREAMING_INGESTION' IN SCHEMA APEX_CAPITAL_DEMO.RAW"
        ).collect()
        assert len(result) > 0, "Task RAW.SIMULATE_STREAMING_INGESTION does not exist"

    def test_masking_policies_exist(self, sf_session):
        result = sf_session.sql(
            "SHOW MASKING POLICIES IN SCHEMA APEX_CAPITAL_DEMO.RAW"
        ).collect()
        policy_names = [row["name"] for row in result]
        assert "SSN_MASK" in policy_names, "Masking policy RAW.SSN_MASK does not exist"
        assert "BANK_ACCOUNT_MASK" in policy_names, "Masking policy RAW.BANK_ACCOUNT_MASK does not exist"

    def test_schemas_exist(self, sf_session):
        result = sf_session.sql(
            "SHOW SCHEMAS IN DATABASE APEX_CAPITAL_DEMO"
        ).collect()
        schema_names = [row["name"] for row in result]
        for expected in ["RAW", "STAGING", "ANALYTICS", "ML", "DS_SANDBOX"]:
            assert expected in schema_names, f"Schema {expected} does not exist"

    def test_recommendations_table_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW TABLES LIKE 'NEXTLOAD_RECOMMENDATIONS' IN SCHEMA APEX_CAPITAL_DEMO.ML"
        ).collect()
        assert len(result) > 0, "Table ML.NEXTLOAD_RECOMMENDATIONS does not exist"


@pytest.mark.sql
@pytest.mark.live
class TestDataIntegrity:
    """Verify data is present and consistent."""

    def test_broker_360_has_rows(self, sf_session):
        result = sf_session.sql(
            "SELECT COUNT(*) AS cnt FROM APEX_CAPITAL_DEMO.ANALYTICS.BROKER_360"
        ).collect()
        assert result[0]["CNT"] > 0, "BROKER_360 is empty"

    def test_recommendations_row_count(self, sf_session):
        result = sf_session.sql(
            "SELECT COUNT(*) AS cnt FROM APEX_CAPITAL_DEMO.ML.NEXTLOAD_RECOMMENDATIONS"
        ).collect()
        assert result[0]["CNT"] > 0, "NEXTLOAD_RECOMMENDATIONS is empty"

    def test_json_table_growing(self, sf_session):
        result = sf_session.sql(
            "SELECT COUNT(*) AS cnt FROM APEX_CAPITAL_DEMO.RAW.INVOICE_TRANSACTIONS_JSON"
        ).collect()
        assert result[0]["CNT"] > 0, "INVOICE_TRANSACTIONS_JSON is empty (task may not be running)"
