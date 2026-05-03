"""
Strategic Asset Clock™ V3 — Moteur de scoring déterministe
+ pont vers le moteur probabiliste
"""

import math
from datetime import datetime
from typing import Dict, Tuple, List, Optional

from config import (
    MACRO_PHASES, ASSET_PHASES, DISCOUNT_RATE, PHASE_PENALTY,
    DECOTE_PCT_BY_PHASE, ROA_BENCHMARKS, BASE_OPTION_SCORES,
)
from utils import present_value, normalize_1_5, clamp


# ─────────────────────────────────────────
# KPI SCORE — sigmoïde continue
# ─────────────────────────────────────────

def _kpi_score(value: float, green_min, green_max) -> float:
    """Score continu 0-100 selon seuils vert/rouge (sigmoïde)."""
    lo, hi = green_min, green_max
    v = value

    def _sig(d: float) -> float:
        if d <= 0:   return 100.0
        if d >= 2.0: return 0.0
        x = d * 3 - 3
        return clamp(100.0 / (1 + math.exp(x)), 0.0, 100.0)

    if lo is not None and hi is not None:
        center = (lo + hi) / 2
        half = (hi - lo) / 2
        margin = half * 0.6
        if lo <= v <= hi:
            dist = abs(v - center) / half if half > 0 else 0
            return 85.0 + 15.0 * (1 - dist)
        dist_pct = (abs(v - center) - half) / (margin if margin > 0 else 1)
        return _sig(dist_pct)

    if lo is not None:
        if v >= lo:
            overshoot = (v - lo) / (lo * 0.3) if lo > 0 else 0
            return max(85.0, 100.0 - overshoot * 5)
        dist_pct = (lo - v) / (lo * 0.35 if lo > 0 else 1)
        return _sig(dist_pct)

    if hi is not None:
        if v <= hi:
            undershoot = (hi - v) / (hi * 0.3) if hi > 0 else 0
            return max(85.0, 100.0 - undershoot * 5)
        dist_pct = (v - hi) / (hi * 0.45 if hi > 0 else 1)
        return _sig(dist_pct)

    return 50.0


# ─────────────────────────────────────────
# CYCLE MARCHÉ — déterministe
# ─────────────────────────────────────────

