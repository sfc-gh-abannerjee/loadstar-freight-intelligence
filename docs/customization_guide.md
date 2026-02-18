# Customization Guide

LoadStar's architecture pattern generalizes to any entity-centric analytics use case. This guide explains how to adapt it for other industries.

## Core Pattern

```
Fragmented Sources → Streaming Ingest → Dynamic Table (Golden Record) → ML Scoring → NL Agent
```

This pattern applies whenever you have:
- Multiple source tables describing an entity
- Risk or scoring requirements
- A need for natural language access to data
- Regulatory or governance requirements (PII, RBAC)

## Industry Mapping

| Component | Freight Factoring | Insurance | Lending | Supply Chain |
|-----------|-------------------|-----------|---------|-------------|
| **Entity** | Broker | Policy / Policyholder | Borrower | Vendor |
| **Transaction** | Invoice | Claim | Loan payment | Purchase order |
| **Risk signal** | Double brokering | Fraud ring | Default probability | Counterfeit |
| **Rate metric** | Rate per mile | Premium | APR | Unit cost |
| **Golden record** | BROKER_360 | POLICY_360 | BORROWER_360 | VENDOR_360 |
| **External data** | Weather (Marketplace) | Catastrophe data | Economic indicators | Supply chain disruption |

## Step-by-Step Adaptation

### 1. Replace Entity Tables

Edit `sql/01_create_raw_tables.sql`:
- Rename `BROKER_PROFILES` to your entity table (e.g., `POLICY_HOLDERS`)
- Adjust columns to match your domain
- Keep the same 5-table structure: entity, counterparty, transactions, postings/events, external data

### 2. Modify Synthetic Data

Edit `sql/02_generate_synthetic_data.sql`:
- Adjust `GENERATOR(ROWCOUNT => ...)` for your scale
- Replace city/state values with your domain geography
- Update status values, equipment types, etc.

### 3. Rebuild the Dynamic Table

Edit `sql/03_create_dynamic_table.sql`:
- Keep the 4-CTE structure (payment metrics, dimension analysis, geospatial, external data)
- Rename output columns to match your domain
- Adjust the composite risk formula weights

### 4. Update the Scoring UDF

Edit `sql/06_create_udf_and_sproc.sql`:
- Replace the scoring formula with your domain-specific logic
- Adjust the weights (credit × 0.30, risk × 0.30, rate × 0.20, velocity × 0.20)
- Update the fraud-level filter (which levels return 0.0)

### 5. Rebuild the Semantic View

Edit `sql/07_create_semantic_view.sql`:
- Update facts, dimensions, and metrics to match your golden record columns
- Rewrite the `AI_SQL_GENERATION` domain context string
- Update synonyms for domain terminology

### 6. Update the Agent

Edit `sql/08_create_agent.sql`:
- Rewrite the orchestration instructions with your domain vocabulary
- Update the response instructions for your audience
- Point `semantic_view` to your new Semantic View name

### 7. Governance

Edit `sql/05_create_governance.sql`:
- Update PII tag values for your domain (e.g., `POLICY_NUMBER`, `SSN`, `DOB`)
- Create masking policies appropriate to your data
- Adjust RBAC roles to match your organization

### 8. Notebook

Copy and modify `notebooks/freight_360_demo.ipynb`:
- Update markdown cells with your domain narrative
- Adjust PyTorch model architecture for your prediction target
- Update visualization cells for your metrics

## Configuration

All hardcoded values are parameterized in `config/demo_config.env`. For a new industry vertical, create a new config file:

```bash
# config/insurance_config.env
export DATABASE="INSURANCE_DEMO"
export ANALYTICS_WH="CLAIMS_WH"
export NOTEBOOK_NAME="POLICY_360_DEMO"
export AGENT_NAME="CLAIMS_AGENT"
export SEMANTIC_VIEW_NAME="POLICY_360_SV"
```

## Naming Convention

When creating a new vertical:
1. Pick a memorable brand name (like "LoadStar" for freight)
2. Use `<ENTITY>_360` for the Dynamic Table
3. Use `<ENTITY>_360_SV` for the Semantic View
4. Keep the `sql/` file numbering convention (00-99)
