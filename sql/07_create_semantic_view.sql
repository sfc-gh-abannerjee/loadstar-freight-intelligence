-- =============================================================================
-- LoadStar Freight Intelligence
-- 07: Semantic View
-- Business-friendly model for Cortex Analyst / natural language queries
-- =============================================================================

USE DATABASE FREIGHT_DEMO;
USE SCHEMA ANALYTICS;

CREATE OR REPLACE SEMANTIC VIEW BROKER_360_SV
    TABLES (
        BROKER AS FREIGHT_DEMO.ANALYTICS.BROKER_360
            PRIMARY KEY (BROKER_ID)
            WITH SYNONYMS = ('broker profile', 'broker 360', 'golden record')
            COMMENT = 'Unified broker profile - single source of truth'
    )
    FACTS (
        BROKER.CREDIT_SCORE AS CREDIT_SCORE COMMENT = 'Credit score 350-850',
        BROKER.TOTAL_FACTORED_AMOUNT AS TOTAL_FACTORED_AMOUNT COMMENT = 'Total dollar amount factored',
        BROKER.AVG_DAYS_TO_PAY AS AVG_DAYS_TO_PAY COMMENT = 'Avg days to payment',
        BROKER.TOTAL_INVOICES AS TOTAL_INVOICES COMMENT = 'Total invoices factored',
        BROKER.OUTSTANDING_AMOUNT AS OUTSTANDING_AMOUNT COMMENT = 'Unpaid invoice amount',
        BROKER.COMPOSITE_RISK_SCORE AS COMPOSITE_RISK_SCORE COMMENT = 'Combined risk score 0-100',
        BROKER.LATE_PAYMENT_COUNT AS LATE_PAYMENT_COUNT COMMENT = 'Late payments after 45 days',
        BROKER.DISPUTED_INVOICES AS DISPUTED_INVOICES COMMENT = 'Disputed invoices',
        BROKER.DISPUTE_COUNT AS DISPUTE_COUNT COMMENT = 'Total disputes',
        BROKER.UNIQUE_LANES AS UNIQUE_LANES COMMENT = 'Unique lane combinations',
        BROKER.LANE_DENSITY AS LANE_DENSITY COMMENT = 'Geospatial lane density - distinct H3 cell-to-state route combinations',
        BROKER.ORIGIN_H3_CELLS AS ORIGIN_H3_CELLS COMMENT = 'Distinct H3 origin cells at resolution 4',
        BROKER.AVG_HAUL_MILES AS AVG_HAUL_MILES COMMENT = 'Avg miles per load',
        BROKER.AVG_INVOICE_AMOUNT AS AVG_INVOICE_AMOUNT COMMENT = 'Average invoice amount',
        BROKER.FACTORING_RATE_PCT AS FACTORING_RATE_PCT COMMENT = 'Factoring fee percentage'
    )
    DIMENSIONS (
        BROKER.BROKER_NAME AS BROKER_NAME
            WITH SYNONYMS = ('broker', 'company')
            COMMENT = 'Broker name',
        BROKER.MC_NUMBER AS MC_NUMBER
            WITH SYNONYMS = ('MC', 'motor carrier')
            COMMENT = 'Motor Carrier number',
        BROKER.HQ_STATE AS HQ_STATE
            WITH SYNONYMS = ('state', 'location')
            COMMENT = 'HQ state',
        BROKER.FACTORING_TYPE AS FACTORING_TYPE
            COMMENT = 'RECOURSE or NON_RECOURSE',
        BROKER.BROKER_STATUS AS BROKER_STATUS
            COMMENT = 'Broker status',
        BROKER.FRAUD_RISK_LEVEL AS FRAUD_RISK_LEVEL
            WITH SYNONYMS = ('risk level', 'fraud risk')
            COMMENT = 'Fraud risk level',
        BROKER.CURRENT_WEATHER_RISK AS CURRENT_WEATHER_RISK
            COMMENT = 'Weather risk at origin',
        BROKER.PRIMARY_ORIGIN AS PRIMARY_ORIGIN
            COMMENT = 'Primary origin city',
        BROKER.PRIMARY_DESTINATION AS PRIMARY_DESTINATION
            COMMENT = 'Primary destination',
        BROKER.DOUBLE_BROKER_FLAG AS DOUBLE_BROKER_FLAG
            WITH SYNONYMS = ('fraud flag', 'double brokering')
            COMMENT = 'Fraud flag',
        BROKER.RELATIONSHIP_START AS RELATIONSHIP_START
            COMMENT = 'Relationship start date'
    )
    METRICS (
        BROKER.TOTAL_EXPOSURE AS SUM(BROKER.TOTAL_FACTORED_AMOUNT) COMMENT = 'Total factored amount',
        BROKER.AVG_CREDIT AS AVG(BROKER.CREDIT_SCORE) COMMENT = 'Avg credit score',
        BROKER.OUTSTANDING_TOTAL AS SUM(BROKER.OUTSTANDING_AMOUNT) COMMENT = 'Total outstanding',
        BROKER.AVG_DAYS AS AVG(BROKER.AVG_DAYS_TO_PAY) COMMENT = 'Avg payment days',
        BROKER.BROKER_COUNT AS COUNT(BROKER.CREDIT_SCORE) COMMENT = 'Broker count',
        BROKER.AVG_LANE_DENSITY AS AVG(BROKER.LANE_DENSITY) COMMENT = 'Avg geospatial lane density'
    )
    COMMENT = 'Broker 360 - Single Source of Truth for freight broker intelligence'
    AI_SQL_GENERATION 'Broker 360 for freight broker analysis. FACTORING: Company buys invoices for liquidity. RISK: composite_risk_score (0-100) combines credit, payment, fraud, weather. DOUBLE BROKERING: Fraud where carrier re-brokers load - double_broker_flag indicates suspects. RECOURSE: Company bears risk. HIGH RISK TX: HQ_STATE=TX AND fraud_risk_level IN (HIGH,CRITICAL). SLOW PAYERS: avg_days_to_pay > 45. LANE_DENSITY: Geospatial spread of broker operations using H3 cells. Higher = more geographically diverse.';
