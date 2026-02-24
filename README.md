# LoadStar Freight Intelligence

**A Snowflake reference architecture for unified broker analytics, ML risk scoring, and natural language queries in freight factoring.**

LoadStar demonstrates how Snowflake replaces fragmented legacy stacks (Oracle + Domo + FTP files) with a single platform covering ingestion, golden record creation, ML training, production inference, and conversational AI — all without external infrastructure.

## What This Proves

| Persona | Pain Point | Snowflake Solution |
|---------|-----------|-------------------|
| **IT Ops** | "Analytics queries crash our Oracle DB" | Workload isolation with dedicated warehouses. Zero impact on source systems. |
| **Data Science** | "We manage ECS containers for GPU training" | Native GPU compute via Container Runtime. PyTorch training without Docker. |
| **Product** | "42 versions of truth across Domo dashboards" | Single Dynamic Table ("Broker Object") with natural language queries. |

## Architecture

```
                    LoadStar Freight Intelligence
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐ │
│  │  RAW Layer   │───▶│ Dynamic Table│───▶│   Semantic View     │ │
│  │  5 tables    │    │  BROKER_360  │    │   + Cortex Agent    │ │
│  │  + Streaming │    │  30 columns  │    │   "Ask in English"  │ │
│  └─────────────┘    │  5-min refresh│    └─────────────────────┘ │
│        │            └──────────────┘              │              │
│        │                   │                      │              │
│  ┌─────▼─────┐    ┌───────▼──────┐    ┌──────────▼──────────┐  │
│  │ Streaming  │    │   ML Layer   │    │   Governance        │  │
│  │ JSON+Task  │    │ PyTorch Model│    │   PII Masking       │  │
│  │ 5 rows/min │    │ Scoring UDF  │    │   RBAC (3 roles)    │  │
│  └────────────┘    │ Recommendations│   │   Tags              │  │
│                    └──────────────┘    └─────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Snowflake Products Used

| # | Product | Usage |
|---|---------|-------|
| 1 | **Dynamic Tables** | Auto-refreshing "Broker Object" golden record |
| 2 | **Notebooks + GPU Runtime** | PyTorch model training on Container Runtime |
| 3 | **Model Registry** | Versioned PyTorch model management |
| 4 | **SQL UDFs** | Production inference scoring function |
| 5 | **Semantic Views** | Business-friendly query model |
| 6 | **Cortex Agents** | Natural language broker intelligence |
| 7 | **Horizon (Governance)** | PII masking policies, RBAC, tags |
| 8 | **Streams + Tasks** | Real-time ingestion simulation |
| 9 | **Zero-Copy Cloning** | DS sandbox at zero storage cost |
| 10 | **H3 Geospatial** | Lane density via H3 cell indexing |
| 11 | **Git Integration** | Source-controlled demo artifacts |
| 12 | **OpenRouteService Native App** | Truck routing via SPCS (driving-hgv profile) |

## Quick Start

```bash
# 1. Configure
cp config/demo_config.env config/my_config.env
# Edit my_config.env with your Snowflake connection details

# 2. Deploy (runs all SQL in order, ~5 minutes)
source config/demo_config.env
./scripts/deploy.sh

# 3. Validate
./scripts/validate_deployment.sh
```

## Repository Structure

```
loadstar-freight-intelligence/
├── README.md                          # This file
├── DEPLOYMENT_GUIDE.md                # Detailed setup instructions
├── ARCHITECTURE.md                    # Technical architecture reference
├── register_model.py                  # Train BrokerRiskNet + register in Model Registry
├── snowpark_session.py                # Snowpark session factory (multi-auth)
├── requirements.txt                   # Python dependencies
├── config/
│   └── demo_config.env                # Parameterized configuration
├── sql/
│   ├── 00_setup_infrastructure.sql    # Database, schemas, warehouses, roles
│   ├── 01_create_raw_tables.sql       # Source table DDL
│   ├── 02_generate_synthetic_data.sql # Synthetic freight data generation
│   ├── 03_create_dynamic_table.sql    # BROKER_360 Dynamic Table
│   ├── 04_create_streaming_pipeline.sql # JSON staging, stream, task
│   ├── 05_create_governance.sql       # Tags, masking policies, RBAC
│   ├── 06_create_udf_and_sproc.sql    # Scoring UDF + stored procedure
│   ├── 07_create_semantic_view.sql    # Semantic View for Cortex Analyst
│   ├── 08_create_agent.sql            # Cortex Agent specification
│   ├── 09_populate_recommendations.sql # Seed recommendation scores
│   ├── 10_create_git_integration.sql  # Snowflake Git Repository
│   └── 99_teardown.sql               # Clean removal of all objects
├── scripts/
│   ├── deploy.sh                      # One-command deployment
│   ├── upload_notebook.sh             # Notebook upload to Snowflake
│   └── validate_deployment.sh         # Deployment verification
├── notebooks/
│   └── freight_360_demo.ipynb         # Demo notebook (GPU runtime)
└── docs/
    ├── demo_talk_track.md             # Phase-by-phase presentation guide
    ├── troubleshooting.md             # Known issues and fixes
    └── customization_guide.md         # Adapting for other industries
```

## Teardown

```bash
snow sql -c $SNOW_CONNECTION -f sql/99_teardown.sql
```

## Adapting for Other Industries

LoadStar's architecture pattern generalizes to any entity-centric analytics use case:

| Freight Factoring | Insurance | Lending | Supply Chain |
|-------------------|-----------|---------|-------------|
| Broker | Policy | Borrower | Vendor |
| Invoice | Claim | Loan | Purchase Order |
| Double brokering | Fraud ring | Default risk | Counterfeit |
| Rate per mile | Premium | APR | Unit cost |

See `docs/customization_guide.md` for detailed adaptation instructions.

## License

Apache 2.0
