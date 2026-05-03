"""
Strategic Asset Clock™ V3 — Interface Streamlit
Intégration du moteur probabiliste, stress testing, et risk profiling.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import math
from datetime import datetime

from config import *
from engine import *
from distributions import ProbabilisticEngine, StressScenarios
from utils import format_eur, format_pct, clamp

# ─────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Strategic Asset Clock™ V3",
    page_icon="⏱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# STYLES (identiques V2 + ajouts V3)
# ─────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #f8f7f4; }
.sac-title { font-size: 1.6rem; font-weight: 600; letter-spacing: -0.5px; margin-bottom: 0; }
.sac-sub   { font-size: 0.85rem; color: #888; margin-bottom: 1.5rem; }
.kpi-box   { background: #fff; border: 1px solid #e8e6e0; border-radius: 10px;
             padding: 14px 18px; text-align: center; }
.kpi-label { font-size: 0.72rem; color: #888; text-transform: uppercase;
             letter-spacing: .06em; margin-bottom: 4px; }
.kpi-value { font-size: 1.5rem; font-weight: 600; color: #1a1a1a; }
.kpi-sub   { font-size: 0.75rem; color: #aaa; margin-top: 2px; }
.prob-bar  { display: flex; border-radius: 6px; overflow: hidden; height: 28px;
             margin: 8px 0; }
.prob-seg  { display: flex; align-items: center; justify-content: center;
             font-size: 0.7rem; font-weight: 600; color: #fff;
             transition: width 0.4s ease; }
.risk-gauge { position: relative; height: 12px; border-radius: 6px;
              background: linear-gradient(90deg, #1D9E75 0%, #BA7517 50%, #A32D2D 100%);
              margin: 8px 0; }
.risk-needle { position: absolute; top: -4px; width: 4px; height: 20px;
               background: #1a1a1a; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════
# SIDEBAR — INPUTS (identiques V2)
# ═══════════════════════════════════════════
with st.sidebar:
    st.markdown("### Strategic Asset Clock™ V3")
    st.markdown("*Scoring probabiliste*")
    st.markdown("---")

    st.markdown("**Identification de l'actif**")
    nom_hotel = st.text_input("Nom de l'hôtel", value="Hôtel Le Clos du Lac")
    segment = st.selectbox("Segment", list(ROA_BENCHMARKS.keys()), index=1)
    nb_chambres = st.number_input("Nombre de chambres", 10, 1000, 52)

    st.markdown("---")
    st.markdown("**L1 · Cycle marché**")

    # Mode probabiliste toggle
    probabilistic_mode = st.toggle("🎲 Mode probabiliste (Monte Carlo)", value=True)
    if probabilistic_mode:
        n_sims = st.select_slider("Simulations MC", [1000, 5000, 10000, 25000, 50000], value=10000)
    else:
        n_sims = 0

    mode_macro = st.radio(
        "Mode de détection",
        ["🤖 Automatique (proxy variables)", "✏️ Manuel (override AM)"],
        index=0,
        horizontal=True,
    )

    if mode_macro == "✏️ Manuel (override AM)":
        macro_phase = st.selectbox("Phase macro (HVS/JLL)", MACRO_PHASES, index=0)
        cycle_result = None
        phase_dist = None
    else:
        with st.expander("📊 Variables macro — Demande", expanded=False):
            gdp_growth_m      = st.number_input("PIB croissance réelle (%)", -5.0, 15.0, 1.2, step=0.1)
            tourism_growth_m  = st.number_input("Croissance arrivées touristiques (%)", -20.0, 30.0, 5.5, step=0.1)
            cci_m             = st.number_input("Consumer Confidence Index (pts)", 50.0, 150.0, 91.0, step=1.0)
            bci_m             = st.number_input("Business Confidence Index (pts)", 50.0, 150.0, 97.0, step=1.0)
            air_traffic_m     = st.number_input("Croissance trafic aérien (%)", -30.0, 30.0, 6.5, step=0.1)
        with st.expander("🏗️ Variables macro — Offre", expanded=False):
            supply_growth_m   = st.number_input("Croissance offre hôtelière nationale (%)", 0.0, 15.0, 2.2, step=0.1)
            pipeline_pct_m    = st.number_input("Pipeline offre locale (%)", 0.0, 30.0, 2.8, step=0.1)
            absorption_m      = st.number_input("Taux absorption (mois)", 3.0, 48.0, 14.0, step=1.0)
            revpar_growth_m   = st.number_input("Croissance RevPAR 3 ans (%)", -10.0, 20.0, 4.2, step=0.1)
        with st.expander("💰 Variables macro — Financement", expanded=False):
            interest_rate_m   = st.number_input("Taux directeur BCE (%)", 0.0, 15.0, 3.65, step=0.05)
            spread_bps_m      = st.number_input("Spread souverain (bps)", 0.0, 1000.0, 85.0, step=5.0)
            vix_m             = st.number_input("VIX (pts)", 5.0, 80.0, 16.0, step=1.0)
            credit_growth_m   = st.number_input("Croissance crédit privé (%)", -5.0, 20.0, 3.2, step=0.1)
        market_type_m = st.selectbox("Type de marché", ["developed", "emerging"], index=0,
                                     format_func=lambda x: "Développé" if x == "developed" else "Émergent")

        # Inputs dict pour moteur
        macro_inputs = {
            "gdp_growth": gdp_growth_m, "tourism_growth": tourism_growth_m,
            "cci": cci_m, "bci": bci_m, "air_traffic": air_traffic_m,
            "supply_growth": supply_growth_m, "pipeline_pct": pipeline_pct_m,
            "absorption_months": absorption_m, "revpar_growth_3y": revpar_growth_m,
            "interest_rate": interest_rate_m, "spread_bps": spread_bps_m,
            "vix": vix_m, "credit_growth": credit_growth_m,
        }

        # Calcul déterministe
        cycle_result = compute_market_cycle(
            gdp_growth=gdp_growth_m, tourism_growth=tourism_growth_m,
            cci=cci_m, bci=bci_m, air_traffic=air_traffic_m,
            supply_growth=supply_growth_m, local_pipeline_pct=pipeline_pct_m,
            absorption_months=absorption_m, revpar_growth_3y=revpar_growth_m,
            interest_rate=interest_rate_m, sovereign_spread_bps=spread_bps_m,
            vix=vix_m, credit_growth=credit_growth_m,
            market_type=market_type_m,
        )
        macro_phase = cycle_result["phase"]

        # Calcul probabiliste
        if probabilistic_mode:
            prob_engine = ProbabilisticEngine(n_simulations=n_sims, seed=42)
            phase_dist = prob_engine.simulate_market_cycle(macro_inputs, market_type_m)
        else:
            phase_dist = None

    macro_dir = st.selectbox("Direction macro", DIRECTIONS, index=0)
    macro_vel = st.selectbox("Vélocité macro", VELOCITIES, index=1)

    st.markdown("---")
    st.markdown("**L1 · Cycle asset**")
    annee_reno = st.number_input("Année dernière réno majeure", 1990, 2024, 2017)
    ratio_correctif = st.slider("Ratio CapEx correctif / total (%)", 0, 100, 35) / 100
    gop_trend = st.selectbox("GOP trend 3 ans", ["Hausse", "Stable", "Légère baisse", "Forte baisse"], index=1)
    score_tech = st.slider("Score technique bâti (1-5)", 1, 5, 3)
    asset_override = st.checkbox("Override phase asset", value=False)
    if asset_override:
        asset_phase_idx = st.selectbox("Phase asset", range(4),
                                        format_func=lambda i: ASSET_PHASES[i], index=2)
    else:
        asset_phase_idx = asset_phase_from_proxy(annee_reno, ratio_correctif, gop_trend, score_tech)
    asset_dir = st.selectbox("Direction asset", DIRECTIONS, index=2)
    asset_vel = st.selectbox("Vélocité asset", VELOCITIES, index=1)

    st.markdown("---")
    st.markdown("**L2 · Analyse micro**")
    pipeline_ch = st.number_input("Chambres en construction (24m)", 0, 2000, 80)
    rgi = st.number_input("RGI vs comp set", 0.50, 1.50, 1.05, step=0.01)
    demande_sc = st.slider("Demande locale (1-5)", 1, 5, 3)
    position_sc = st.slider("Positionnement relatif (1-5)", 1, 5, 3)

    st.markdown("---")
    st.markdown("**L3 · Données financières**")
    noi = st.number_input("NOI annuel (€)", 0, 10_000_000, 520_000, step=10_000)
    valeur_marche = st.number_input("Valeur de marché (€)", 100_000, 50_000_000, 9_500_000, step=100_000)
    valeur_book = st.number_input("Valeur book (€)", 100_000, 50_000_000, 8_200_000, step=100_000)
    revpar = st.number_input("RevPAR (€)", 0, 1000, 74)
    capex_estime = st.number_input("CapEx réno estimé (€)", 0, 10_000_000, 1_800_000, step=50_000)

    st.markdown("---")
    st.markdown("**L6 · Simulateur**")
    decalage_ans = st.slider("Décalage décision (années)", 1, 5, 2)
    taux_declin_noi = st.slider("Taux déclin NOI annuel (%)", 0, 20, 5) / 100
    taux_surcoute_capex = st.slider("Surcoût CapEx glissement (%)", 0, 80, 35) / 100


# ═══════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════
_errors = []
if valeur_marche <= 0:
    _errors.append("Valeur de marché doit être > 0.")
if valeur_book <= 0:
    _errors.append("Valeur book doit être > 0.")
if _errors:
    for e in _errors:
        st.error(f"⛔ {e}")
    st.stop()


# ═══════════════════════════════════════════
# CALCULS CENTRAUX
# ═══════════════════════════════════════════
micro_score = compute_micro_score(pipeline_ch, rgi, demande_sc, position_sc)
roa_reel, roa_book, roa_benchmark, gap_benchmark, trigger_option = compute_roa_reel(
    noi, valeur_marche, valeur_book, segment)
window_mois = compute_window(macro_dir, macro_vel, asset_dir, asset_vel, micro_score, asset_phase_idx)
noi_perdu, surcoute_capex, decote_valeur, total_cost, glissement = simulate_timing(
    noi, valeur_marche, asset_phase_idx, decalage_ans,
    taux_declin_noi, taux_surcoute_capex, capex_estime)

asset_phase = ASSET_PHASES[asset_phase_idx]
prescription = MATRIX[macro_phase][asset_phase]
signal = prescription["signal"]
sig_cfg = SIGNAL_CONFIG[signal]

# Probabiliste — timing
timing_dist = None
risk_profile = None
stress_results = None

if probabilistic_mode and mode_macro != "✏️ Manuel (override AM)":
    prob_engine = ProbabilisticEngine(n_simulations=n_sims, seed=42)
    
    timing_dist = prob_engine.simulate_timing_distribution(
        noi, valeur_marche, asset_phase_idx, decalage_ans,
        taux_declin_noi, taux_surcoute_capex, capex_estime)
    
    if phase_dist is not None:
        risk_profile = prob_engine.compute_risk_profile(
            phase_dist, timing_dist, roa_reel, roa_benchmark,
            micro_score, asset_phase_idx, valeur_marche)
    
    stress_results = StressScenarios.run_all_scenarios(
        prob_engine, macro_inputs, market_type_m)


# ═══════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════
today = datetime.now().strftime("%B %Y")
st.markdown(f'<div class="sac-title">Strategic Asset Clock™ V3</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sac-sub">{nom_hotel} · {nb_chambres} ch. · {segment} · {today}'
            f'{" · 🎲 Mode probabiliste" if probabilistic_mode else ""}</div>',
            unsafe_allow_html=True)


# ═══════════════════════════════════════════
# KPI ROW — enrichi probabiliste
# ═══════════════════════════════════════════
k1, k2, k3, k4, k5, k6, k7 = st.columns(7)

with k1:
    conf_label = ""
    if phase_dist:
        conf_label = f"P={phase_dist.probabilities.get(macro_phase, 0)*100:.0f}%"
    st.markdown(f"""<div class="kpi-box">
    <div class="kpi-label">Cycle marché</div>
    <div class="kpi-value" style="color:{MACRO_COLORS[macro_phase]};font-size:1.1rem">{macro_phase}</div>
    <div class="kpi-sub">{conf_label if conf_label else f'{macro_dir} · {macro_vel}'}</div>
    </div>""", unsafe_allow_html=True)

with k2:
    st.markdown(f"""<div class="kpi-box">
    <div class="kpi-label">Cycle asset</div>
    <div class="kpi-value" style="color:{ASSET_COLORS[asset_phase]};font-size:0.85rem">{asset_phase}</div>
    <div class="kpi-sub">{asset_dir} · {asset_vel}</div>
    </div>""", unsafe_allow_html=True)

with k3:
    roa_color = "#1D9E75" if roa_reel >= roa_benchmark else "#A32D2D"
    st.markdown(f"""<div class="kpi-box">
    <div class="kpi-label">ROA réel</div>
    <div class="kpi-value" style="color:{roa_color}">{roa_reel*100:.2f}%</div>
    <div class="kpi-sub">benchmark {roa_benchmark*100:.1f}%</div>
    </div>""", unsafe_allow_html=True)

with k4:
    micro_color = "#1D9E75" if micro_score > 0 else ("#A32D2D" if micro_score < 0 else "#888")
    st.markdown(f"""<div class="kpi-box">
    <div class="kpi-label">Score micro</div>
    <div class="kpi-value" style="color:{micro_color}">{micro_score:+.1f}</div>
    <div class="kpi-sub">{"Amplificateur" if micro_score >= 0.5 else ("Atténuateur" if micro_score <= -0.5 else "Neutre")}</div>
    </div>""", unsafe_allow_html=True)

with k5:
    w_color = "#1D9E75" if window_mois >= 18 else ("#BA7517" if window_mois >= 10 else "#A32D2D")
    st.markdown(f"""<div class="kpi-box">
    <div class="kpi-label">Fenêtre</div>
    <div class="kpi-value" style="color:{w_color}">{window_mois} mois</div>
    <div class="kpi-sub">avant recalibration</div>
    </div>""", unsafe_allow_html=True)

with k6:
    cost_label = format_eur(total_cost)
    ci_label = ""
    if timing_dist:
        ci_label = f"IC90: {format_eur(timing_dist.p5_cost)}–{format_eur(timing_dist.p95_cost)}"
    st.markdown(f"""<div class="kpi-box">
    <div class="kpi-label">Coût décalage {decalage_ans}a</div>
    <div class="kpi-value" style="color:#A32D2D;font-size:1.1rem">−{cost_label}</div>
    <div class="kpi-sub">{ci_label if ci_label else 'valorisation perdue'}</div>
    </div>""", unsafe_allow_html=True)

with k7:
    if risk_profile:
        sri = risk_profile.strategic_risk_index
        sri_color = "#1D9E75" if sri < 35 else ("#BA7517" if sri < 65 else "#A32D2D")
        st.markdown(f"""<div class="kpi-box">
        <div class="kpi-label">Risk Index</div>
        <div class="kpi-value" style="color:{sri_color}">{sri:.0f}/100</div>
        <div class="kpi-sub">Strategic Risk Index</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="kpi-box">
        <div class="kpi-label">Risk Index</div>
        <div class="kpi-value" style="color:#888">—</div>
        <div class="kpi-sub">Activer mode 🎲</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ═══════════════════════════════════════════
