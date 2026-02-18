-- =============================================================================
-- LoadStar Freight Intelligence
-- 00: Infrastructure Setup
-- Creates database, schemas, warehouses, compute pool, and RBAC roles
-- =============================================================================

-- Database
CREATE OR REPLACE DATABASE FREIGHT_DEMO
    COMMENT = 'LoadStar Freight Intelligence - Unified broker analytics platform';

-- Schemas
CREATE SCHEMA IF NOT EXISTS FREIGHT_DEMO.RAW
    COMMENT = 'Raw ingestion layer - source tables and streaming pipeline';
CREATE SCHEMA IF NOT EXISTS FREIGHT_DEMO.STAGING
    COMMENT = 'Staging layer - transformations and data quality';
CREATE SCHEMA IF NOT EXISTS FREIGHT_DEMO.ANALYTICS
    COMMENT = 'Analytics layer - golden records, semantic views, agents';
CREATE SCHEMA IF NOT EXISTS FREIGHT_DEMO.ML
    COMMENT = 'Machine learning layer - models, UDFs, recommendations';

-- Warehouses (workload isolation)
CREATE WAREHOUSE IF NOT EXISTS ANALYTICS_WH
    WAREHOUSE_SIZE = 'MEDIUM'
    AUTO_SUSPEND = 120
    AUTO_RESUME = TRUE
    COMMENT = 'Analytics workloads - Dynamic Tables, queries, agent execution';

CREATE WAREHOUSE IF NOT EXISTS DS_SANDBOX_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    COMMENT = 'Data science sandbox - exploratory queries on cloned data';

-- Compute pool for GPU (Notebook + ML training)
-- Use GPU_NV_M for production demos; GPU_NV_S for cost-conscious dev
CREATE COMPUTE POOL IF NOT EXISTS GPU_POOL
    MIN_NODES = 1
    MAX_NODES = 1
    INSTANCE_FAMILY = GPU_NV_S
    AUTO_SUSPEND_SECS = 300
    COMMENT = 'GPU compute for PyTorch training and Container Runtime notebooks';

-- RBAC Roles
CREATE ROLE IF NOT EXISTS FREIGHT_ANALYST
    COMMENT = 'Analyst role - read-only access to analytics layer';
CREATE ROLE IF NOT EXISTS FREIGHT_DATA_SCIENTIST
    COMMENT = 'Data scientist role - full access to ML schema + DS sandbox';
CREATE ROLE IF NOT EXISTS FREIGHT_OPS
    COMMENT = 'IT Ops role - read-only access to RAW layer for monitoring';

-- Role hierarchy
GRANT ROLE FREIGHT_ANALYST TO ROLE SYSADMIN;
GRANT ROLE FREIGHT_DATA_SCIENTIST TO ROLE SYSADMIN;
GRANT ROLE FREIGHT_OPS TO ROLE SYSADMIN;

-- Database grants
GRANT USAGE ON DATABASE FREIGHT_DEMO TO ROLE FREIGHT_ANALYST;
GRANT USAGE ON DATABASE FREIGHT_DEMO TO ROLE FREIGHT_DATA_SCIENTIST;
GRANT USAGE ON DATABASE FREIGHT_DEMO TO ROLE FREIGHT_OPS;

-- Schema grants: Analyst -> ANALYTICS
GRANT USAGE ON SCHEMA FREIGHT_DEMO.ANALYTICS TO ROLE FREIGHT_ANALYST;
GRANT USAGE ON WAREHOUSE ANALYTICS_WH TO ROLE FREIGHT_ANALYST;

-- Schema grants: Data Scientist -> ML + DS_SANDBOX + ANALYTICS
GRANT USAGE ON SCHEMA FREIGHT_DEMO.ML TO ROLE FREIGHT_DATA_SCIENTIST;
GRANT USAGE ON SCHEMA FREIGHT_DEMO.DS_SANDBOX TO ROLE FREIGHT_DATA_SCIENTIST;
GRANT USAGE ON SCHEMA FREIGHT_DEMO.ANALYTICS TO ROLE FREIGHT_DATA_SCIENTIST;
GRANT ALL ON SCHEMA FREIGHT_DEMO.ML TO ROLE FREIGHT_DATA_SCIENTIST;
GRANT USAGE ON WAREHOUSE DS_SANDBOX_WH TO ROLE FREIGHT_DATA_SCIENTIST;

-- Schema grants: Ops -> RAW (read-only)
GRANT USAGE ON SCHEMA FREIGHT_DEMO.RAW TO ROLE FREIGHT_OPS;
GRANT USAGE ON WAREHOUSE ANALYTICS_WH TO ROLE FREIGHT_OPS;
