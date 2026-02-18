# Troubleshooting

## UDF in INSERT...SELECT: "Unsupported subquery type"

**Symptom:** `SQL compilation error: Unsupported subquery type cannot be evaluated`

**Cause:** `GET_RECOMMENDATION_SCORE()` internally joins `LOAD_POSTINGS` and `BROKER_360`. Snowflake cannot nest correlated subqueries inside `INSERT...SELECT`.

**Fix:** Use the `POPULATE_RECOMMENDATIONS()` stored procedure, which iterates row-by-row and calls the UDF per pair.

```sql
CALL FREIGHT_DEMO.ML.POPULATE_RECOMMENDATIONS();
```

---

## GPU Cold Start

**Symptom:** First notebook cell execution or UDF call takes 30-60 seconds.

**Cause:** GPU compute pool nodes are provisioned on-demand. The first execution triggers node startup.

**Fix:** This is expected behavior. Subsequent calls will be fast. To pre-warm, run a trivial query on the compute pool before the demo.

---

## Notebook Upload Fails

**Symptom:** `CREATE NOTEBOOK` fails or notebook appears empty.

**Cause:** Notebook must be staged before creation. The `.ipynb` file must exist on an internal stage.

**Fix:**
```sql
-- Create stage
CREATE STAGE IF NOT EXISTS FREIGHT_DEMO.ANALYTICS.NOTEBOOK_STAGE;

-- Upload
PUT 'file:///path/to/freight_360_demo.ipynb' @FREIGHT_DEMO.ANALYTICS.NOTEBOOK_STAGE/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE;

-- Create notebook
CREATE OR REPLACE NOTEBOOK FREIGHT_DEMO.ANALYTICS.FREIGHT_360_DEMO
    FROM '@FREIGHT_DEMO.ANALYTICS.NOTEBOOK_STAGE'
    MAIN_FILE = 'freight_360_demo.ipynb'
    COMPUTE_POOL = 'GPU_POOL'
    RUNTIME_NAME = 'SYSTEM$GPU_RUNTIME';

-- Add live version
ALTER NOTEBOOK FREIGHT_DEMO.ANALYTICS.FREIGHT_360_DEMO ADD LIVE VERSION FROM LAST;
```

---

## Model Registry: "snowflake-ml-python not found"

**Symptom:** `ModuleNotFoundError: No module named 'snowflake.ml'`

**Fix:**
```bash
pip install snowflake-ml-python torch
```

The model registration script requires `snowflake-ml-python` for `Registry.log_model()` and `torch` for the PyTorch model definition.

---

## Hybrid Table "Reader Account" Error

**Symptom:** `SQL compilation error: Operation is not supported in reader account.`

**Cause:** The internal parameter `ENABLE_KEY_VALUE_TABLE` is not set on the account. This requires SnowCommand enablement by Snowflake Support.

**Note:** LoadStar uses clustered regular tables instead of hybrid tables. The demo point (sub-500ms UDF scoring) works without hybrid tables.

---

## Streaming Task Not Running

**Symptom:** JSON table row count not growing.

**Fix:**
```sql
-- Check task status
SHOW TASKS IN SCHEMA FREIGHT_DEMO.RAW;

-- Resume if suspended
ALTER TASK FREIGHT_DEMO.RAW.SIMULATE_STREAMING_INGESTION RESUME;
```

---

## Dynamic Table Not Refreshing

**Symptom:** `LAST_REFRESHED` timestamp is stale.

**Fix:**
```sql
-- Check DT status
SELECT * FROM TABLE(INFORMATION_SCHEMA.DYNAMIC_TABLE_REFRESH_HISTORY(
    NAME => 'FREIGHT_DEMO.ANALYTICS.BROKER_360'
)) ORDER BY REFRESH_START_TIME DESC LIMIT 5;

-- Force refresh
ALTER DYNAMIC TABLE FREIGHT_DEMO.ANALYTICS.BROKER_360 REFRESH;
```

---

## Agent Not Responding

**Symptom:** Agent returns empty or error responses.

**Check:**
1. Semantic View exists: `SHOW SEMANTIC VIEWS IN SCHEMA FREIGHT_DEMO.ANALYTICS;`
2. BROKER_360 has data: `SELECT COUNT(*) FROM FREIGHT_DEMO.ANALYTICS.BROKER_360;`
3. Warehouse is running: `SELECT CURRENT_WAREHOUSE();`

The agent requires the semantic view to be backed by a populated Dynamic Table.
