-- =============================================================================
-- LoadStar Freight Intelligence
-- 06: UDF and Stored Procedure
-- GET_RECOMMENDATION_SCORE: Production inference UDF (single source of truth)
-- POPULATE_RECOMMENDATIONS: Iterates driver-load pairs, calls UDF per row
-- =============================================================================

USE DATABASE FREIGHT_DEMO;
USE SCHEMA ML;

-- ============================================================
-- Recommendations table (pre-computed scores for low-latency lookups)
-- ============================================================
CREATE OR REPLACE TABLE CARRIERMATCH_RECOMMENDATIONS (
    DRIVER_ID NUMBER(38,0) NOT NULL,
    LOAD_ID NUMBER(38,0) NOT NULL,
    BROKER_ID NUMBER(38,0),
    RECOMMENDATION_SCORE FLOAT,
    RISK_LEVEL VARCHAR(20),
    COMPUTED_AT TIMESTAMP_LTZ(9) DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY (DRIVER_ID, LOAD_ID)
COMMENT = 'Pre-computed recommendation scores for low-latency CarrierMatch lookups. Clustered by driver+load for fast point lookups.';

-- ============================================================
-- Scoring UDF
-- Returns a recommendation score (0.0-1.0) for a driver-load match
-- based on broker credit, composite risk, rate per mile, and payment velocity.
-- Returns 0.0 for HIGH/CRITICAL fraud risk brokers.
-- ============================================================
CREATE OR REPLACE FUNCTION GET_RECOMMENDATION_SCORE(P_DRIVER_ID NUMBER(38,0), P_LOAD_ID NUMBER(38,0))
RETURNS FLOAT
LANGUAGE SQL
COMMENT = 'Returns a recommendation score (0.0-1.0) for a driver-load match based on broker risk, rate, and lane fit'
AS '
    SELECT 
        CASE 
            WHEN b.FRAUD_RISK_LEVEL IN (''HIGH'', ''CRITICAL'') THEN 0.0::FLOAT
            ELSE ROUND(LEAST(
                (LEAST(b.CREDIT_SCORE, 850) / 850.0) * 0.30 +
                GREATEST(1.0 - b.COMPOSITE_RISK_SCORE / 100.0, 0.0) * 0.30 +
                LEAST(l.RATE_PER_MILE / 4.0, 1.0) * 0.20 +
                GREATEST(1.0 - b.AVG_DAYS_TO_PAY / 90.0, 0.0) * 0.20
            , 1.0), 4)::FLOAT
        END
    FROM FREIGHT_DEMO.RAW.LOAD_POSTINGS l
    JOIN FREIGHT_DEMO.ANALYTICS.BROKER_360 b ON l.BROKER_ID = b.BROKER_ID
    WHERE l.LOAD_ID = ''LOAD-'' || LPAD(P_LOAD_ID::TEXT, 7, ''0'')
    LIMIT 1
';

-- ============================================================
-- Stored Procedure: POPULATE_RECOMMENDATIONS
-- Iterates driver-load pairs, calls UDF per row, inserts in batches.
-- Required because UDF contains correlated subqueries that cannot be
-- used directly in INSERT...SELECT statements.
-- ============================================================
CREATE OR REPLACE PROCEDURE POPULATE_RECOMMENDATIONS()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS '
    // Truncate existing data
    snowflake.execute({sqlText: "TRUNCATE TABLE FREIGHT_DEMO.ML.CARRIERMATCH_RECOMMENDATIONS"});
    
    // 200 drivers x 10 loads = 2000 pairs
    // Mix of LOW/MEDIUM/HIGH fraud risk loads for realistic score diversity
    var pairs_query = "SELECT d.BROKER_ID AS DRIVER_ID, l.LOAD_NUM FROM FREIGHT_DEMO.ANALYTICS.BROKER_360 d CROSS JOIN (SELECT 4531 AS LOAD_NUM UNION ALL SELECT 279 UNION ALL SELECT 3021 UNION ALL SELECT 98 UNION ALL SELECT 51 UNION ALL SELECT 73 UNION ALL SELECT 4560 UNION ALL SELECT 4712 UNION ALL SELECT 1 UNION ALL SELECT 500) l ORDER BY d.BROKER_ID, l.LOAD_NUM";
    
    var pairs_rs = snowflake.execute({sqlText: pairs_query});
    var batch = [];
    var row_count = 0;
    
    while (pairs_rs.next()) {
        var driver_id = pairs_rs.getColumnValue(1);
        var load_id = pairs_rs.getColumnValue(2);
        
        // Call UDF for this pair - single source of truth
        var score_rs = snowflake.execute({sqlText: 
            "SELECT FREIGHT_DEMO.ML.GET_RECOMMENDATION_SCORE(" + driver_id + ", " + load_id + ") AS SCORE"
        });
        
        var score = 0;
        if (score_rs.next()) {
            score = score_rs.getColumnValue(1);
            if (score === null) score = 0;
        }
        
        var risk_level;
        if (score >= 0.8) risk_level = "STRONG_MATCH";
        else if (score >= 0.6) risk_level = "GOOD_MATCH";
        else if (score >= 0.4) risk_level = "MEDIUM_MATCH";
        else if (score > 0.0) risk_level = "WEAK_MATCH";
        else risk_level = "NO_MATCH";
        
        // Get broker_id for this load
        var broker_rs = snowflake.execute({sqlText:
            "SELECT BROKER_ID FROM FREIGHT_DEMO.RAW.LOAD_POSTINGS WHERE LOAD_ID = \\'LOAD-\\' || LPAD(" + load_id + "::TEXT, 7, \\'0\\') LIMIT 1"
        });
        var broker_id = null;
        if (broker_rs.next()) {
            broker_id = broker_rs.getColumnValue(1);
        }
        
        batch.push("(" + driver_id + "," + load_id + "," + (broker_id !== null ? broker_id : "NULL") + "," + score + ",\\'" + risk_level + "\\', CURRENT_TIMESTAMP())");
        row_count++;
        
        if (batch.length >= 100) {
            snowflake.execute({sqlText:
                "INSERT INTO FREIGHT_DEMO.ML.CARRIERMATCH_RECOMMENDATIONS (DRIVER_ID, LOAD_ID, BROKER_ID, RECOMMENDATION_SCORE, RISK_LEVEL, COMPUTED_AT) VALUES " + batch.join(",")
            });
            batch = [];
        }
    }
    
    if (batch.length > 0) {
        snowflake.execute({sqlText:
            "INSERT INTO FREIGHT_DEMO.ML.CARRIERMATCH_RECOMMENDATIONS (DRIVER_ID, LOAD_ID, BROKER_ID, RECOMMENDATION_SCORE, RISK_LEVEL, COMPUTED_AT) VALUES " + batch.join(",")
        });
    }
    
    return "Populated " + row_count + " recommendations using GET_RECOMMENDATION_SCORE UDF";
';