def compute_market_cycle(
    gdp_growth, tourism_growth, cci, bci, air_traffic,
    supply_growth, local_pipeline_pct, absorption_months, revpar_growth_3y,
    interest_rate, sovereign_spread_bps, vix, credit_growth,
    market_type="developed",
) -> dict:
    """Calcul déterministe de la phase du cycle marché hôtelier."""
    dev = (market_type == "developed")

    s_gdp      = _kpi_score(gdp_growth,           2.0 if dev else 4.0, None)
    s_tourism  = _kpi_score(tourism_growth,        4.0 if dev else 6.0, None)
    s_cci      = _kpi_score(cci,                   100.0,               None)
    s_bci      = _kpi_score(bci,                   100.0,               None)
    s_air      = _kpi_score(air_traffic,           4.0 if dev else 6.0, None)
    s_supply   = _kpi_score(supply_growth,         None,                3.5)
    s_pipeline = _kpi_score(local_pipeline_pct,   None,                4.0)
    s_absorb   = _kpi_score(absorption_months,    None,                18.0)
    s_revpar3y = _kpi_score(revpar_growth_3y,      3.0,                 None)
    s_rate     = _kpi_score(interest_rate,         None,                4.5 if dev else 6.5)
    s_spread   = _kpi_score(sovereign_spread_bps,  None,                150.0 if dev else 350.0)
    s_vix      = _kpi_score(vix,                   None,                22.0)
    s_credit   = _kpi_score(credit_growth,         3.0,                 None)

    demand_score  = s_gdp*0.30 + s_tourism*0.25 + s_cci*0.15 + s_bci*0.15 + s_air*0.15
    supply_score  = s_supply*0.30 + s_pipeline*0.30 + s_absorb*0.20 + s_revpar3y*0.20
    finance_score = s_rate*0.35 + s_spread*0.25 + s_vix*0.20 + s_credit*0.20

    d_strong = demand_score >= 68
    d_weak   = demand_score <= 38
    s_tight  = supply_score >= 65
    s_loose  = supply_score <= 35

    if d_strong and s_tight:
        phase = "Expansion"
        confidence = min(100, (demand_score + supply_score) / 2)
    elif d_strong and s_loose:
        phase = "Hypersupply"
        confidence = min(100, (demand_score + (100 - supply_score)) / 2)
    elif d_weak and s_tight:
        phase = "Recovery"
        confidence = min(100, ((100 - demand_score) + supply_score) / 2)
    elif d_weak and s_loose:
        phase = "Recession"
        confidence = min(100, ((100 - demand_score) + (100 - supply_score)) / 2)
    else:
        d_pressure = demand_score - 53
        s_pressure = supply_score - 50
        combined   = d_pressure * 0.6 + s_pressure * 0.4
        fin_adj    = (finance_score - 65) * 0.15
        total      = combined + fin_adj
        if total > 12:    phase = "Expansion"
        elif total > 2:   phase = "Recovery"
        elif total > -10: phase = "Hypersupply"
        else:             phase = "Recession"
        confidence = clamp(100 - abs(total) * 1.2, 20, 70)

    # Override finance
    if finance_score < 30 and phase in ["Expansion", "Hypersupply"]:
        order = ["Recession", "Recovery", "Hypersupply", "Expansion"]
        idx = order.index(phase)
        phase = order[max(0, idx - 1)]
        confidence = max(0, confidence - 15)
        finance_signal = "🔴 Frein financier fort — spread cap rate compressé"
    elif finance_score < 45 and phase == "Expansion":
        phase = "Hypersupply"
        confidence = max(0, confidence - 10)
        finance_signal = "🟡 Financement tendu — surveiller spread cap rate / dette"
    elif finance_score >= 80 and phase == "Recovery":
        phase = "Expansion"
        confidence = min(100, confidence + 10)
        finance_signal = "🟢 Financement porteur — fenêtre d'acquisition ouverte"
    else:
        if finance_score >= 65:   finance_signal = "🟢 Conditions financières favorables"
        elif finance_score >= 45: finance_signal = "🟡 Conditions financières neutres"
        else:                     finance_signal = "🔴 Conditions financières dégradées"

    signals = []
    if demand_score >= 75:   signals.append(("✅", "Demande forte",         f"Score {demand_score:.0f}/100"))
    elif demand_score >= 50: signals.append(("⚠️", "Demande modérée",      f"Score {demand_score:.0f}/100"))
    else:                    signals.append(("❌", "Demande faible",         f"Score {demand_score:.0f}/100"))
    if supply_score >= 70:   signals.append(("✅", "Offre maîtrisée",       f"Score {supply_score:.0f}/100"))
    elif supply_score >= 45: signals.append(("⚠️", "Tension offre modérée", f"Score {supply_score:.0f}/100"))
    else:                    signals.append(("❌", "Pression offre élevée",  f"Score {supply_score:.0f}/100"))

    return {
        "phase":          phase,
        "confidence":     round(confidence),
        "demand_score":   round(demand_score, 1),
        "supply_score":   round(supply_score, 1),
        "finance_score":  round(finance_score, 1),
        "finance_signal": finance_signal,
        "signals":        signals,
    }


# ─────────────────────────────────────────
# PHASE ASSET
# ─────────────────────────────────────────

def asset_phase_from_proxy(annee_reno: int, ratio_correctif: float,
                            gop_trend: str, score_technique: int) -> int:
    """Calcule la phase asset automatiquement."""
    age = datetime.now().year - annee_reno
    score = 0
    
    if age <= 3:    score += 0
    elif age <= 7:  score += 1
    elif age <= 12: score += 2
    else:           score += 3
    
    if ratio_correctif < 0.20:   score += 0
    elif ratio_correctif < 0.40: score += 1
    elif ratio_correctif < 0.60: score += 2
    else:                        score += 3
    
    gop_map = {"Hausse": 0, "Stable": 1, "Légère baisse": 2, "Forte baisse": 3}
    score += gop_map.get(gop_trend, 2)
    
    if score_technique >= 4:   score += 0
    elif score_technique >= 3: score += 1
    elif score_technique >= 2: score += 2
    else:                      score += 3

    avg = score / 4
    if avg < 0.75:   return 0
    elif avg < 1.75: return 1
    elif avg < 2.75: return 2
    return 3


# ─────────────────────────────────────────
# MICRO SCORE
# ─────────────────────────────────────────

def compute_micro_score(pipeline_ch: int, rgi: float,
                         demande_score: int, positionnement_score: int) -> float:
    """Score micro de −2 à +2."""
    s = 0.0

    if pipeline_ch == 0:       pipeline_raw =  2.0
    elif pipeline_ch < 100:    pipeline_raw =  1.0
    elif pipeline_ch < 300:    pipeline_raw =  0.0
    elif pipeline_ch < 500:    pipeline_raw = -1.0
    else:                      pipeline_raw = -2.0
    s += pipeline_raw * 0.40

    if rgi > 1.10:             rgi_raw =  2.0
    elif rgi > 1.02:           rgi_raw =  1.0
    elif rgi > 0.98:           rgi_raw =  0.0
    elif rgi > 0.90:           rgi_raw = -1.0
    else:                      rgi_raw = -2.0
    s += rgi_raw * 0.30

    s += normalize_1_5(demande_score) * 0.15
    s += normalize_1_5(positionnement_score) * 0.15

    return clamp(round(s, 1), -2.0, 2.0)


