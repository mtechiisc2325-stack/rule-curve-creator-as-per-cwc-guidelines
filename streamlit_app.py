"""
streamlit_app.py
Rule Curve Optimizer v2.0 – Main entry point
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from io import BytesIO

from src.constants import (
    WATER_YEAR_PERIODS,
    SAMPLE_ES_CURVE, SAMPLE_INFLOWS_P50, SAMPLE_INFLOWS_P10, SAMPLE_DEMAND,
    CUSHION_CASES_FT, UPPER_ANCHOR_PID, LOWER_ANCHOR_PID,
    CUSHION_START_PID, CUSHION_END_PID,
)
from src.es_curve import ElevationStorageCurve
from src.rule_curve_calc import RuleCurveCalculator
from src.simulation import ForwardSimulator
from src.report_generator import generate_pdf_report
from src.excel_exporter import build_excel_workbook

# ═══════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Rule Curve Optimizer",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .block-container { padding-top: 1.5rem; }
  h1 { color: #0055A5; }
  h2 { color: #0055A5; border-bottom: 2px solid #0055A5; padding-bottom: 4px; }
  h3 { color: #FF6600; }
  .stMetric label { font-size: 0.85rem; }
  .stAlert { border-radius: 6px; }
  /* Sidebar */
  [data-testid="stSidebar"] { background-color: #EEF4FB; }
  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3 { color: #0055A5; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════
CUSHION_COLORS = [
    '#003f5c','#2f4b7c','#665191','#a05195',
    '#d45087','#f95d6a','#ff7c43','#ffa600',
    '#7cb342','#1e88e5',
]

def make_period_df(q50, q10, demand):
    return pd.DataFrame({
        'PID':       range(36),
        'Period':    WATER_YEAR_PERIODS,
        'P50 Inflow (MCM)': q50,
        'P10 Inflow (MCM)': q10,
        'Demand (MCM)':     demand,
    })

def _parse_inflow_csv(text: str):
    """Parse pasted 36-row × 3-col CSV into three arrays."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    data = []
    for line in lines:
        parts = [p.strip() for p in line.replace('\t', ',').split(',')]
        data.append([float(p) for p in parts[:3]])
    arr = np.array(data)
    if arr.shape[0] != 36 or arr.shape[1] < 3:
        raise ValueError(f"Expected 36 rows × 3 columns, got {arr.shape}")
    return arr[:, 0], arr[:, 1], arr[:, 2]