# TABS — V3 enrichi
# ═══════════════════════════════════════════
tabs = ["⏱ Horloge & Prescription", "📊 ROA & Options", "🧭 Micro"]

if probabilistic_mode:
    tabs += ["🎲 Distribution des phases", "📈 Stress Testing", "🛡️ Risk Profile"]

tabs += ["⏳ Simulateur de timing", "📋 Rapport exécutif"]

tab_objects = st.tabs(tabs)
tab_idx = 0


# ══════════════════════════════════════════
# TAB — HORLOGE & PRESCRIPTION (identique V2)
# ══════════════════════════════════════════
with tab_objects[tab_idx]:
    tab_idx += 1
    col_clock, col_presc = st.columns([1, 1], gap="large")

    with col_clock:
        st.markdown("##### Positionnement sur les deux cycles")

        macro_angles = {"Recovery": 315, "Expansion": 45, "Hypersupply": 135, "Recession": 225}
        asset_angles = {0: 315, 1: 45, 2: 135, 3: 225}
        r_macro = 0.72
        r_asset = 0.38

        fig_clock = go.Figure()

        for ph, ang, col in [
            ("Recovery", 315, "rgba(29,158,117,0.12)"),
            ("Expansion", 45, "rgba(24,95,165,0.12)"),
            ("Hypersupply", 135, "rgba(186,117,23,0.12)"),
            ("Recession", 225, "rgba(163,45,45,0.12)"),
        ]:
            theta = [ang - 45 + j for j in range(91)]
            r_fill = [1.0] * 91
            fig_clock.add_trace(go.Scatterpolar(
                r=r_fill + [0], theta=theta + [theta[0]],
                fill="toself", fillcolor=col,
                line=dict(color="rgba(0,0,0,0)", width=0),
                hoverinfo="skip", showlegend=False,
            ))
            lx = math.cos(math.radians(ang))
            ly = math.sin(math.radians(ang))
            fig_clock.add_annotation(
                x=lx * 0.82, y=ly * 0.82,
                text=ph, showarrow=False,
                font=dict(size=10, color=MACRO_COLORS[ph]),
                xref="paper", yref="paper",
                xanchor="center", yanchor="middle",
            )

        # Cercle asset
        fig_clock.add_trace(go.Scatterpolar(
            r=[0.5] * 361, theta=list(range(361)),
            mode="lines", line=dict(color="#cccccc", width=1, dash="dot"),
            hoverinfo="skip", showlegend=False,
        ))

        for i, ph in enumerate(ASSET_PHASES):
            fig_clock.add_trace(go.Scatterpolar(
                r=[0.50], theta=[asset_angles[i]],
                mode="text", text=[f"Ph.{i+1}"],
                textfont=dict(size=8, color=ASSET_COLORS[ph]),
                hoverinfo="skip", showlegend=False,
            ))

        # Probabilité visuelle — taille du marqueur proportionnelle à P(phase)
        marker_size = 18
        if phase_dist:
            p_dominant = phase_dist.probabilities.get(macro_phase, 0.5)
            marker_size = max(12, int(p_dominant * 28))

        fig_clock.add_trace(go.Scatterpolar(
            r=[r_macro], theta=[macro_angles[macro_phase]],
            mode="markers",
            marker=dict(size=marker_size, color=MACRO_COLORS[macro_phase], symbol="circle",
                        opacity=0.9 if not phase_dist else max(0.4, phase_dist.probabilities.get(macro_phase, 0.5))),
            name="Cycle marché",
            hovertemplate=f"<b>Marché</b>: {macro_phase}"
                          + (f"<br>P={phase_dist.probabilities.get(macro_phase, 0)*100:.0f}%" if phase_dist else "")
                          + "<extra></extra>",
        ))

        # Marqueurs secondaires pour phases alternatives (V3)
        if phase_dist:
            for ph_name, ph_prob in phase_dist.probabilities.items():
                if ph_name != macro_phase and ph_prob > 0.10:
                    fig_clock.add_trace(go.Scatterpolar(
                        r=[r_macro * 0.90], theta=[macro_angles[ph_name]],
                        mode="markers",
                        marker=dict(size=max(6, int(ph_prob * 20)),
                                    color=MACRO_COLORS[ph_name], symbol="circle",
                                    opacity=ph_prob * 0.8),
                        name=f"{ph_name} ({ph_prob*100:.0f}%)",
                        hovertemplate=f"<b>{ph_name}</b>: P={ph_prob*100:.0f}%<extra></extra>",
                    ))

        fig_clock.add_trace(go.Scatterpolar(
            r=[r_asset], theta=[asset_angles[asset_phase_idx]],
            mode="markers",
            marker=dict(size=14, color=ASSET_COLORS[asset_phase], symbol="diamond"),
            name="Cycle asset",
        ))

        dir_delta = {"Ascending ↑": 15, "Stable →": 0, "Descending ↓": -15}
        macro_next = macro_angles[macro_phase] + dir_delta[macro_dir]
        asset_next = asset_angles[asset_phase_idx] + dir_delta[asset_dir]
        fig_clock.add_trace(go.Scatterpolar(
            r=[r_macro, r_macro * 1.06], theta=[macro_angles[macro_phase], macro_next],
            mode="lines", line=dict(color=MACRO_COLORS[macro_phase], width=2),
            hoverinfo="skip", showlegend=False,
        ))
        fig_clock.add_trace(go.Scatterpolar(
            r=[r_asset, r_asset * 1.15], theta=[asset_angles[asset_phase_idx], asset_next],
            mode="lines", line=dict(color=ASSET_COLORS[asset_phase], width=2),
            hoverinfo="skip", showlegend=False,
        ))

        fig_clock.update_layout(
            polar=dict(
                radialaxis=dict(visible=False, range=[0, 1]),
                angularaxis=dict(visible=False, direction="clockwise", rotation=90),
                bgcolor="rgba(0,0,0,0)",
            ),
            showlegend=True,
            legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center", font=dict(size=10)),
            margin=dict(l=20, r=20, t=20, b=40),
            height=380,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_clock, use_container_width=True)

        # Barre de probabilité V3
        if phase_dist:
            bar_html = '<div class="prob-bar">'
            for ph in MACRO_PHASES:
                p = phase_dist.probabilities.get(ph, 0)
                if p > 0.02:
                    bar_html += (f'<div class="prob-seg" style="width:{p*100:.0f}%;'
                                 f'background:{MACRO_COLORS[ph]}">'
                                 f'{ph[:3]} {p*100:.0f}%</div>')
            bar_html += '</div>'
            st.markdown(bar_html, unsafe_allow_html=True)
            st.caption(f"Entropie : {phase_dist.entropy:.2f}/2.00 · "
                       f"Confiance : {phase_dist.confidence:.0f}% · "
                       f"{n_sims:,} simulations MC")

    with col_presc:
        st.markdown("##### Prescription stratégique")

        # Signal badge (identique V2)
        stability_note = ""
        if risk_profile:
            stability_note = f" · Stabilité {risk_profile.stability_score:.0f}%"

        st.markdown(f"""
        <div style="background:{sig_cfg['bg']};border:1px solid {sig_cfg['border']};
                    border-radius:10px;padding:16px 20px;margin-bottom:14px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span style="font-size:1.05rem;font-weight:600;color:{sig_cfg['color']}">
              {prescription['titre']}</span>
            <span style="background:{sig_cfg['border']};color:#fff;padding:3px 10px;
                         border-radius:20px;font-size:0.7rem;font-weight:600">
              {sig_cfg['label']}</span>
          </div>
          <div style="font-size:0.85rem;color:#555;line-height:1.5">
            {prescription['detail']}</div>
          <div style="margin-top:10px;font-size:0.75rem;color:#888">
            {macro_phase} × {asset_phase} · Micro {micro_score:+.1f} · ~{window_mois} mois{stability_note}</div>
        </div>""", unsafe_allow_html=True)

        st.markdown("**Initiatives prioritaires**")
        for init_titre, init_impact, init_prio in prescription["initiatives"]:
            prio_color, prio_dot = INIT_COLORS[init_prio]
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:10px;padding:9px 14px;
                        margin-bottom:6px;background:#fff;border:1px solid #e8e6e0;
                        border-radius:8px">
              <span style="color:{prio_color};font-size:10px">{prio_dot}</span>
              <span style="flex:1;font-size:0.85rem">{init_titre}</span>
              <span style="font-size:0.72rem;color:#888;background:#f1efe8;
                           padding:2px 8px;border-radius:10px">Impact {init_impact}</span>
              <span style="font-size:0.72rem;color:{prio_color};font-weight:600">{init_prio}</span>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════