# ─────────────────────────────────────────
# ROA
# ─────────────────────────────────────────

def compute_roa_reel(noi: float, valeur_marche: float,
                      valeur_book: float, segment: str) -> tuple:
    roa_reel = noi / valeur_marche if valeur_marche > 0 else 0
    roa_book = noi / valeur_book if valeur_book > 0 else 0
    benchmark = ROA_BENCHMARKS.get(segment, 0.055)
    gap = roa_reel - benchmark
    trigger = roa_reel < benchmark
    return roa_reel, roa_book, benchmark, gap, trigger


# ─────────────────────────────────────────
# FENÊTRE DE DÉCISION
# ─────────────────────────────────────────

def velocity_months(v: str) -> int:
    return {"Lente": 30, "Normale": 20, "Rapide": 10}[v]


def compute_window(macro_dir: str, macro_vel: str,
                    asset_dir: str, asset_vel: str,
                    micro_score: float, asset_phase_idx: int = 1) -> int:
    """Fenêtre de validité de la prescription en mois."""
    base_macro = velocity_months(macro_vel)
    base_asset = velocity_months(asset_vel)

    if macro_dir == "Stable →":
        base_macro = int(base_macro * 1.3)
    if asset_dir == "Stable →" and asset_phase_idx <= 1:
        base_asset = int(base_asset * 1.3)
    elif asset_dir == "Stable →" and asset_phase_idx >= 2:
        base_asset = int(base_asset * 0.9)

    penalty = PHASE_PENALTY.get(asset_phase_idx, 1.0)
    base_asset = int(base_asset * penalty)

    window = min(base_macro, base_asset)
    window = int(window * (1 + micro_score * 0.10))
    return clamp(window, 3, 36)


# ─────────────────────────────────────────
# SIMULATEUR TIMING — déterministe
# ─────────────────────────────────────────

def simulate_timing(noi: float, valeur_marche: float, asset_phase_idx: int,
                     decalage_ans: int, taux_declin_noi: float,
                     taux_surcoute_capex: float, capex_estime: float
                     ) -> Tuple[float, float, float, float, bool]:
    """Simulation déterministe du coût du décalage."""
    discount = DISCOUNT_RATE

    noi_perdu = 0.0
    for y in range(1, decalage_ans + 1):
        noi_theorique = noi
        noi_degrade = noi * ((1 - taux_declin_noi) ** y)
        perte = noi_theorique - noi_degrade
        noi_perdu += present_value(perte, y, discount)

    if asset_phase_idx == 3:
        glissement = True
    elif asset_phase_idx == 2:
        glissement = decalage_ans >= 2
    elif asset_phase_idx == 1:
        glissement = decalage_ans >= 4
    else:
        glissement = False

    surcoute_capex = capex_estime * taux_surcoute_capex if glissement else 0
    
    decote_pct = DECOTE_PCT_BY_PHASE.get(asset_phase_idx, 0.05)
    decote_valeur = 0.0
    if glissement:
        for y in range(1, decalage_ans + 1):
            decote_valeur += present_value(valeur_marche * decote_pct, y, discount)

    total = noi_perdu + surcoute_capex + decote_valeur
    return noi_perdu, surcoute_capex, decote_valeur, total, glissement


# ─────────────────────────────────────────
# OPTIONS ANALYSIS
# ─────────────────────────────────────────

def compute_option_scores(signal: str, gap_benchmark: float) -> Dict[str, int]:
    """Scoring des options stratégiques."""
    scores = dict(BASE_OPTION_SCORES.get(signal, BASE_OPTION_SCORES["attente"]))
    
    severity = clamp(gap_benchmark / 0.02, -2, 2)
    
    if severity < -1:
        scores["Cession"] = min(5, scores.get("Cession", 2) + 2)
        scores["Changement d'usage"] = min(5, scores.get("Changement d'usage", 2) + 1)
        scores["Refinancement"] = max(1, scores.get("Refinancement", 3) - 1)
    elif severity < -0.25:
        scores["Cession"] = min(5, scores.get("Cession", 2) + 1)
        scores["Repositionnement"] = min(5, scores.get("Repositionnement", 2) + 1)
    elif severity > 0.75:
        scores["Refinancement"] = min(5, scores.get("Refinancement", 3) + 1)
        scores["Cession"] = max(1, scores.get("Cession", 2) - 1)
        scores["Changement d'usage"] = max(1, scores.get("Changement d'usage", 2) - 1)
    
    return scores
