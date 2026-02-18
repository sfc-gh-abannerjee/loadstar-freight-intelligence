-- =============================================================================
-- LoadStar Freight Intelligence
-- 05: Governance - Tags, Masking Policies, and RBAC Grants
-- Proves: Snowflake Horizon for PII protection and role-based access control
-- =============================================================================

USE DATABASE FREIGHT_DEMO;
USE SCHEMA RAW;

-- ============================================================
-- PII Tag
-- ============================================================
CREATE OR REPLACE TAG PII_TYPE
    ALLOWED_VALUES 'SSN', 'BANK_ACCOUNT', 'DRIVER_NAME'
    COMMENT = 'Classifies PII columns for governance tracking';

-- ============================================================
-- Masking Policies
-- ============================================================

-- SSN masking: shows full SSN only to ACCOUNTADMIN
CREATE OR REPLACE MASKING POLICY SSN_MASK AS (val STRING) RETURNS STRING ->
    CASE
        WHEN CURRENT_ROLE() IN ('ACCOUNTADMIN') THEN val
        ELSE '***-**-' || RIGHT(val, 4)
    END;

-- Bank account masking: shows full number only to ACCOUNTADMIN
CREATE OR REPLACE MASKING POLICY BANK_ACCOUNT_MASK AS (val STRING) RETURNS STRING ->
    CASE
        WHEN CURRENT_ROLE() IN ('ACCOUNTADMIN') THEN val
        ELSE '******' || RIGHT(val, 4)
    END;

-- ============================================================
-- Apply policies and tags to CARRIER_PROFILES
-- ============================================================

-- Apply masking policies
ALTER TABLE FREIGHT_DEMO.RAW.CARRIER_PROFILES
    MODIFY COLUMN DRIVER_SSN
    SET MASKING POLICY SSN_MASK;

ALTER TABLE FREIGHT_DEMO.RAW.CARRIER_PROFILES
    MODIFY COLUMN BANK_ACCOUNT_NUMBER
    SET MASKING POLICY BANK_ACCOUNT_MASK;

-- Apply PII tags
ALTER TABLE FREIGHT_DEMO.RAW.CARRIER_PROFILES
    MODIFY COLUMN DRIVER_SSN
    SET TAG PII_TYPE = 'SSN';

ALTER TABLE FREIGHT_DEMO.RAW.CARRIER_PROFILES
    MODIFY COLUMN BANK_ACCOUNT_NUMBER
    SET TAG PII_TYPE = 'BANK_ACCOUNT';

-- ============================================================
-- RBAC Grants (complement to 00_setup_infrastructure.sql)
-- ============================================================

-- Ops: read-only on all RAW tables
GRANT SELECT ON ALL TABLES IN SCHEMA FREIGHT_DEMO.RAW TO ROLE FREIGHT_OPS;

-- Analyst: read access to analytics objects
GRANT SELECT ON ALL TABLES IN SCHEMA FREIGHT_DEMO.ANALYTICS TO ROLE FREIGHT_ANALYST;
GRANT SELECT ON ALL DYNAMIC TABLES IN SCHEMA FREIGHT_DEMO.ANALYTICS TO ROLE FREIGHT_ANALYST;
GRANT SELECT ON ALL VIEWS IN SCHEMA FREIGHT_DEMO.ANALYTICS TO ROLE FREIGHT_ANALYST;

-- Data Scientist: full ML schema + sandbox read
GRANT SELECT ON ALL TABLES IN SCHEMA FREIGHT_DEMO.DS_SANDBOX TO ROLE FREIGHT_DATA_SCIENTIST;
GRANT SELECT ON ALL TABLES IN SCHEMA FREIGHT_DEMO.ML TO ROLE FREIGHT_DATA_SCIENTIST;
