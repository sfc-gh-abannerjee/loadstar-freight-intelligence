"""
LoadStar Commander — Freight intelligence dashboard.
Runs on Snowflake Container Runtime (SPCS).
"""

import os

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import requests

import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="LoadStar Commander",
    page_icon=":material/local_shipping:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Neumorphism CSS on Stellar dark-mode palette
# ---------------------------------------------------------------------------
NEUMORPH_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --canvas: #191e24;
    --surface: #1e252f;
    --border: #293246;
    --text-primary: #bdc4d5;
    --text-secondary: #9fabc1;
    --text-header: #bdc4d5;
    --accent: #1a6ce7;
    --accent-light: #5999f8;
    --success: #1db588;
    --warning: #e8a317;
    --danger: #d3132f;
    --danger-light: #ef405e;
    --shadow-dark: #12161c;
    --shadow-light: #242d38;
}

html, body, [class*="st-"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Neumorphic card */
.neu-card {
    background: var(--surface);
    border-radius: 16px;
    padding: 24px;
    box-shadow: 8px 8px 16px var(--shadow-dark),
                -8px -8px 16px var(--shadow-light);
    margin-bottom: 16px;
}

.neu-card-inset {
    background: var(--surface);
    border-radius: 12px;
    padding: 20px;
    box-shadow: inset 4px 4px 8px var(--shadow-dark),
                inset -4px -4px 8px var(--shadow-light);
    margin-bottom: 12px;
}

/* Stat card */
.stat-card {
    background: var(--surface);
    border-radius: 16px;
    padding: 20px 24px;
    box-shadow: 6px 6px 12px var(--shadow-dark),
                -6px -6px 12px var(--shadow-light);
    text-align: center;
    min-height: 100px;
}
.stat-card .stat-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--text-header);
    margin: 4px 0;
}
.stat-card .stat-label {
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Risk badge */
.risk-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.risk-low { background: rgba(29,181,136,0.15); color: #1db588; }
.risk-medium { background: rgba(232,163,23,0.15); color: #e8a317; }
.risk-high { background: rgba(211,19,47,0.15); color: #ef405e; }
.risk-critical { background: rgba(211,19,47,0.25); color: #ef405e; font-weight: 700; }

/* Match score gauge */
.match-gauge {
    width: 64px; height: 64px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.9rem; font-weight: 700;
    box-shadow: inset 3px 3px 6px var(--shadow-dark),
                inset -3px -3px 6px var(--shadow-light);
}

/* Section header */
.section-header {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-header);
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--accent);
    display: inline-block;
}

/* App title */
.app-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text-header);
    margin: 0;
}
.app-subtitle {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-top: 2px;
}
</style>
"""
st.html(NEUMORPH_CSS)


# ---------------------------------------------------------------------------
# Snowflake connection (thread-safe for container runtime)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_session():
    return st.connection("snowflake").session()


@st.cache_data(ttl=300)
def run_query(sql: str) -> pd.DataFrame:
    session = get_session()
    return session.sql(sql).to_pandas()


# ---------------------------------------------------------------------------
# Cortex Agent helper (container runtime auth)
# ---------------------------------------------------------------------------
def call_cortex_agent(question: str) -> str:
    """Call the Broker Intelligence Agent via REST API."""
    host = os.getenv("SNOWFLAKE_HOST")
    if not host:
        return "Agent unavailable — SNOWFLAKE_HOST not set."
    try:
        token = open("/snowflake/session/token", "r").read()
    except FileNotFoundError:
        return "Agent unavailable — session token not found."

    url = (
        f"https://{host}/api/v2/databases/APEX_CAPITAL_DEMO"
        f"/schemas/ANALYTICS/agents/APEX_BROKER_AGENT:run"
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Snowflake-Authorization-Token-Type": "OAUTH",
        "Accept": "application/json",
    }
    payload = {
        "stream": False,
        "messages": [{"role": "user", "content": question}],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        return f"Agent returned HTTP {resp.status_code}."
    data = resp.json()
    # Extract text from agent response
    if "messages" in data:
        for msg in data["messages"]:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    parts = [
                        p.get("text", "") for p in content if p.get("type") == "text"
                    ]
                    return "\n".join(parts) if parts else str(content)
                return str(content)
    return str(data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def risk_badge(level: str) -> str:
    css_class = {
        "LOW": "risk-low",
        "MEDIUM": "risk-medium",
        "HIGH": "risk-high",
        "CRITICAL": "risk-critical",
    }.get(str(level).upper(), "risk-medium")
    return f'<span class="risk-badge {css_class}">{level}</span>'


def stat_card(label: str, value: str, color: str = "var(--text-header)") -> str:
    return f"""
    <div class="stat-card">
        <div class="stat-label">{label}</div>
        <div class="stat-value" style="color:{color}">{value}</div>
    </div>
    """


def match_color(score: float) -> str:
    if score >= 0.8:
        return "#1db588"
    if score >= 0.6:
        return "#5999f8"
    if score >= 0.4:
        return "#e8a317"
    return "#ef405e"


# ---------------------------------------------------------------------------
# Title bar
# ---------------------------------------------------------------------------
st.html(
    '<div style="padding:8px 0 16px 0;">'
    '<p class="app-title">LoadStar Commander</p>'
    '<p class="app-subtitle">Freight intelligence platform</p>'
    "</div>"
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_map, tab_match, tab_broker = st.tabs(
    [
        ":material/map: Command map",
        ":material/match_case: Match engine",
        ":material/person_search: Broker 360",
    ]
)

# ===== TAB 1: Command Map ===================================================
with tab_map:

    @st.cache_data(ttl=300)
    def load_map_data():
        carriers = run_query("""
            SELECT CARRIER_NAME, HOME_LATITUDE AS LAT, HOME_LONGITUDE AS LON,
                   EQUIPMENT_TYPE::STRING AS EQUIPMENT, STATUS, FLEET_SIZE
            FROM APEX_CAPITAL_DEMO.RAW.CARRIER_PROFILES
            WHERE HOME_LATITUDE IS NOT NULL
        """)
        loads = run_query("""
            SELECT LOAD_ID, ORIGIN_CITY::STRING AS ORIGIN_CITY,
                   ORIGIN_STATE::STRING AS ORIGIN_STATE,
                   ORIGIN_LATITUDE AS O_LAT, ORIGIN_LONGITUDE AS O_LON,
                   DESTINATION_CITY::STRING AS DEST_CITY,
                   DESTINATION_STATE::STRING AS DEST_STATE,
                   TOTAL_RATE, STATUS,
                   EQUIPMENT_REQUIRED::STRING AS EQUIPMENT
            FROM APEX_CAPITAL_DEMO.RAW.LOAD_POSTINGS
            WHERE ORIGIN_LATITUDE IS NOT NULL AND STATUS = 'AVAILABLE'
        """)
        weather = run_query("""
            SELECT CITY_NAME, AVG_TEMP_F, MAX_WIND_MPH,
                   PRECIPITATION_IN, WEATHER_RISK_LEVEL
            FROM APEX_CAPITAL_DEMO.RAW.TEXAS_WEATHER
        """)
        return carriers, loads, weather

    carriers_df, loads_df, weather_df = load_map_data()

    # Sidebar filters
    with st.sidebar:
        st.html('<div class="section-header">Map filters</div>')
        equip_options = sorted(carriers_df["EQUIPMENT"].dropna().unique())
        sel_equip = st.multiselect("Equipment type", equip_options, default=equip_options)
        risk_options = sorted(weather_df["WEATHER_RISK_LEVEL"].dropna().unique())
        sel_risk = st.multiselect("Weather risk", risk_options, default=risk_options)

    # Filter
    filt_carriers = carriers_df[carriers_df["EQUIPMENT"].isin(sel_equip)]
    filt_weather = weather_df[weather_df["WEATHER_RISK_LEVEL"].isin(sel_risk)]

    # KPI row
    cols = st.columns(4)
    with cols[0]:
        st.html(stat_card("Active carriers", str(len(filt_carriers))))
    with cols[1]:
        st.html(stat_card("Available loads", str(len(loads_df))))
    with cols[2]:
        high_risk_ct = len(weather_df[weather_df["WEATHER_RISK_LEVEL"].isin(["HIGH", "SEVERE"])])
        st.html(stat_card("High-risk cities", str(high_risk_ct), "var(--danger-light)"))
    with cols[3]:
        avg_rate = f"${loads_df['TOTAL_RATE'].mean():,.0f}" if len(loads_df) else "$0"
        st.html(stat_card("Avg load rate", avg_rate, "var(--success)"))

    # Map
    def carrier_color(row):
        if row["STATUS"] == "ACTIVE":
            return [26, 108, 231, 180]
        return [112, 129, 154, 120]

    filt_carriers = filt_carriers.copy()
    filt_carriers["COLOR"] = filt_carriers.apply(carrier_color, axis=1)

    carrier_layer = pdk.Layer(
        "ScatterplotLayer",
        data=filt_carriers,
        get_position=["LON", "LAT"],
        get_fill_color="COLOR",
        get_radius=25000,
        pickable=True,
        auto_highlight=True,
    )

    load_layer = pdk.Layer(
        "ScatterplotLayer",
        data=loads_df,
        get_position=["O_LON", "O_LAT"],
        get_fill_color=[29, 181, 136, 140],
        get_radius=15000,
        pickable=True,
    )

    view = pdk.ViewState(latitude=32.5, longitude=-99.5, zoom=5.2, pitch=0)

    deck = pdk.Deck(
        layers=[carrier_layer, load_layer],
        initial_view_state=view,
        map_style="mapbox://styles/mapbox/dark-v11",
        tooltip={
            "html": "<b>{CARRIER_NAME}</b><br/>Equipment: {EQUIPMENT}<br/>Fleet: {FLEET_SIZE}",
            "style": {
                "backgroundColor": "#1e252f",
                "color": "#bdc4d5",
                "border": "1px solid #293246",
                "border-radius": "8px",
                "padding": "8px",
            },
        },
    )
    st.pydeck_chart(deck, use_container_width=True, height=520)

    # Weather table
    st.html('<div class="section-header">Weather conditions</div>')
    st.dataframe(
        filt_weather.sort_values("WEATHER_RISK_LEVEL", ascending=False),
        use_container_width=True,
        hide_index=True,
        height=240,
    )


# ===== TAB 2: Match Engine ===================================================
with tab_match:

    @st.cache_data(ttl=300)
    def load_recommendations():
        return run_query("""
            SELECT DRIVER_ID, LOAD_ID, RECOMMENDATION_SCORE, RISK_LEVEL,
                   ORIGIN_CITY, ORIGIN_STATE, DESTINATION_CITY, DESTINATION_STATE,
                   TOTAL_RATE, EQUIPMENT_REQUIRED, MILES,
                   BROKER_NAME, CREDIT_SCORE, FRAUD_RISK_LEVEL, COMPOSITE_RISK_SCORE
            FROM APEX_CAPITAL_DEMO.ANALYTICS.LOADSTAR_RECOMMENDATIONS_V
            ORDER BY RECOMMENDATION_SCORE DESC
        """)

    recs_df = load_recommendations()
    driver_ids = sorted(recs_df["DRIVER_ID"].unique())

    col_left, col_right = st.columns([1, 3])
    with col_left:
        st.html('<div class="section-header">Select driver</div>')
        sel_driver = st.selectbox(
            "Driver ID",
            driver_ids,
            label_visibility="collapsed",
        )

    driver_recs = (
        recs_df[recs_df["DRIVER_ID"] == sel_driver]
        .sort_values("RECOMMENDATION_SCORE", ascending=False)
        .head(6)
    )

    with col_right:
        st.html('<div class="section-header">Top load recommendations</div>')

    if driver_recs.empty:
        st.info("No recommendations available for this driver.")
    else:
        rec_cols = st.columns(min(3, len(driver_recs)))
        for idx, (_, rec) in enumerate(driver_recs.iterrows()):
            col = rec_cols[idx % 3]
            score = rec["RECOMMENDATION_SCORE"]
            sc = match_color(score)
            fraud = rec.get("FRAUD_RISK_LEVEL", "LOW")
            badge = risk_badge(fraud)

            card_html = f"""
            <div class="neu-card">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                    <div class="match-gauge" style="border:3px solid {sc};color:{sc};">
                        {score*100:.0f}%
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:0.75rem;color:var(--text-secondary);">LOAD</div>
                        <div style="font-weight:600;color:var(--text-header);font-size:0.95rem;">{rec['LOAD_ID']}</div>
                    </div>
                </div>
                <div style="font-size:0.85rem;color:var(--text-primary);margin-bottom:8px;">
                    {rec['ORIGIN_CITY']}, {rec['ORIGIN_STATE']}
                    &rarr; {rec['DESTINATION_CITY']}, {rec['DESTINATION_STATE']}
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-weight:600;color:var(--success);font-size:1.1rem;">${rec['TOTAL_RATE']:,.0f}</span>
                    <span style="font-size:0.8rem;color:var(--text-secondary);">{rec.get('MILES', 'N/A')} mi</span>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:0.8rem;color:var(--text-secondary);">{rec['BROKER_NAME']}</span>
                    {badge}
                </div>
            </div>
            """
            with col:
                st.html(card_html)

            # Show second row if more than 3
            if idx == 2 and len(driver_recs) > 3:
                rec_cols = st.columns(min(3, len(driver_recs) - 3))

    # Recommendation distribution
    st.html('<div class="section-header">Score distribution</div>')
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=recs_df["RECOMMENDATION_SCORE"],
            nbinsx=20,
            marker_color="#1a6ce7",
            marker_line_color="#5999f8",
            marker_line_width=1,
        )
    )
    fig.update_layout(
        plot_bgcolor="#1e252f",
        paper_bgcolor="#191e24",
        font=dict(color="#9fabc1", family="Inter"),
        xaxis=dict(title="Match score", gridcolor="#293246", zerolinecolor="#293246"),
        yaxis=dict(title="Count", gridcolor="#293246", zerolinecolor="#293246"),
        margin=dict(l=40, r=20, t=20, b=40),
        height=280,
    )
    st.plotly_chart(fig, use_container_width=True)


# ===== TAB 3: Broker 360 Inspector ==========================================
with tab_broker:

    @st.cache_data(ttl=300)
    def load_brokers():
        return run_query("""
            SELECT BROKER_ID, BROKER_NAME, MC_NUMBER, HQ_STATE,
                   CREDIT_SCORE, FACTORING_TYPE, TOTAL_INVOICES,
                   TOTAL_FACTORED_AMOUNT, AVG_DAYS_TO_PAY,
                   DISPUTED_INVOICES, FRAUD_RISK_LEVEL,
                   COMPOSITE_RISK_SCORE, DOUBLE_BROKER_FLAG,
                   CURRENT_WEATHER_RISK, UNIQUE_LANES,
                   PRIMARY_ORIGIN, PRIMARY_DESTINATION,
                   LANE_DENSITY, LAST_REFRESHED
            FROM APEX_CAPITAL_DEMO.ANALYTICS.BROKER_360
            ORDER BY BROKER_NAME
        """)

    brokers_df = load_brokers()

    # Broker selector
    col_sel, col_spacer = st.columns([2, 3])
    with col_sel:
        st.html('<div class="section-header">Broker lookup</div>')
        broker_names = brokers_df["BROKER_NAME"].tolist()
        sel_broker = st.selectbox("Search broker", broker_names, label_visibility="collapsed")

    broker = brokers_df[brokers_df["BROKER_NAME"] == sel_broker].iloc[0]

    # Header row — risk gauge + identity
    h_left, h_right = st.columns([1, 3])
    with h_left:
        risk_val = broker["COMPOSITE_RISK_SCORE"]
        risk_color = (
            "#1db588" if risk_val < 30
            else "#e8a317" if risk_val < 60
            else "#ef405e"
        )
        gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=float(risk_val),
                gauge=dict(
                    axis=dict(range=[0, 100], tickcolor="#70819a"),
                    bar=dict(color=risk_color),
                    bgcolor="#293246",
                    borderwidth=0,
                    steps=[
                        dict(range=[0, 30], color="rgba(29,181,136,0.1)"),
                        dict(range=[30, 60], color="rgba(232,163,23,0.1)"),
                        dict(range=[60, 100], color="rgba(211,19,47,0.1)"),
                    ],
                ),
                title=dict(text="Composite risk", font=dict(size=13, color="#9fabc1")),
                number=dict(font=dict(size=36, color=risk_color)),
            )
        )
        gauge.update_layout(
            paper_bgcolor="#191e24",
            plot_bgcolor="#1e252f",
            height=200,
            margin=dict(l=20, r=20, t=40, b=10),
            font=dict(family="Inter"),
        )
        st.plotly_chart(gauge, use_container_width=True)

    with h_right:
        fraud_badge = risk_badge(broker["FRAUD_RISK_LEVEL"])
        double_flag = (
            '<span class="risk-badge risk-critical">DOUBLE BROKER FLAG</span>'
            if broker["DOUBLE_BROKER_FLAG"]
            else ""
        )
        header_html = f"""
        <div class="neu-card">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <div style="font-size:1.3rem;font-weight:700;color:var(--text-header);">{broker['BROKER_NAME']}</div>
                    <div style="font-size:0.85rem;color:var(--text-secondary);margin-top:4px;">
                        MC #{broker['MC_NUMBER']} &middot; {broker['HQ_STATE']} &middot; {broker['FACTORING_TYPE']}
                    </div>
                </div>
                <div style="text-align:right;">{fraud_badge} {double_flag}</div>
            </div>
            <div style="margin-top:12px;font-size:0.8rem;color:var(--text-secondary);">
                Primary lane: {broker.get('PRIMARY_ORIGIN', 'N/A')} &rarr; {broker.get('PRIMARY_DESTINATION', 'N/A')}
                &middot; {broker.get('UNIQUE_LANES', 0)} unique lanes
                &middot; Last refreshed: {str(broker.get('LAST_REFRESHED', 'N/A'))[:19]}
            </div>
        </div>
        """
        st.html(header_html)

    # Stat cards
    stat_cols = st.columns(5)
    stats = [
        ("Credit score", f"{broker['CREDIT_SCORE']:.0f}", "#5999f8"),
        ("Avg days to pay", f"{broker['AVG_DAYS_TO_PAY']:.1f}", "var(--text-header)"),
        ("Total invoices", f"{broker['TOTAL_INVOICES']:,}", "var(--text-header)"),
        ("Disputed", f"{broker['DISPUTED_INVOICES']}", "var(--danger-light)" if broker["DISPUTED_INVOICES"] > 5 else "var(--text-header)"),
        ("Total factored", f"${broker['TOTAL_FACTORED_AMOUNT']:,.0f}", "var(--success)"),
    ]
    for i, (label, val, color) in enumerate(stats):
        with stat_cols[i]:
            st.html(stat_card(label, val, color))

    # Weather + additional context
    wx_col, agent_col = st.columns([1, 2])

    with wx_col:
        st.html('<div class="section-header">Current conditions</div>')
        wx_risk = broker.get("CURRENT_WEATHER_RISK", "N/A")
        wx_badge = risk_badge(wx_risk)
        st.html(
            f'<div class="neu-card-inset">'
            f'<div style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:8px;">Weather risk</div>'
            f'<div>{wx_badge}</div>'
            f'<div style="margin-top:12px;font-size:0.85rem;color:var(--text-secondary);">'
            f'Lane density: {broker.get("LANE_DENSITY", "N/A")}</div>'
            f"</div>"
        )

    with agent_col:
        st.html('<div class="section-header">Ask the broker agent</div>')

        if "agent_messages" not in st.session_state:
            st.session_state.agent_messages = []

        for msg in st.session_state.agent_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        if prompt := st.chat_input(
            f"Ask about {sel_broker}...", key="broker_chat"
        ):
            st.session_state.agent_messages.append(
                {"role": "user", "content": prompt}
            )
            with st.chat_message("user"):
                st.write(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Querying agent..."):
                    answer = call_cortex_agent(prompt)
                st.write(answer)

            st.session_state.agent_messages.append(
                {"role": "assistant", "content": answer}
            )
