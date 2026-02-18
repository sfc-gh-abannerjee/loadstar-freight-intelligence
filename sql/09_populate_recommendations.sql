-- =============================================================================
-- LoadStar Freight Intelligence
-- 09: Populate Recommendations
-- Calls the stored procedure to seed recommendation scores using the UDF
-- =============================================================================

USE DATABASE FREIGHT_DEMO;
USE WAREHOUSE ANALYTICS_WH;

-- This calls GET_RECOMMENDATION_SCORE() for each driver-load pair
-- and inserts results into CARRIERMATCH_RECOMMENDATIONS.
-- Expect ~2000 rows (200 drivers x 10 loads), takes ~2-3 minutes.
CALL FREIGHT_DEMO.ML.POPULATE_RECOMMENDATIONS();

-- Verify
SELECT 
    RISK_LEVEL,
    COUNT(*) AS CNT,
    ROUND(AVG(RECOMMENDATION_SCORE), 4) AS AVG_SCORE,
    MIN(RECOMMENDATION_SCORE) AS MIN_SCORE,
    MAX(RECOMMENDATION_SCORE) AS MAX_SCORE
FROM FREIGHT_DEMO.ML.CARRIERMATCH_RECOMMENDATIONS
GROUP BY RISK_LEVEL
ORDER BY AVG_SCORE DESC;