# TAB — ROA & OPTIONS (identique V2 — voir V2)
# ══════════════════════════════════════════
with tab_objects[tab_idx]:
    tab_idx += 1
    col_roa, col_opt = st.columns([1, 1], gap="large")

    with col_roa:
        st.markdown("##### ROA réel vs ROA book vs benchmark")
        fig_roa = go.Figure()
        categories = ["ROA réel", "ROA book", f"Benchmark\n{segment}"]
        values_roa = [roa_reel * 100, roa_book * 100, roa_benchmark * 100]
        colors_roa = [
            "#1D9E75" if roa_reel >= roa_benchmark else "#A32D2D",
            "#185FA5", "#888780",
        ]
        fig_roa.add_trace(go.Bar(
            x=categories, y=values_roa,
            marker_color=colors_roa,
            text=[f"{v:.2f}%" for v in values_roa],
            textposition="outside",
        ))
        fig_roa.update_layout(
            yaxis=dict(title="ROA (%)", range=[0, max(values_roa) * 1.3]),
            height=300, margin=dict(l=0, r=0, t=20, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
        )
        st.plotly_chart(fig_roa, use_container_width=True)

    with col_opt:
        st.markdown("##### Option Analysis")
        option_scores = compute_option_scores(signal, gap_benchmark)
        for opt, score in sorted(option_scores.items(), key=lambda x: -x[1]):
            bar_w = score / 5 * 100
            bar_col = "#1D9E75" if score >= 4 else ("#BA7517" if score >= 3 else "#888780")
            st.markdown(f"""
            <div style="margin-bottom:10px">
              <div style="display:flex;justify-content:space-between;font-size:0.82rem;margin-bottom:4px">
                <span>{opt}</span>
                <span style="font-weight:600;color:{bar_col}">{score}/5</span>
              </div>
              <div style="background:#e8e6e0;border-radius:4px;height:6px">
                <div style="width:{bar_w:.0f}%;height:6px;background:{bar_col};border-radius:4px"></div>
              </div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════
# TAB — MICRO (identique V2 — voir V2)
# ══════════════════════════════════════════
with tab_objects[tab_idx]:
    tab_idx += 1
    st.markdown("##### Analyse micro-marché")
    st.info(f"Score micro global : **{micro_score:+.1f}** / 2.0")
    # (Radar identique V2 — omis pour brièveté)


# ══════════════════════════════════════════
# TAB V3 — DISTRIBUTION DES PHASES (NOUVEAU)
# ══════════════════════════════════════════
if probabilistic_mode:
    with tab_objects[tab_idx]:
        tab_idx += 1
        st.markdown("##### 🎲 Distribution probabiliste des phases du cycle")

        if phase_dist:
            col_d1, col_d2 = st.columns([1, 1], gap="large")

            with col_d1:
                # Barplot probabilités
                phases_sorted = phase_dist.phase_rank()
                fig_prob = go.Figure()
                fig_prob.add_trace(go.Bar(
                    x=[p[0] for p in phases_sorted],
                    y=[p[1] * 100 for p in phases_sorted],
                    marker_color=[MACRO_COLORS[p[0]] for p in phases_sorted],
                    text=[f"{p[1]*100:.1f}%" for p in phases_sorted],
                    textposition="outside",
                ))
                fig_prob.update_layout(
                    yaxis=dict(title="Probabilité (%)", range=[0, 100]),
                    height=320, margin=dict(l=0, r=0, t=20, b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_prob, use_container_width=True)

                # Entropie gauge
                ent = phase_dist.entropy
                ent_pct = ent / 2.0 * 100
                ent_color = "#1D9E75" if ent < 0.8 else ("#BA7517" if ent < 1.4 else "#A32D2D")
                ent_label = "Forte certitude" if ent < 0.8 else ("Incertitude modérée" if ent < 1.4 else "Forte incertitude")
                st.markdown(f"""
                <div style="background:#f8f7f4;border-radius:8px;padding:12px 16px;margin-top:8px">
                  <div style="display:flex;justify-content:space-between">
                    <span style="font-size:0.72rem;color:#888;text-transform:uppercase">Entropie de Shannon</span>
                    <span style="font-size:0.78rem;font-weight:600;color:{ent_color}">{ent:.2f}/2.00 — {ent_label}</span>
                  </div>
                  <div style="background:#e8e6e0;border-radius:4px;height:8px;margin-top:6px">
                    <div style="width:{ent_pct:.0f}%;height:8px;background:{ent_color};border-radius:4px"></div>
                  </div>
                  <div style="font-size:0.72rem;color:#888;margin-top:4px">
                    0 = certitude absolue · 2 = incertitude maximale (4 phases équiprobables)</div>
                </div>""", unsafe_allow_html=True)

            with col_d2:
                # Distributions des scores : demande, offre, finance
                st.markdown("**Intervalles de confiance des scores**")

                for label, dist, color in [
                    ("Demande", phase_dist.demand_dist, "#185FA5"),
                    ("Offre maîtrisée", phase_dist.supply_dist, "#1D9E75"),
                    ("Financement", phase_dist.finance_dist, "#BA7517"),
                ]:
                    mean = dist["mean"]
                    p5 = dist["p5"]
                    p95 = dist["p95"]
                    std = dist["std"]
                    
                    # Barre d'intervalle
                    bar_left = p5
                    bar_width = p95 - p5
                    mean_pos = (mean - p5) / bar_width * 100 if bar_width > 0 else 50
                    
                    st.markdown(f"""
                    <div style="margin-bottom:14px">
                      <div style="display:flex;justify-content:space-between;font-size:0.82rem;margin-bottom:4px">
                        <span><b>{label}</b></span>
                        <span style="color:{color};font-weight:600">{mean:.0f}/100 ± {std:.0f}</span>
                      </div>
                      <div style="position:relative;background:#e8e6e0;border-radius:4px;height:18px;margin-top:4px">
                        <div style="position:absolute;left:{bar_left}%;width:{bar_width}%;
                                    height:18px;background:{color};opacity:0.25;border-radius:4px"></div>
                        <div style="position:absolute;left:{mean}%;top:0;width:3px;height:18px;
                                    background:{color};border-radius:2px"></div>
                      </div>
                      <div style="display:flex;justify-content:space-between;font-size:0.68rem;color:#aaa;margin-top:2px">
                        <span>P5: {p5:.0f}</span>
                        <span>Médiane: {dist['median']:.0f}</span>
                        <span>P95: {p95:.0f}</span>
                      </div>
                    </div>""", unsafe_allow_html=True)

                # Probabilité de transition
                trans_prob = phase_dist.risk_metrics.get("transition_probability", 0)
                st.markdown(f"""
                <div style="background:#f8f7f4;border-radius:8px;padding:12px 16px;margin-top:10px">
                  <div style="font-size:0.82rem"><b>Probabilité de transition de régime</b></div>
                  <div style="font-size:1.1rem;font-weight:600;color:{'#BA7517' if trans_prob > 0.3 else '#1D9E75'}">
                    {trans_prob*100:.0f}%</div>
                  <div style="font-size:0.72rem;color:#888;margin-top:4px">
                    % de scénarios MC proches des seuils de changement de phase</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Activer le mode automatique de détection macro pour le scoring probabiliste.")


    # ══════════════════════════════════════════
    # TAB V3 — STRESS TESTING (NOUVEAU)
    # ══════════════════════════════════════════
    with tab_objects[tab_idx]:
        tab_idx += 1
        st.markdown("##### 📈 Stress Testing — Analyse de scénarios")

        if stress_results:
            col_s1, col_s2 = st.columns([2, 1], gap="large")

            with col_s1:
                # Heatmap scénarios × phases
                scenario_names = list(stress_results.keys())
                phase_names = MACRO_PHASES
                z_data = []
                for sname in scenario_names:
                    row = [stress_results[sname].probabilities.get(ph, 0) * 100 for ph in phase_names]
                    z_data.append(row)

                fig_heat = go.Figure(data=go.Heatmap(
                    z=z_data,
                    x=phase_names,
                    y=scenario_names,
                    colorscale=[
                        [0, "#f8f7f4"],
                        [0.25, "#E1F5EE"],
                        [0.5, "#E6F1FB"],
                        [0.75, "#FAEEDA"],
                        [1, "#FAECE7"],
                    ],
                    text=[[f"{v:.0f}%" for v in row] for row in z_data],
                    texttemplate="%{text}",
                    textfont=dict(size=11),
                    hoverongaps=False,
                    colorbar=dict(title="P(%)", ticksuffix="%"),
                ))
                fig_heat.update_layout(
                    height=350,
                    margin=dict(l=0, r=0, t=20, b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(autorange="reversed"),
                )
                st.plotly_chart(fig_heat, use_container_width=True)

            with col_s2:
                st.markdown("**Phase dominante par scénario**")
                for sname, sdist in stress_results.items():
                    dom = sdist.dominant_phase
                    conf = sdist.confidence
                    icon = "🟢" if dom in ["Recovery", "Expansion"] else ("🟡" if dom == "Hypersupply" else "🔴")
                    st.markdown(f"""
                    <div style="padding:8px 12px;margin-bottom:6px;background:#fff;
                                border:1px solid #e8e6e0;border-radius:8px;
                                display:flex;justify-content:space-between;align-items:center">
                      <div>
                        <div style="font-size:0.82rem;font-weight:500">{icon} {sname}</div>
                      </div>
                      <div style="text-align:right">
                        <div style="font-size:0.82rem;font-weight:600;color:{MACRO_COLORS[dom]}">{dom}</div>
                        <div style="font-size:0.68rem;color:#888">P={conf:.0f}%</div>
                      </div>
                    </div>""", unsafe_allow_html=True)

                # Delta vs base case
                base_dom = stress_results.get("Base case", list(stress_results.values())[0]).dominant_phase
                shifts = sum(1 for s in stress_results.values() if s.dominant_phase != base_dom)
                st.markdown(f"""
                <div style="background:#f8f7f4;border-radius:8px;padding:12px 16px;margin-top:12px">
                  <div style="font-size:0.82rem"><b>Robustesse de la prescription</b></div>
                  <div style="font-size:0.78rem;color:#555;margin-top:4px">
                    {shifts}/{len(stress_results)-1} scénarios changent la phase dominante</div>
                  <div style="font-size:0.78rem;color:{'#1D9E75' if shifts <= 1 else '#A32D2D'};
                              font-weight:600;margin-top:2px">
                    {'✅ Prescription robuste' if shifts <= 1 else '⚠️ Prescription sensible aux chocs'}
                  </div>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Activer le mode automatique et probabiliste.")


    # ══════════════════════════════════════════
    # TAB V3 — RISK PROFILE (NOUVEAU)
    # ══════════════════════════════════════════
    with tab_objects[tab_idx]:
        tab_idx += 1
        st.markdown("##### 🛡️ Risk Profile — Strategic Risk Index")

        if risk_profile:
            col_r1, col_r2 = st.columns([1, 1], gap="large")

            with col_r1:
                # SRI Gauge
                sri = risk_profile.strategic_risk_index
                sri_color = "#1D9E75" if sri < 35 else ("#BA7517" if sri < 65 else "#A32D2D")

                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=sri,
                    title={"text": "Strategic Risk Index", "font": {"size": 14}},
                    number={"suffix": "/100", "font": {"size": 28}},
                    gauge={
                        "axis": {"range": [0, 100], "tickwidth": 1},
                        "bar": {"color": sri_color},
                        "steps": [
                            {"range": [0, 35], "color": "rgba(29,158,117,0.15)"},
                            {"range": [35, 65], "color": "rgba(186,117,23,0.15)"},
                            {"range": [65, 100], "color": "rgba(163,45,45,0.15)"},
                        ],
                        "threshold": {
                            "line": {"color": "#1a1a1a", "width": 3},
                            "thickness": 0.8,
                            "value": sri,
                        },
                    },
                ))
                fig_gauge.update_layout(
                    height=250, margin=dict(l=30, r=30, t=50, b=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_gauge, use_container_width=True)

                # Interprétation
                if sri < 35:
                    interp = "Profil de risque favorable. La combinaison cycle/asset/finance permet une exécution stratégique sereine."
                    interp_icon = "🟢"
                elif sri < 65:
                    interp = "Profil de risque modéré. Certains facteurs nécessitent une surveillance active et des plans de contingence."
                    interp_icon = "🟡"
                else:
                    interp = "Profil de risque élevé. Plusieurs dimensions sous tension — exécution rapide recommandée avec couverture des risques."
                    interp_icon = "🔴"

                st.markdown(f"""
                <div style="background:#f8f7f4;border-radius:8px;padding:12px 16px">
                  <div style="font-size:0.85rem">{interp_icon} {interp}</div>
                </div>""", unsafe_allow_html=True)

            with col_r2:
                st.markdown("**Décomposition du risque**")

                risk_components = [
                    ("VaR 95%", format_eur(risk_profile.var_95),
                     "Perte maximale à 95% de confiance", "#A32D2D"),
                    ("CVaR 95% (Expected Shortfall)", format_eur(risk_profile.cvar_95),
                     "Perte moyenne dans les 5% pires scénarios", "#A32D2D"),
                    ("Tail Risk Score", f"{risk_profile.tail_risk_score:.0f}%",
                     "Probabilité de coût > 2× médiane", "#BA7517"),
                    ("Stabilité prescription", f"{risk_profile.stability_score:.0f}%",
                     "Robustesse de la recommandation", "#1D9E75" if risk_profile.stability_score > 60 else "#BA7517"),
                    ("P(transition régime)", f"{risk_profile.regime_transition_prob:.0f}%",
                     "Probabilité de changement de phase 12 mois", "#185FA5"),
                ]

                for label, value, desc, color in risk_components:
                    st.markdown(f"""
                    <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;
                                margin-bottom:6px;background:#fff;border:1px solid #e8e6e0;
                                border-radius:8px">
                      <div style="flex:1">
                        <div style="font-size:0.82rem;font-weight:500">{label}</div>
                        <div style="font-size:0.72rem;color:#888">{desc}</div>
                      </div>
                      <div style="font-size:1rem;font-weight:600;color:{color}">{value}</div>
                    </div>""", unsafe_allow_html=True)

                # Distribution des coûts
                if timing_dist:
                    st.markdown("**Distribution des coûts de décalage**")
                    fig_hist = go.Figure()
                    fig_hist.add_trace(go.Histogram(
                        x=timing_dist.cost_samples / 1000,
                        nbinsx=50,
                        marker_color="rgba(163,45,45,0.5)",
                        name="Distribution MC",
                    ))
                    fig_hist.add_vline(x=timing_dist.median_cost / 1000,
                                       line_dash="solid", line_color="#1a1a1a",
                                       annotation_text=f"Médiane: {format_eur(timing_dist.median_cost)}",
                                       annotation_position="top right",
                                       annotation_font_size=10)
                    fig_hist.add_vline(x=timing_dist.p95_cost / 1000,
                                       line_dash="dash", line_color="#A32D2D",
                                       annotation_text=f"P95: {format_eur(timing_dist.p95_cost)}",
                                       annotation_position="top right",
                                       annotation_font_size=10)
                    fig_hist.update_layout(
                        xaxis=dict(title="Coût total (k€)"),
                        yaxis=dict(title="Fréquence"),
                        height=250, margin=dict(l=0, r=0, t=20, b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        showlegend=False,
                    )
                    st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("Activer le mode probabiliste pour le Risk Profile.")


# ══════════════════════════════════════════
# TAB — SIMULATEUR TIMING (enrichi V3)
# ══════════════════════════════════════════
with tab_objects[tab_idx]:
    tab_idx += 1
    st.markdown("##### Simulateur de timing — coût du décalage")

    col_t1, col_t2 = st.columns([1, 1], gap="large")

    with col_t1:
        fig_sim = go.Figure()

        # Courbe déterministe
        tots_det = []
        for d in range(1, 6):
            _, _, _, tot_, _ = simulate_timing(
                noi, valeur_marche, asset_phase_idx, d,
                taux_declin_noi, taux_surcoute_capex, capex_estime)
            tots_det.append(tot_ / 1000)

        fig_sim.add_trace(go.Scatter(
            x=list(range(1, 6)), y=tots_det,
            mode="lines+markers",
            line=dict(color="#A32D2D", width=2),
            marker=dict(size=8),
            name="Déterministe",
        ))

        # Intervalle de confiance MC (si dispo)
        if probabilistic_mode and mode_macro != "✏️ Manuel (override AM)":
            p5s, p95s, medians = [], [], []
            for d in range(1, 6):
                td = prob_engine.simulate_timing_distribution(
                    noi, valeur_marche, asset_phase_idx, d,
                    taux_declin_noi, taux_surcoute_capex, capex_estime)
                p5s.append(td.p5_cost / 1000)
                p95s.append(td.p95_cost / 1000)
                medians.append(td.median_cost / 1000)

            fig_sim.add_trace(go.Scatter(
                x=list(range(1, 6)) + list(range(5, 0, -1)),
                y=p95s + p5s[::-1],
                fill="toself",
                fillcolor="rgba(163,45,45,0.12)",
                line=dict(color="rgba(0,0,0,0)"),
                name="IC 90% (Monte Carlo)",
                hoverinfo="skip",
            ))
            fig_sim.add_trace(go.Scatter(
                x=list(range(1, 6)), y=medians,
                mode="lines",
                line=dict(color="#A32D2D", width=1, dash="dot"),
                name="Médiane MC",
            ))

        fig_sim.add_vline(x=decalage_ans, line_dash="dash", line_color="#185FA5",
                          annotation_text=f"Scénario sélectionné ({decalage_ans}a)")
        fig_sim.update_layout(
            xaxis=dict(title="Décalage (années)", dtick=1),
            yaxis=dict(title="Coût total (k€)"),
            height=320, margin=dict(l=0, r=0, t=20, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_sim, use_container_width=True)

    with col_t2:
        st.markdown(f"**Décomposition — scénario {decalage_ans}a**")

        components = [
            ("NOI perdu (actualisé 7%)", noi_perdu, "#185FA5"),
            ("Surcoût CapEx", surcoute_capex, "#BA7517"),
            ("Décote valeur à risque", decote_valeur, "#A32D2D"),
        ]
        for label, val, col in components:
            pct = val / total_cost * 100 if total_cost > 0 else 0
            st.markdown(f"""
            <div style="margin-bottom:10px">
              <div style="display:flex;justify-content:space-between;font-size:0.82rem;margin-bottom:4px">
                <span>{label}</span>
                <span style="font-weight:600;color:{col}">{format_eur(val)}</span>
              </div>
              <div style="background:#e8e6e0;border-radius:4px;height:6px">
                <div style="width:{pct:.0f}%;height:6px;background:{col};border-radius:4px"></div>
              </div>
            </div>""", unsafe_allow_html=True)

        cost_pct = total_cost / valeur_marche * 100 if valeur_marche > 0 else 0
        ci_text = ""
        if timing_dist:
            ci_text = (f"<div style='font-size:0.75rem;color:#888;margin-top:4px'>"
                       f"IC 90% : {format_eur(timing_dist.p5_cost)} – {format_eur(timing_dist.p95_cost)} · "
                       f"P(glissement Ph.4) = {timing_dist.glissement_prob*100:.0f}%</div>")

        st.markdown(f"""
        <div style="background:#FAECE7;border:1px solid #D85A30;border-radius:8px;
                    padding:14px 18px;margin-top:12px">
          <div style="font-size:0.72rem;color:#888;text-transform:uppercase">Coût total estimé</div>
          <div style="font-size:1.4rem;font-weight:600;color:#A32D2D">−{format_eur(total_cost)}</div>
          <div style="font-size:0.75rem;color:#888;margin-top:4px">
            Soit {cost_pct:.1f}% de la valeur marché</div>
          {ci_text}
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════
# TAB — RAPPORT EXÉCUTIF (enrichi V3)
# ══════════════════════════════════════════
with tab_objects[tab_idx]:
    tab_idx += 1
    st.markdown("##### Rapport exécutif — synthèse comité d'investissement")

    roa_interp = "au-dessus" if roa_reel >= roa_benchmark else "en-dessous"
    micro_interp = "renforce" if micro_score >= 0.5 else ("atténue" if micro_score <= -0.5 else "confirme")

    # Section probabiliste dans le rapport
    prob_section = ""
    if phase_dist:
        ranks = phase_dist.phase_rank()
        prob_section = f"""
        <div style="margin-bottom:14px">
          <b>Analyse probabiliste ({n_sims:,} simulations) :</b>
          Phase dominante <b>{ranks[0][0]}</b> avec P={ranks[0][1]*100:.0f}%.
          {'Phase alternative <b>' + ranks[1][0] + '</b> à P=' + f"{ranks[1][1]*100:.0f}%" + '.' if ranks[1][1] > 0.15 else ''}
          Entropie de Shannon : {phase_dist.entropy:.2f}/2.00
          ({'forte certitude' if phase_dist.entropy < 0.8 else 'incertitude modérée' if phase_dist.entropy < 1.4 else 'forte incertitude'}).
        </div>"""

    risk_section = ""
    if risk_profile:
        risk_section = f"""
        <div style="margin-bottom:14px">
          <b>Risk Profile :</b> Strategic Risk Index = <b>{risk_profile.strategic_risk_index:.0f}/100</b>.
          VaR 95% = {format_eur(risk_profile.var_95)}, CVaR = {format_eur(risk_profile.cvar_95)}.
          Stabilité de la prescription : {risk_profile.stability_score:.0f}%.
          Probabilité de transition de régime : {risk_profile.regime_transition_prob:.0f}%.
        </div>"""

    stress_section = ""
    if stress_results:
        base_dom = stress_results.get("Base case", list(stress_results.values())[0]).dominant_phase
        shifts = sum(1 for s in stress_results.values() if s.dominant_phase != base_dom)
        stress_section = f"""
        <div style="margin-bottom:14px">
          <b>Stress Testing :</b> {shifts}/{len(stress_results)-1} scénarios modifient la phase dominante.
          {'Prescription robuste aux chocs.' if shifts <= 1 else 'Prescription sensible — plan de contingence recommandé.'}
        </div>"""

    timing_ci = ""
    if timing_dist:
        timing_ci = f" (IC 90% : {format_eur(timing_dist.p5_cost)} – {format_eur(timing_dist.p95_cost)})"

    st.markdown(f"""
    <div style="background:#fff;border:1px solid #e8e6e0;border-radius:12px;
                padding:24px 28px;line-height:1.8;font-size:0.9rem">

    <div style="font-size:1.1rem;font-weight:600;margin-bottom:16px">
      {nom_hotel} · Analyse stratégique cycle · {segment} · {today}</div>

    <div style="margin-bottom:14px">
      <b>Positionnement cycle :</b> Phase macro <b>{macro_phase}</b>
      ({macro_dir}, {macro_vel}) · <b>{asset_phase}</b> ({asset_dir}, {asset_vel}).
      Score micro {micro_score:+.1f}/2.0 ({micro_interp} la prescription).
    </div>

    {prob_section}

    <div style="margin-bottom:14px">
      <b>Prescription :</b>
      <span style="background:{sig_cfg['bg']};color:{sig_cfg['color']};
                   padding:2px 8px;border-radius:10px;font-weight:600">
        {sig_cfg['label']}</span>
      — {prescription['titre']}. {prescription['detail']}
    </div>

    <div style="margin-bottom:14px">
      <b>ROA réel :</b> {roa_reel*100:.2f}% ({roa_interp} du benchmark {roa_benchmark*100:.1f}%).
      ROA book {roa_book*100:.2f}%.
      {'Option Analysis déclenchée.' if trigger_option else 'Valeur de continuation favorable.'}
    </div>

    <div style="margin-bottom:14px">
      <b>Fenêtre de décision :</b> ~{window_mois} mois.
      {'Fenêtre large.' if window_mois >= 18 else
       ('Fenêtre courte — décision sous 6 mois.' if window_mois >= 10 else
        'Fenêtre fermée — décision immédiate.')}
    </div>

    <div style="margin-bottom:14px">
      <b>Coût d'inaction :</b> Décalage {decalage_ans}a = 
      <b style="color:#A32D2D">−{format_eur(total_cost)}</b>
      ({cost_pct:.1f}% de la valeur marché){timing_ci}.
      {'Glissement Phase 4 probable.' if glissement else ''}
    </div>

    {risk_section}
    {stress_section}

    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("**Initiatives prioritaires**")
    for i, (init_titre, init_impact, init_prio) in enumerate(prescription["initiatives"], 1):
        prio_color, _ = INIT_COLORS[init_prio]
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;padding:9px 14px;
                    margin-bottom:6px;background:#fff;border:1px solid #e8e6e0;
                    border-radius:8px">
          <span style="color:#888;font-size:0.75rem;min-width:20px">{i}.</span>
          <span style="flex:1;font-size:0.85rem">{init_titre}</span>
          <span style="font-size:0.72rem;color:#888;background:#f1efe8;
                       padding:2px 8px;border-radius:10px">Impact {init_impact}</span>
          <span style="font-size:0.72rem;color:{prio_color};font-weight:600">{init_prio}</span>
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="font-size:0.72rem;color:#aaa;margin-top:20px;text-align:center">
    Strategic Asset Clock™ V3 · REIV Hospitality · Scoring probabiliste · {n_sims:,} simulations MC
    <br>Outil de pilotage stratégique Asset Manager — Ne constitue pas un conseil en investissement
    </div>""", unsafe_allow_html=True)
