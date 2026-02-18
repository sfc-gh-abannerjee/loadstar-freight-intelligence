-- =============================================================================
-- LoadStar Freight Intelligence
-- 10: Git Repository Integration
-- Connects this repo to Snowflake for notebook sourcing and version control
-- =============================================================================

USE DATABASE FREIGHT_DEMO;
USE SCHEMA ANALYTICS;

-- API Integration for GitHub access
CREATE OR REPLACE API INTEGRATION GIT_API_INTEGRATION
    API_PROVIDER = git_https_api
    API_ALLOWED_PREFIXES = ('https://github.com/sfc-gh-abannerjee/')
    ENABLED = TRUE
    COMMENT = 'GitHub API integration for LoadStar Freight Intelligence repo';

-- Git Repository object pointing to the public repo
CREATE OR REPLACE GIT REPOSITORY LOADSTAR_REPO
    API_INTEGRATION = GIT_API_INTEGRATION
    ORIGIN = 'https://github.com/sfc-gh-abannerjee/loadstar-freight-intelligence.git'
    COMMENT = 'LoadStar Freight Intelligence - source-controlled demo artifacts';

-- Fetch latest
ALTER GIT REPOSITORY LOADSTAR_REPO FETCH;

-- Verify
SHOW GIT REPOSITORIES IN SCHEMA FREIGHT_DEMO.ANALYTICS;
