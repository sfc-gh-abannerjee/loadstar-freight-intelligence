### LoadStar Commander — Streamlit app

**Deployed as:** `APEX_CAPITAL_DEMO.ANALYTICS.LOADSTAR_COMMANDER`

**Runtime:** Snowflake Container Runtime (`SYSTEM$ST_CONTAINER_RUNTIME_PY3_11`)

**Compute pool:** `LOADSTAR_COMPUTE_POOL` (CPU_X64_XS, dedicated)

**Dependencies:** `streamlit[snowflake]>=1.52.0`, `pydeck>=0.9.0`, `plotly>=5.0.0`, `requests>=2.28.0`

**Data sources:**
- `ANALYTICS.BROKER_360` — Dynamic Table (unified broker record)
- `ANALYTICS.LOADSTAR_RECOMMENDATIONS_V` — View joining recommendations + loads + brokers
- `RAW.CARRIER_PROFILES` — Carrier positions and equipment
- `RAW.LOAD_POSTINGS` — Available freight loads with lat/lon
- `RAW.TEXAS_WEATHER` — City-level weather risk
- `ANALYTICS.APEX_BROKER_AGENT` — Cortex Agent for natural language queries

---

#### Tab 1: Command map (geospatial awareness)

Geospatial map (`pydeck`) displaying active carriers and available loads. Weather risk data highlights cities affected by severe conditions. Sidebar filters for equipment type and weather risk level.

#### Tab 2: Match engine (AI recommendations)

Select a driver ID to view top load recommendations ranked by match score. Each recommendation card shows origin/destination, rate, mileage, broker name, and fraud risk level. Scores are powered by the `NEXTLOAD_RECOMMENDATIONS` table (backed by `GET_RECOMMENDATION_SCORE()` UDF). Includes a score distribution histogram.

#### Tab 3: Broker 360 inspector (golden record)

Credit-report style interface for any broker in the `BROKER_360` Dynamic Table. Displays composite risk gauge, credit score, payment metrics, disputed invoices, weather risk, and lane information. Includes a Cortex Agent chat panel for natural language queries against the broker data.

---

#### Design system

- **Aesthetic:** Neumorphism (soft shadow outset/inset effects)
- **Palette:** Snowflake Stellar dark mode tokens
- **Typography:** Inter font family
- **Spacing:** 8px base scale
- **Accessibility:** 4.5:1 minimum text contrast

#### Deployment

```bash
cd streamlit/
snow streamlit deploy --replace --connection se_demo
```

Files: `streamlit_app.py`, `pyproject.toml`, `snowflake.yml`, `.streamlit/config.toml`