def _parse_es_csv(text: str):
    """Parse pasted ES curve CSV (elevation_m, storage_mcm)."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    data = []
    for line in lines:
        parts = [p.strip() for p in line.replace('\t', ',').split(',')]
        if len(parts) >= 2:
            data.append([float(parts[0]), float(parts[1])])
    arr = np.array(data)
    if len(arr) < 3:
        raise ValueError("Need at least 3 elevation-storage pairs")
    return arr[:, 0], arr[:, 1]


# ═══════════════════════════════════════════════════════════════════════
#  SIDEBAR – INPUT SECTION
# ═══════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("# 💧 Rule Curve Optimizer")
    st.caption("v2.0 — Backward calculation method (CWC)")
    st.markdown("---")

    # ── Reservoir identity ────────────────────────────────────────────
    st.markdown("### 🏗️ Reservoir Details")
    reservoir_name = st.text_input("Reservoir Name", "Bhavanisagar Reservoir")
    river_name     = st.text_input("River",          "Bhavani River")
    col1, col2 = st.columns(2)
    with col1:
        frl_m  = st.number_input("FRL (m)",  value=107.59, step=0.01, format="%.2f")
    with col2:
        mddl_m = st.number_input("MDDL (m)", value= 95.33, step=0.01, format="%.2f")

    st.markdown("---")

    # ── ES Curve ──────────────────────────────────────────────────────
    st.markdown("### 📐 Elevation-Storage Curve")
    es_method = st.radio("Input method", ["Use sample data", "Paste CSV", "Upload CSV"],
                         horizontal=True, key="es_method")

    es_elev, es_stor = None, None

    if es_method == "Use sample data":
        es_elev = np.array(SAMPLE_ES_CURVE['elevation_m'])
        es_stor = np.array(SAMPLE_ES_CURVE['storage_mcm'])
        st.success("✓ Bhavanisagar sample ES curve loaded")

    elif es_method == "Paste CSV":
        es_text = st.text_area(
            "elevation_m, storage_mcm (one pair per line)",
            value="\n".join(
                f"{e},{s}"
                for e, s in zip(SAMPLE_ES_CURVE['elevation_m'], SAMPLE_ES_CURVE['storage_mcm'])
            ),
            height=180,
        )
        try:
            es_elev, es_stor = _parse_es_csv(es_text)
            st.success(f"✓ {len(es_elev)} elevation-storage pairs parsed")
        except Exception as ex:
            st.error(f"❌ {ex}")

    else:  # Upload CSV
        es_file = st.file_uploader("Upload ES curve CSV (2 columns, no header required)",
                                   type=["csv", "txt"])
        if es_file:
            try:
                df_es = pd.read_csv(es_file, header=None)
                es_elev = df_es.iloc[:, 0].values.astype(float)
                es_stor = df_es.iloc[:, 1].values.astype(float)
                st.success(f"✓ {len(es_elev)} pairs loaded")
            except Exception as ex:
                st.error(f"❌ {ex}")

    st.markdown("---")

    # ── Inflows & Demand ──────────────────────────────────────────────
    st.markdown("### 💧 Inflows & Demand (36 periods)")
    flow_method = st.radio("Input method",
                           ["Use sample data", "Paste CSV", "Upload CSV"],
                           horizontal=True, key="flow_method")

    q50, q10, demand = None, None, None

    if flow_method == "Use sample data":
        q50    = np.array(SAMPLE_INFLOWS_P50)
        q10    = np.array(SAMPLE_INFLOWS_P10)
        demand = np.array(SAMPLE_DEMAND)
        st.success("✓ Sample inflows & demand loaded")

    elif flow_method == "Paste CSV":
        default_flow = "\n".join(
            f"{p50},{p10},{d}"
            for p50, p10, d in zip(SAMPLE_INFLOWS_P50, SAMPLE_INFLOWS_P10, SAMPLE_DEMAND)
        )
        flow_text = st.text_area(
            "p50_inflow, p10_inflow, demand  (36 rows)",
            value=default_flow, height=200,
        )
        try:
            q50, q10, demand = _parse_inflow_csv(flow_text)
            st.success("✓ 36 periods parsed")
        except Exception as ex:
            st.error(f"❌ {ex}")

    else:  # Upload CSV
        flow_file = st.file_uploader(
            "Upload CSV: 36 rows × 3 cols (p50, p10, demand) – no header",
            type=["csv", "txt"])
        if flow_file:
            try:
                df_flow = pd.read_csv(flow_file, header=None)
                q50    = df_flow.iloc[:, 0].values.astype(float)
                q10    = df_flow.iloc[:, 1].values.astype(float)
                demand = df_flow.iloc[:, 2].values.astype(float)
                st.success("✓ Inflows loaded")
            except Exception as ex:
                st.error(f"❌ {ex}")

    st.markdown("---")

    # ── Initial storage for simulation ───────────────────────────────
    st.markdown("### ⚙️ Simulation Settings")
    init_storage_option = st.radio(
        "Initial storage (Jul-I)",
        ["FRL (full reservoir)", "MDDL (worst-case dry start)", "Custom"],
        horizontal=False,
    )

    # ── Run button ────────────────────────────────────────────────────
    st.markdown("---")
    run_btn = st.button("🚀  RUN OPTIMIZATION", use_container_width=True, type="primary")


# ═══════════════════════════════════════════════════════════════════════
#  MAIN AREA – HEADER (always visible)
# ═══════════════════════════════════════════════════════════════════════
st.title("💧 Reservoir Rule Curve Optimizer")
st.markdown(
    "**Backward calculation method (CWC) · 10 flood-cushion cases · "
    "Forward simulation · PDF export**  "
    "_Enter data in the sidebar, then click **RUN OPTIMIZATION**._"
)
st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════
#  PRE-RUN: show input preview
# ═══════════════════════════════════════════════════════════════════════
if not run_btn and 'results' not in st.session_state:
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### ES Curve Preview")
        if es_elev is not None:
            df_prev = pd.DataFrame({'Elevation (m)': es_elev, 'Storage (MCM)': es_stor})
            st.dataframe(df_prev, height=280, use_container_width=True)
            fig_es = go.Figure()
            fig_es.add_trace(go.Scatter(x=es_stor, y=es_elev, mode='lines+markers',
                                        line=dict(color='steelblue', width=2)))
            fig_es.update_layout(title="ES Curve", xaxis_title="Storage (MCM)",
                                 yaxis_title="Elevation (m)", height=280, margin=dict(t=40))
            st.plotly_chart(fig_es, use_container_width=True)
        else:
            st.info("No ES curve loaded yet.")

    with col_r:
        st.markdown("#### Inflow & Demand Preview")
        if q50 is not None:
            df_flow_prev = make_period_df(q50, q10, demand)
            st.dataframe(df_flow_prev, height=280, use_container_width=True)
            fig_flow = go.Figure()
            fig_flow.add_trace(go.Bar(x=WATER_YEAR_PERIODS, y=q50,
                                      name="P50 Inflow", marker_color='steelblue'))
            fig_flow.add_trace(go.Bar(x=WATER_YEAR_PERIODS, y=q10,
                                      name="P10 Inflow", marker_color='orange'))
            fig_flow.add_trace(go.Scatter(x=WATER_YEAR_PERIODS, y=demand,
                                          name="Demand", mode='lines+markers',
                                          line=dict(color='red', width=2)))
            fig_flow.update_layout(title="Inflows & Demand",
                                   yaxis_title="MCM/decade", height=280,
                                   barmode='group', margin=dict(t=40))
            st.plotly_chart(fig_flow, use_container_width=True)
        else:
            st.info("No inflow data loaded yet.")

    st.stop()


# ═══════════════════════════════════════════════════════════════════════
#  COMPUTATION BLOCK
# ═══════════════════════════════════════════════════════════════════════
if run_btn:
    # Validation
    errors = []
    if es_elev is None or es_stor is None:
        errors.append("Please provide ES curve data.")
    if q50 is None:
        errors.append("Please provide inflow / demand data.")
    if frl_m <= mddl_m:
        errors.append("FRL must be greater than MDDL.")

    if errors:
        for e in errors:
            st.error(f"❌ {e}")
        st.stop()

    with st.spinner("⏳ Running backward calculation & simulation …"):
        try:
            # Build ES curve
            esc = ElevationStorageCurve(es_elev, es_stor)
            val_errors = esc.validate()
            if val_errors:
                for e in val_errors:
                    st.error(f"❌ ES Curve: {e}")
                st.stop()

            # Derived storages
            frl_s  = esc.level_to_storage(frl_m)
            mddl_s = esc.level_to_storage(mddl_m)

            # Initial storage for simulation
            if init_storage_option == "FRL (full reservoir)":
                init_stor = frl_s
            elif init_storage_option == "MDDL (worst-case dry start)":
                init_stor = mddl_s
            else:
                init_stor = st.sidebar.number_input(
                    "Custom initial storage (MCM)",
                    min_value=float(mddl_s), max_value=float(frl_s),
                    value=float(frl_s), step=1.0)

            # Rule curve calculation
            calc = RuleCurveCalculator(
                es_curve=esc,
                frl_level_m=frl_m,
                mddl_level_m=mddl_m,
                inflows_p50=q50,
                inflows_p10=q10,
                demand=demand,
            )
            all_cases   = calc.run_all_cases()
            lower_rc    = calc.get_lower_rc()
            rel_df      = calc.reliability_summary(all_cases)
            tradeoff_df = calc.tradeoff_table(all_cases)

            # Forward simulation (Cases 1, 5, 10)
            sim_engine = ForwardSimulator(
                es_curve=esc,
                frl_level_m=frl_m,
                mddl_level_m=mddl_m,
                inflows_p50=q50,
                demand=demand,
                initial_storage=init_stor,
            )
            simulations = sim_engine.simulate_cases_1_5_10(all_cases)

            # Store everything in session state
            st.session_state.results = {
                'esc': esc, 'frl_m': frl_m, 'mddl_m': mddl_m,
                'frl_s': frl_s, 'mddl_s': mddl_s,
                'reservoir_name': reservoir_name, 'river_name': river_name,
                'all_cases': all_cases, 'lower_rc': lower_rc,
                'rel_df': rel_df, 'tradeoff_df': tradeoff_df,
                'simulations': simulations,
                'q50': q50, 'q10': q10, 'demand': demand,
                'init_stor': init_stor,
            }

        except Exception as ex:
            st.error(f"❌ Calculation error: {ex}")
            import traceback; st.code(traceback.format_exc())
            st.stop()


# ═══════════════════════════════════════════════════════════════════════
#  RESULTS DISPLAY
# ═══════════════════════════════════════════════════════════════════════
if 'results' not in st.session_state:
    st.stop()

R            = st.session_state.results
esc          = R['esc']
frl_m        = R['frl_m'];      mddl_m = R['mddl_m']
frl_s        = R['frl_s'];      mddl_s = R['mddl_s']
all_cases    = R['all_cases']
lower_rc     = R['lower_rc']
rel_df       = R['rel_df']
tradeoff_df  = R['tradeoff_df']
simulations  = R['simulations']
q50          = R['q50'];        q10    = R['q10']
demand       = R['demand']
rname        = R['reservoir_name']
river        = R['river_name']

case5 = next(c for c in all_cases if c.case_number == 5)

# ── TOP-LEVEL METRICS ─────────────────────────────────────────────────
st.markdown(f"## Results — {rname}")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("FRL Storage",   f"{frl_s:.0f} MCM")
m2.metric("MDDL Storage",  f"{mddl_s:.0f} MCM")
m3.metric("Live Storage",  f"{frl_s - mddl_s:.0f} MCM")
m4.metric("Annual P50 Inflow", f"{q50.sum():.0f} MCM")
m5.metric("Annual Demand",     f"{demand.sum():.0f} MCM")
st.markdown("---")


# ── TABS ──────────────────────────────────────────────────────────────
tab_rc, tab_sim, tab_rel, tab_tf, tab_data, tab_export = st.tabs([
    "📈 Rule Curves",
    "🔄 Simulation",
    "✅ Reliability",
    "⚖️ Tradeoff",
    "📋 Data Tables",
    "📥 Export",
])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 1: RULE CURVES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_rc:
    st.markdown("### Upper Rule Curves – All 10 Cases + Lower Rule Curve")

    col_opt1, col_opt2 = st.columns([3, 1])
    with col_opt2:
        show_all_cases = st.checkbox("Show all 10 URC cases", value=True)
        highlight_case = st.selectbox("Highlight case", list(range(1, 11)), index=4)

    fig_rc = go.Figure()

    # FRL and MDDL reference lines
    fig_rc.add_hline(y=frl_m,  line_dash="dash", line_color="red",    line_width=1.5,
                     annotation_text="FRL",  annotation_position="right")
    fig_rc.add_hline(y=mddl_m, line_dash="dash", line_color="orange", line_width=1.5,
                     annotation_text="MDDL", annotation_position="right")

    # Flood cushion zone shading
    fig_rc.add_vrect(
        x0=CUSHION_START_PID, x1=CUSHION_END_PID,
        fillcolor="lightblue", opacity=0.15, layer="below",
        annotation_text="Flood Cushion Zone",
        annotation_position="top left",
    )

    # Upper RC curves
    for case in all_cases:
        if not show_all_cases and case.case_number != highlight_case:
            continue
        is_highlight = (case.case_number == highlight_case)
        fig_rc.add_trace(go.Scatter(
            x=list(range(36)),
            y=case.upper_rc['Level_m'].values,
            mode='lines',
            name=f"URC Case {case.case_number} ({case.cushion_ft:.1f} ft)",
            line=dict(
                color=CUSHION_COLORS[case.case_number - 1],
                width=3 if is_highlight else 1,
                dash='solid' if is_highlight else 'dot',
            ),
            opacity=1.0 if is_highlight else 0.5,
        ))

    # Lower RC
    fig_rc.add_trace(go.Scatter(
        x=list(range(36)),
        y=lower_rc['Level_m'].values,
        mode='lines',
        name="Lower RC (P10)",
        line=dict(color='darkorange', width=2.5, dash='dashdot'),
    ))

    # Anchor markers
    fig_rc.add_vline(x=UPPER_ANCHOR_PID, line_dash="longdash",
                     line_color="navy", line_width=1,
                     annotation_text="Nov-II anchor")
    fig_rc.add_vline(x=LOWER_ANCHOR_PID, line_dash="longdash",
                     line_color="saddlebrown", line_width=1,
                     annotation_text="May-III anchor")

    fig_rc.update_layout(
        title=f"Rule Curves — {rname}",
        xaxis=dict(
            title="10-Day Period",
            tickvals=list(range(36)),
            ticktext=[WATER_YEAR_PERIODS[i] for i in range(36)],
            tickangle=45,
        ),
        yaxis_title="Reservoir Level (m)",
        hovermode='x unified',
        height=520,
        legend=dict(orientation='h', yanchor='bottom', y=-0.6),
    )
    st.plotly_chart(fig_rc, use_container_width=True)

    # Storage version
    with st.expander("📊 Show in Storage (MCM) instead of Level (m)"):
        fig_stor = go.Figure()
        fig_stor.add_hline(y=frl_s,  line_dash="dash", line_color="red",    line_width=1,
                           annotation_text="FRL")
        fig_stor.add_hline(y=mddl_s, line_dash="dash", line_color="orange", line_width=1,
                           annotation_text="MDDL")
        fig_stor.add_vrect(x0=CUSHION_START_PID, x1=CUSHION_END_PID,
                           fillcolor="lightblue", opacity=0.15, layer="below")

        for case in all_cases:
            if not show_all_cases and case.case_number != highlight_case:
                continue
            is_h = (case.case_number == highlight_case)
            fig_stor.add_trace(go.Scatter(
                x=list(range(36)),
                y=case.upper_rc['Storage_MCM'].values,
                name=f"URC Case {case.case_number}",
                line=dict(color=CUSHION_COLORS[case.case_number-1],
                          width=3 if is_h else 1,
                          dash='solid' if is_h else 'dot'),
                opacity=1.0 if is_h else 0.5,
            ))
        fig_stor.add_trace(go.Scatter(
            x=list(range(36)),
            y=lower_rc['Storage_MCM'].values,
            name="Lower RC (P10)",
            line=dict(color='darkorange', width=2.5, dash='dashdot'),
        ))
        fig_stor.update_layout(
            xaxis=dict(tickvals=list(range(36)),
                       ticktext=WATER_YEAR_PERIODS, tickangle=45),
            yaxis_title="Storage (MCM)", height=420,
        )
        st.plotly_chart(fig_stor, use_container_width=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 2: SIMULATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_sim:
    st.markdown("### Forward Simulation – Cases 1, 5, 10 (P50 Inflow Basis)")

    # Summary metrics
    s_cols = st.columns(3)
    case_order = [1, 5, 10]
    sim_label  = {1: "Case 1 (0 ft)", 5: "Case 5 (2 ft)", 10: "Case 10 (4.5 ft)"}

    for i, cn in enumerate(case_order):
        if cn in simulations:
            sim = simulations[cn]
            with s_cols[i]:
                st.markdown(f"**{sim_label[cn]}**")
                st.metric("Avg Satisfaction", f"{sim.avg_satisfaction:.1f}%")
                st.metric("Total Spill (MCM)", f"{sim.total_spill:.0f}")
                st.metric("End Storage (MCM)", f"{sim.end_storage:.0f}")

    st.markdown("---")

    # Storage profile chart
    fig_sim = go.Figure()
    sim_colors = {1: 'steelblue', 5: 'seagreen', 10: 'tomato'}

    for cn in case_order:
        if cn in simulations:
            sim = simulations[cn]
            fig_sim.add_trace(go.Scatter(
                x=list(range(36)),
                y=sim.df['Storage_End_MCM'].values,
                mode='lines',
                name=sim_label[cn],
                line=dict(color=sim_colors[cn], width=2.5),
            ))

    fig_sim.add_hline(y=frl_s,  line_dash="dash", line_color="red",    line_width=1,
                      annotation_text="FRL")
    fig_sim.add_hline(y=mddl_s, line_dash="dash", line_color="orange", line_width=1,
                      annotation_text="MDDL")
    fig_sim.add_vrect(x0=CUSHION_START_PID, x1=CUSHION_END_PID,
                      fillcolor="lightblue", opacity=0.15, layer="below",
                      annotation_text="Flood Cushion Zone")
    fig_sim.update_layout(
        title="Reservoir Storage Profile – Cases 1, 5, 10",
        xaxis=dict(tickvals=list(range(36)),
                   ticktext=WATER_YEAR_PERIODS, tickangle=45),
        yaxis_title="Storage (MCM)",
        hovermode='x unified', height=450,
    )
    st.plotly_chart(fig_sim, use_container_width=True)

    # Spill comparison
    fig_spill = go.Figure()
    for cn in case_order:
        if cn in simulations:
            sim = simulations[cn]
            fig_spill.add_trace(go.Bar(
                x=list(range(36)),
                y=sim.df['Spill_MCM'].values,
                name=sim_label[cn],
                marker_color=sim_colors[cn],
                opacity=0.75,
            ))
    fig_spill.update_layout(
        title="Period-wise Spill Comparison",
        xaxis=dict(tickvals=list(range(36)),
                   ticktext=WATER_YEAR_PERIODS, tickangle=45),
        yaxis_title="Spill (MCM)",
        barmode='group', height=360,
    )
    st.plotly_chart(fig_spill, use_container_width=True)

    # Detailed tables per case
    for cn in case_order:
        if cn not in simulations:
            continue
        with st.expander(f"📋 Period-wise Details — {sim_label[cn]}"):
            st.dataframe(
                simulations[cn].df.style.background_gradient(
                    subset=['Spill_MCM'], cmap='Reds'
                ).background_gradient(
                    subset=['Satisfaction_%'], cmap='Greens'
                ),
                use_container_width=True, height=400,
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3: RELIABILITY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_rel:
    st.markdown("### Reliability Summary – All 10 Cases")
    st.dataframe(
        rel_df.style.background_gradient(subset=['Flood Space(MCM)'], cmap='Blues')
                    .background_gradient(subset=['Sat P50 (%)'],      cmap='Greens')
                    .background_gradient(subset=['Sat P10 (%)'],      cmap='Oranges'),
        use_container_width=True, height=420,
    )

    # Bar chart: flood space vs demand satisfaction
    fig_rel = go.Figure()
    fig_rel.add_trace(go.Bar(
        x=[f"Case {r['Case']}\n({r['Cushion (ft)']}ft)" for _, r in rel_df.iterrows()],
        y=rel_df['Flood Space(MCM)'].values,
        name='Flood Space (MCM)',
        marker_color='steelblue',
        yaxis='y1',
    ))
    fig_rel.add_trace(go.Scatter(
        x=[f"Case {r['Case']}\n({r['Cushion (ft)']}ft)" for _, r in rel_df.iterrows()],
        y=rel_df['Sat P50 (%)'].values,
        name='P50 Satisfaction (%)',
        mode='lines+markers',
        line=dict(color='seagreen', width=2),
        yaxis='y2',
    ))
    fig_rel.update_layout(
        title="Flood Space vs Demand Satisfaction",
        yaxis=dict(title="Flood Space (MCM)"),
        yaxis2=dict(title="Demand Satisfaction (%)", overlaying='y', side='right'),
        height=380,
    )
    st.plotly_chart(fig_rel, use_container_width=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 4: TRADEOFF
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_tf:
    st.markdown("### Flood Risk vs Drought Risk Tradeoff")
    st.dataframe(
        tradeoff_df.style.background_gradient(subset=['Flood Space (MCM)'], cmap='Blues')
                         .background_gradient(subset=['Flood Risk Score'],   cmap='Reds'),
        use_container_width=True, height=380,
    )
    st.info(
        "★ **Case 5 (2.0 ft cushion)** is the initial recommendation. "
        "Override this based on downstream population density, historical flood damage, "
        "and dam safety board requirements."
    )

    # Scatter plot: flood risk vs drought risk
    flood_scores = tradeoff_df['Flood Risk Score'].values
    flood_space  = tradeoff_df['Flood Space (MCM)'].values
    end_storages = [simulations[cn].end_storage if cn in simulations else None
                    for cn in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]]

    fig_tf = go.Figure()
    colors_tf = [f"hsl({int(i*25)},70%,50%)" for i in range(10)]
    for i, case in enumerate(all_cases):
        es_val = end_storages[i]
        fig_tf.add_trace(go.Scatter(
            x=[flood_scores[i]],
            y=[es_val if es_val is not None else 0],
            mode='markers+text',
            name=f"Case {i+1}",
            marker=dict(size=16, color=CUSHION_COLORS[i],
                        line=dict(color='black', width=1)),
            text=[f"C{i+1}"],
            textposition='middle center',
            textfont=dict(color='white', size=10),
        ))

    fig_tf.update_layout(
        title="Tradeoff: Flood Risk Score vs End-of-Year Storage",
        xaxis_title="Flood Risk Score (0 = no cushion → 10 = max cushion)",
        yaxis_title="End-of-Year Storage (MCM) – Cases 1,5,10 only",
        showlegend=False, height=400,
    )
    st.plotly_chart(fig_tf, use_container_width=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 5: DATA TABLES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_data:
    st.markdown("### Raw Data Tables")

    sub = st.selectbox("Select table", [
        "ES Curve",
        "Inflows & Demand",
        "Upper RC – Case 5 (Recommended)",
        "Upper RC – All Cases (Levels)",
        "Lower RC",
    ])

    if sub == "ES Curve":
        st.dataframe(esc.to_dataframe(), use_container_width=True)

    elif sub == "Inflows & Demand":
        st.dataframe(make_period_df(q50, q10, demand), use_container_width=True)

    elif sub == "Upper RC – Case 5 (Recommended)":
        st.dataframe(case5.upper_rc, use_container_width=True)

    elif sub == "Upper RC – All Cases (Levels)":
        combined = pd.DataFrame({'PID': range(36), 'Period': WATER_YEAR_PERIODS})
        for case in all_cases:
            combined[f"Case{case.case_number}_{case.cushion_ft}ft"] = \
                case.upper_rc['Level_m'].values
        combined['LowerRC_m'] = lower_rc['Level_m'].values
        st.dataframe(combined, use_container_width=True)

    elif sub == "Lower RC":
        st.dataframe(lower_rc, use_container_width=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 6: EXPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_export:
    st.markdown("### Export Results")

    col_xl, col_pdf = st.columns(2)

    # ── Excel Export ─────────────────────────────────────────────────
    with col_xl:
        st.markdown("#### 📊 Excel Workbook")
        st.write("7 formatted sheets matching PKm model structure:")
        st.caption(
            "1_Summary · 2_Demand · 3_Inflows · "
            "4_UpperRC_AllCases · 5_LowerRC_AllCases · "
            "6_DemSat_AllCases · 10_CrossComparison"
        )
        if st.button("Prepare Excel Download", use_container_width=True):
            with st.spinner("Building workbook …"):
                try:
                    xl_bytes = build_excel_workbook(
                        reservoir_name=rname,
                        river_name=river,
                        frl_m=frl_m,
                        mddl_m=mddl_m,
                        frl_s=frl_s,
                        mddl_s=mddl_s,
                        all_cases=all_cases,
                        q50=q50,
                        q10=q10,
                        demand=demand,
                        es_curve=esc,
                        unit_label="MCM",
                    )
                    st.download_button(
                        label="📥 Download Excel",
                        data=xl_bytes,
                        file_name=f"{rname.replace(' ','_')}_RuleCurve.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                    st.success("✓ Workbook ready — 7 sheets, colour-coded")
                except Exception as ex:
                    st.error(f"❌ Excel error: {ex}")
                    import traceback; st.code(traceback.format_exc())


    # ── PDF Export ───────────────────────────────────────────────────
    with col_pdf:
        st.markdown("#### 📄 PDF Report")
        st.write("Professional report suitable for Dam Safety Authority submission.")
        if st.button("Prepare PDF Download", use_container_width=True):
            with st.spinner("Generating PDF …"):
                try:
                    pdf_bytes = generate_pdf_report(
                        reservoir_name=reservoir_name,
                        river_name=river_name,
                        frl_m=frl_m,
                        mddl_m=mddl_m,
                        frl_storage=frl_s,
                        mddl_storage=mddl_s,
                        all_cases=all_cases,
                        simulations=simulations,
                        reliability_df=rel_df,
                        tradeoff_df=tradeoff_df,
                        upper_rc_case5=case5.upper_rc,
                        lower_rc=lower_rc,
                    )
                    st.download_button(
                        label="📥 Download PDF",
                        data=pdf_bytes,
                        file_name=f"{reservoir_name.replace(' ', '_')}_RuleCurve_Report.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as ex:
                    st.error(f"❌ PDF generation failed: {ex}")

    st.markdown("---")
    st.caption(
        "DISCLAIMER: This tool is developed independently using published CWC engineering "
        "guidelines. Not an official product of WRD Tamil Nadu or SDSO. All outputs must "
        "be reviewed and endorsed by a qualified engineer before official submission."
    )
