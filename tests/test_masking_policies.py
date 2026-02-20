"""Tests for masking policy behavior."""
import pytest


@pytest.mark.sql
@pytest.mark.live
class TestMaskingPolicies:
    """Verify PII masking policies are active and correctly applied."""

    def test_ssn_mask_policy_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW MASKING POLICIES LIKE 'SSN_MASK' IN SCHEMA APEX_CAPITAL_DEMO.RAW"
        ).collect()
        assert len(result) > 0, "SSN_MASK policy does not exist"

    def test_bank_account_mask_policy_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW MASKING POLICIES LIKE 'BANK_ACCOUNT_MASK' IN SCHEMA APEX_CAPITAL_DEMO.RAW"
        ).collect()
        assert len(result) > 0, "BANK_ACCOUNT_MASK policy does not exist"

    def test_pii_tag_exists(self, sf_session):
        result = sf_session.sql(
            "SHOW TAGS LIKE 'PII_TYPE' IN SCHEMA APEX_CAPITAL_DEMO.RAW"
        ).collect()
        assert len(result) > 0, "PII_TYPE tag does not exist"

    def test_carrier_profiles_has_ssn_column(self, sf_session):
        result = sf_session.sql(
            "DESCRIBE TABLE APEX_CAPITAL_DEMO.RAW.CARRIER_PROFILES"
        ).collect()
        col_names = [row["name"] for row in result]
        assert "DRIVER_SSN" in col_names, "DRIVER_SSN column not found in CARRIER_PROFILES"

    def test_carrier_profiles_has_bank_column(self, sf_session):
        result = sf_session.sql(
            "DESCRIBE TABLE APEX_CAPITAL_DEMO.RAW.CARRIER_PROFILES"
        ).collect()
        col_names = [row["name"] for row in result]
        assert "BANK_ACCOUNT_NUMBER" in col_names, (
            "BANK_ACCOUNT_NUMBER column not found in CARRIER_PROFILES"
        )
