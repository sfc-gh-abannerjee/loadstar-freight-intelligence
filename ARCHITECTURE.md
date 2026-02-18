# Architecture Reference

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     LoadStar Freight Intelligence                       │
│                                                                         │
│  SOURCE LAYER              TRANSFORM LAYER          CONSUMPTION LAYER   │
│  ─────────────            ───────────────          ─────────────────    │
│                                                                         │
│  ┌──────────┐             ┌─────────────┐          ┌──────────────┐    │
│  │ broker_  │────────────▶│             │          │ Semantic View│    │
│  │ profiles │             │  BROKER_360 │─────────▶│ (NL queries) │    │
│  └──────────┘             │             │          └──────┬───────┘    │
│  ┌──────────┐             │  Dynamic    │                 │            │
│  │ invoice_ │────────────▶│  Table      │          ┌──────▼───────┐    │
│  │ txns     │             │             │          │ Cortex Agent │    │
│  └──────────┘             │  200 rows   │          │ "Ask in      │    │
│  ┌──────────┐             │  30 columns │          │  English"    │    │
│  │ load_    │────────────▶│  5-min lag  │          └──────────────┘    │
│  │ postings │             │             │                              │
│  └──────────┘             └──────┬──────┘          ┌──────────────┐    │
│  ┌──────────┐                    │                 │ Scoring UDF  │    │
│  │ carrier_ │                    │                 │ 0.0 - 1.0    │    │
│  │ profiles │                    └────────────────▶│ per driver-  │    │
│  └──────────┘                                      │ load pair    │    │
│  ┌──────────┐    ┌──────────┐                      └──────────────┘    │
│  │ weather  │───▶│ H3 Geo   │                                          │
│  │ (Mktplc) │    │ Functions │                      ┌──────────────┐    │
│  └──────────┘    └──────────┘                      │ Notebook     │    │
│                                                     │ (GPU Runtime)│    │
│  STREAMING                 GOVERNANCE               │ PyTorch      │    │
│  ─────────                 ──────────               └──────────────┘    │
│  ┌──────────┐             ┌─────────────┐                              │
│  │ JSON     │             │ SSN_MASK    │           ┌──────────────┐    │
│  │ Staging  │             │ BANK_MASK   │           │ DS Sandbox   │    │
│  │ (VARIANT)│             │ PII_TYPE tag│           │ (Zero-Copy   │    │
│  └────┬─────┘             │ 3 RBAC roles│           │  Clone)      │    │
│       │                   └─────────────┘           └──────────────┘    │
│  ┌────▼─────┐                                                          │
│  │ Stream + │                                                          │
│  │ Task     │                                                          │
│  │ 5 rows/m │                                                          │
│  └──────────┘                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## The BROKER_360 Dynamic Table

The centerpiece of the architecture. A single auto-refreshing table that combines:

| Source | Columns Added | Technique |
|--------|-------------|-----------|
| `broker_profiles` | ID, name, MC#, credit score, factoring type, status | Direct join |
| `invoice_transactions` | Payment metrics (avg days, late count, disputed, outstanding) | CTE aggregation |
| `invoice_transactions` | Lane analysis (unique lanes, primary origin/dest, avg miles) | CTE with MODE() |
| `load_postings` | Geospatial lane density (H3 cells, route diversity) | H3_LATLNG_TO_CELL() |
| `texas_weather` | Current weather risk at primary origin | QUALIFY ROW_NUMBER() |
| Computed | Fraud risk level, composite risk score (0-100) | CASE logic |

**Total: 30 columns, 200 rows, 5-minute auto-refresh.**

## Composite Risk Score Formula

```
composite_risk_score (0-100) =
    credit_component (0-40):
        credit < 400 → 40
        credit < 550 → 25
        credit < 700 → 10
        else → 0
    + payment_component (0-25):
        avg_days > 60 → 25
        avg_days > 45 → 15
        else → 0
    + fraud_component (0-30):
        double_broker_flag → 30
        else → 0
    + weather_component (0-10):
        HIGH risk → 10
        MEDIUM risk → 5
        else → 0
```

## Recommendation Scoring UDF

`GET_RECOMMENDATION_SCORE(driver_id, load_id)` returns a FLOAT 0.0-1.0:

```
score = MIN(
    (credit_score / 850) × 0.30 +
    (1.0 - risk_score / 100) × 0.30 +
    (rate_per_mile / 4.0) × 0.20 +
    (1.0 - avg_days / 90) × 0.20
, 1.0)

If fraud_risk_level IN ('HIGH', 'CRITICAL') → 0.0
```

## RBAC Model

```
ACCOUNTADMIN
├── FREIGHT_ANALYST      → ANALYTICS schema (read-only) + ANALYTICS_WH
├── FREIGHT_DATA_SCIENTIST → ML + DS_SANDBOX schemas (full) + DS_SANDBOX_WH
└── FREIGHT_OPS          → RAW schema (read-only) + ANALYTICS_WH
```

## Streaming Pipeline

```
External Source → INVOICE_TRANSACTIONS_JSON (VARIANT)
                        │
                  INVOICE_JSON_STREAM (CDC)
                        │
                  INVOICE_TRANSACTIONS_FLATTENED (typed view)

SIMULATE_STREAMING_INGESTION task: 5 rows/minute
```
