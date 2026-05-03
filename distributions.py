"""
Strategic Asset Clock™ V3 — Distributions probabilistes & Monte Carlo
═══════════════════════════════════════════════════════════════════════

Approche bayésienne simplifiée :
1. Chaque variable d'entrée est modélisée comme une distribution (pas un point)
2. Monte Carlo propage l'incertitude à travers le moteur de scoring
3. Les sorties sont des distributions de probabilité par phase
4. Le scoring final donne P(phase) et intervalles de confiance

Fondements méthodologiques :
- Crystal Ball / @RISK methodology pour real estate
- Bayesian updating adapté de Geltner & Miller (Commercial Real Estate)
- Tail risk analysis inspiré de Taleb / stress testing bancaire
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from config import PRIOR_DISTRIBUTIONS, MACRO_PHASES


# ─────────────────────────────────────────
# DATACLASSES
# ─────────────────────────────────────────

@dataclass
class DistributionSpec:
    """Spécification d'une distribution pour une variable."""
    name: str
    central: float           # Valeur centrale (input utilisateur)
    dist_type: str = "normal"  # normal, triangular, uniform, lognormal
    sigma_pct: float = 0.20    # Incertitude relative
    low: Optional[float] = None
    high: Optional[float] = None
    
    @property
    def sigma(self) -> float:
        return abs(self.central * self.sigma_pct) if self.central != 0 else self.sigma_pct
    
    def sample(self, n: int, rng: np.random.Generator) -> np.ndarray:
        """Génère n échantillons de la distribution."""
        if self.dist_type == "normal":
            samples = rng.normal(self.central, self.sigma, n)
        elif self.dist_type == "lognormal":
            # Log-normal pour variables strictement positives
            mu = np.log(max(self.central, 1e-6))
            sig = self.sigma_pct
            samples = rng.lognormal(mu, sig, n)
        elif self.dist_type == "triangular":
            lo = self.central * (1 - self.sigma_pct * 2)
            hi = self.central * (1 + self.sigma_pct * 2)
            if self.low is not None:
                lo = max(self.low, lo)
            if self.high is not None:
                hi = min(self.high, hi)
            if lo >= hi:
                hi = lo + abs(self.central) * 0.01 + 0.01
            mode = np.clip(self.central, lo, hi)
            samples = rng.triangular(lo, mode, hi, n)
        elif self.dist_type == "uniform":
            lo = self.central * (1 - self.sigma_pct)
            hi = self.central * (1 + self.sigma_pct)
            samples = rng.uniform(lo, hi, n)
        else:
            samples = np.full(n, self.central)
        
        # Bornes physiques
        if self.low is not None:
            samples = np.maximum(samples, self.low)
        if self.high is not None:
            samples = np.minimum(samples, self.high)
        
        return samples


@dataclass
class PhaseDistribution:
    """Résultat probabiliste : distribution de probabilité sur les 4 phases."""
    probabilities: Dict[str, float]     # P(phase) pour chaque phase
    confidence: float                    # Confiance dans la phase dominante
    dominant_phase: str                  # Phase la plus probable
    entropy: float                       # Entropie de Shannon (0=certain, 2=uniforme)
    demand_dist: Dict[str, float]       # Statistiques score demande
    supply_dist: Dict[str, float]       # Statistiques score offre
    finance_dist: Dict[str, float]      # Statistiques score financement
    risk_metrics: Dict[str, float]      # VaR, CVaR, etc.

    def phase_rank(self) -> List[Tuple[str, float]]:
        """Phases classées par probabilité décroissante."""
        return sorted(self.probabilities.items(), key=lambda x: -x[1])


@dataclass
class TimingDistribution:
    """Résultat probabiliste du simulateur de timing."""
    mean_cost: float
    median_cost: float
    p5_cost: float          # 5e percentile (best case)
    p25_cost: float
    p75_cost: float
    p95_cost: float         # 95e percentile (worst case)
    glissement_prob: float  # Probabilité de glissement en phase 4
    cost_samples: np.ndarray  # Distribution complète


@dataclass 
class RiskProfile:
    """Profil de risque consolidé."""
    strategic_risk_index: float   # 0-100
    var_95: float                 # Value at Risk 95%
    cvar_95: float                # Conditional VaR (Expected Shortfall)
    tail_risk_score: float        # Score de risque de queue (0-100)
    stability_score: float        # Stabilité de la prescription (0-100)
    regime_transition_prob: float # Probabilité de changement de phase dans 12 mois


# ─────────────────────────────────────────
# MOTEUR MONTE CARLO
# ─────────────────────────────────────────

class ProbabilisticEngine:
    """
    Moteur de scoring probabiliste.
    
    Workflow :
    1. Construire les distributions d'entrée à partir des valeurs utilisateur
    2. Tirer N échantillons Monte Carlo
    3. Pour chaque échantillon, calculer les scores et la phase
    4. Agréger en distribution de probabilité
    
    Paramètres :
        n_simulations: nombre de tirages MC (défaut 10000)
        seed: graine aléatoire pour reproductibilité
        confidence_level: niveau de confiance pour intervalles (défaut 0.90)
    """
    
    def __init__(self, n_simulations: int = 10_000, seed: int = 42,
                 confidence_level: float = 0.90):
        self.n_sims = n_simulations
        self.rng = np.random.default_rng(seed)
        self.conf_level = confidence_level
        self._alpha = (1 - confidence_level) / 2
    
    # ─── Construction des distributions ───
    
    def build_macro_distributions(self, inputs: Dict[str, float]) -> Dict[str, DistributionSpec]:
        """
        Construit les distributions pour chaque variable macro
        à partir des valeurs centrales saisies par l'utilisateur.
        """
        mapping = {
            "gdp_growth": "gdp_growth",
            "tourism_growth": "tourism_growth",
            "cci": "cci",
            "bci": "bci",
            "air_traffic": "air_traffic",
            "supply_growth": "supply_growth",
            "pipeline_pct": "pipeline_pct",
            "absorption_months": "absorption_months",
            "revpar_growth_3y": "revpar_growth_3y",
            "interest_rate": "interest_rate",
            "spread_bps": "spread_bps",
            "vix": "vix",
            "credit_growth": "credit_growth",
        }
        
        distributions = {}
        for key, prior_key in mapping.items():
            prior = PRIOR_DISTRIBUTIONS.get(prior_key, {})
            distributions[key] = DistributionSpec(
                name=key,
                central=inputs[key],
                dist_type=prior.get("type", "normal"),
                sigma_pct=prior.get("sigma_pct", 0.20),
                low=prior.get("min"),
                high=prior.get("max"),
            )
        return distributions
    
    def build_financial_distributions(self, noi: float, valeur_marche: float,
                                       taux_declin: float, capex: float
                                       ) -> Dict[str, DistributionSpec]:
        """Distributions pour les variables financières."""
        return {
            "noi": DistributionSpec(
                "noi", noi, "lognormal", 
                PRIOR_DISTRIBUTIONS["noi"]["sigma_pct"],
                low=0,
            ),
            "valeur_marche": DistributionSpec(
                "valeur_marche", valeur_marche, "lognormal",
                PRIOR_DISTRIBUTIONS["valeur_marche"]["sigma_pct"],
                low=0,
            ),
            "taux_declin_noi": DistributionSpec(
                "taux_declin_noi", taux_declin, "triangular",
                PRIOR_DISTRIBUTIONS["taux_declin_noi"]["sigma_pct"],
                low=0.0, high=0.25,
            ),
            "capex_estime": DistributionSpec(
                "capex_estime", capex, "triangular",
                PRIOR_DISTRIBUTIONS["capex_estime"]["sigma_pct"],
                low=0,
            ),
        }
    
    # ─── Scoring unitaire (vectorisé) ───
    
    @staticmethod
    def _kpi_score_vec(values: np.ndarray, green_min, green_max) -> np.ndarray:
        """Version vectorisée de _kpi_score pour Monte Carlo."""
        scores = np.full_like(values, 50.0)
        lo, hi = green_min, green_max
        
        def _sig_vec(d: np.ndarray) -> np.ndarray:
            result = np.where(d <= 0, 100.0, 0.0)
            mask = (d > 0) & (d < 2.0)
            x = d[mask] * 3 - 3
            result[mask] = np.clip(100.0 / (1 + np.exp(x)), 0.0, 100.0)
            return result
        
        if lo is not None and hi is not None:
            center = (lo + hi) / 2
            half = (hi - lo) / 2
            margin = half * 0.6
            
            in_range = (values >= lo) & (values <= hi)
            dist_in = np.abs(values - center) / half if half > 0 else np.zeros_like(values)
            scores[in_range] = 85.0 + 15.0 * (1 - dist_in[in_range])
            
            out_range = ~in_range
            dist_out = (np.abs(values[out_range] - center) - half) / (margin if margin > 0 else 1)
            scores[out_range] = _sig_vec(dist_out)
            
        elif lo is not None:
            above = values >= lo
            overshoot = (values[above] - lo) / (lo * 0.3) if lo > 0 else np.zeros(above.sum())
            scores[above] = np.maximum(85.0, 100.0 - overshoot * 5)
            
            below = ~above
            dist_pct = (lo - values[below]) / (lo * 0.35 if lo > 0 else 1)
            scores[below] = _sig_vec(dist_pct)
            
        elif hi is not None:
            below = values <= hi
            undershoot = (hi - values[below]) / (hi * 0.3) if hi > 0 else np.zeros(below.sum())
            scores[below] = np.maximum(85.0, 100.0 - undershoot * 5)
            
            above = ~below
            dist_pct = (values[above] - hi) / (hi * 0.45 if hi > 0 else 1)
            scores[above] = _sig_vec(dist_pct)
        
        return scores
    
    # ─── Phase classification vectorisée ───
    
    def _classify_phases(self, demand_scores: np.ndarray,
                          supply_scores: np.ndarray,
                          finance_scores: np.ndarray,
                          dev: bool = True) -> np.ndarray:
        """
        Classification vectorisée des phases.
        Retourne un array d'indices de phase (0=Recovery, 1=Expansion, etc.)
        """
        n = len(demand_scores)
        phases = np.full(n, -1, dtype=int)
        confidences = np.zeros(n)
        
        d_strong = demand_scores >= 68
        d_weak = demand_scores <= 38
        s_tight = supply_scores >= 65
        s_loose = supply_scores <= 35
        
        # Expansion : demand forte + supply tight
        mask = d_strong & s_tight
        phases[mask] = 1  # Expansion
        
        # Hypersupply : demand forte + supply loose
        mask = d_strong & s_loose
        phases[mask] = 2
        
        # Recovery : demand faible + supply tight
        mask = d_weak & s_tight
        phases[mask] = 0
        
        # Recession : demand faible + supply loose
        mask = d_weak & s_loose
        phases[mask] = 3
        
        # Zone grise
        grey = phases == -1
        if grey.any():
            d_p = demand_scores[grey] - 53
            s_p = supply_scores[grey] - 50
            combined = d_p * 0.6 + s_p * 0.4
            fin_adj = (finance_scores[grey] - 65) * 0.15
            total = combined + fin_adj
            
            grey_phases = np.where(total > 12, 1,      # Expansion
                         np.where(total > 2, 0,         # Recovery
                         np.where(total > -10, 2, 3)))   # Hypersupply / Recession
            phases[grey] = grey_phases
        
        # Override finance
        phase_order = np.array([3, 0, 2, 1])  # Recession, Recovery, Hypersupply, Expansion
        
        # Finance < 30 et phase expansion/hypersupply → rétrogradation
        fin_low = finance_scores < 30
        exp_or_hyp = (phases == 1) | (phases == 2)
        downgrade = fin_low & exp_or_hyp
        phases[downgrade & (phases == 1)] = 2   # Expansion → Hypersupply
        phases[downgrade & (phases == 2)] = 0   # Hypersupply → Recovery
        
        # Finance < 45 et Expansion → Hypersupply
        fin_med = (finance_scores < 45) & (finance_scores >= 30)
        phases[fin_med & (phases == 1)] = 2
        
        # Finance >= 80 et Recovery → Expansion
        fin_high = finance_scores >= 80
        phases[fin_high & (phases == 0)] = 1
        
        return phases
    
    # ─── Monte Carlo principal — cycle marché ───
    
    def simulate_market_cycle(self, inputs: Dict[str, float],
                               market_type: str = "developed"
                               ) -> PhaseDistribution:
        """
        Simulation Monte Carlo du cycle marché.
        
        Pour chaque tirage :
        1. Échantillonner toutes les variables macro
        2. Calculer les scores demande/offre/financement
        3. Classifier la phase
        4. Agréger les fréquences → P(phase)
        """
        dev = (market_type == "developed")
        distributions = self.build_macro_distributions(inputs)
        
        # Échantillonnage
        samples = {k: d.sample(self.n_sims, self.rng) for k, d in distributions.items()}
        
        # Scores vectorisés — Demande
        s_gdp     = self._kpi_score_vec(samples["gdp_growth"], 2.0 if dev else 4.0, None)
        s_tourism = self._kpi_score_vec(samples["tourism_growth"], 4.0 if dev else 6.0, None)
        s_cci     = self._kpi_score_vec(samples["cci"], 100.0, None)
        s_bci     = self._kpi_score_vec(samples["bci"], 100.0, None)
        s_air     = self._kpi_score_vec(samples["air_traffic"], 4.0 if dev else 6.0, None)
        
        demand_scores = (s_gdp * 0.30 + s_tourism * 0.25 + s_cci * 0.15 +
                        s_bci * 0.15 + s_air * 0.15)
        
        # Scores vectorisés — Offre
        s_supply  = self._kpi_score_vec(samples["supply_growth"], None, 3.5)
        s_pipe    = self._kpi_score_vec(samples["pipeline_pct"], None, 4.0)
        s_absorb  = self._kpi_score_vec(samples["absorption_months"], None, 18.0)
        s_revpar  = self._kpi_score_vec(samples["revpar_growth_3y"], 3.0, None)
        
        supply_scores = (s_supply * 0.30 + s_pipe * 0.30 +
                        s_absorb * 0.20 + s_revpar * 0.20)
        
        # Scores vectorisés — Finance
        s_rate   = self._kpi_score_vec(samples["interest_rate"], None, 4.5 if dev else 6.5)
        s_spread = self._kpi_score_vec(samples["spread_bps"], None, 150.0 if dev else 350.0)
        s_vix    = self._kpi_score_vec(samples["vix"], None, 22.0)
        s_credit = self._kpi_score_vec(samples["credit_growth"], 3.0, None)
        
        finance_scores = (s_rate * 0.35 + s_spread * 0.25 +
                         s_vix * 0.20 + s_credit * 0.20)
        
        # Classification
        phase_indices = self._classify_phases(demand_scores, supply_scores, finance_scores, dev)
        
        # Fréquences → probabilités
        phase_map = {0: "Recovery", 1: "Expansion", 2: "Hypersupply", 3: "Recession"}
        probs = {}
        for idx, name in phase_map.items():
            probs[name] = float(np.mean(phase_indices == idx))
        
        # Phase dominante
        dominant = max(probs, key=probs.get)
        confidence = probs[dominant] * 100
        
        # Entropie de Shannon
        p_vals = np.array([max(p, 1e-10) for p in probs.values()])
        entropy = float(-np.sum(p_vals * np.log2(p_vals)))
        
        # Statistiques des scores
        def dist_stats(arr):
            return {
                "mean": float(np.mean(arr)),
                "median": float(np.median(arr)),
                "std": float(np.std(arr)),
                "p5": float(np.percentile(arr, 5)),
                "p25": float(np.percentile(arr, 25)),
                "p75": float(np.percentile(arr, 75)),
                "p95": float(np.percentile(arr, 95)),
            }
        
        # Risk metrics
        # VaR et CVaR sur le "score de santé" global
        health_scores = (demand_scores * 0.4 + supply_scores * 0.3 + finance_scores * 0.3)
        var_5 = float(np.percentile(health_scores, 5))
        cvar_5 = float(np.mean(health_scores[health_scores <= var_5]))
        
        # Probabilité de transition
        # = P(phase ≠ dominant) dans les scénarios proches du seuil
        border_mask = (demand_scores > 35) & (demand_scores < 42) | \
                      (demand_scores > 65) & (demand_scores < 72) | \
                      (supply_scores > 32) & (supply_scores < 38) | \
                      (supply_scores > 62) & (supply_scores < 68)
        transition_prob = float(np.mean(border_mask))
        
        risk_metrics = {
            "var_5": var_5,
            "cvar_5": cvar_5,
            "health_mean": float(np.mean(health_scores)),
            "health_std": float(np.std(health_scores)),
            "transition_probability": transition_prob,
        }
        
        return PhaseDistribution(
            probabilities=probs,
            confidence=round(confidence, 1),
            dominant_phase=dominant,
            entropy=round(entropy, 3),
            demand_dist=dist_stats(demand_scores),
            supply_dist=dist_stats(supply_scores),
            finance_dist=dist_stats(finance_scores),
            risk_metrics=risk_metrics,
        )
    
    # ─── Monte Carlo — Timing / Coût du décalage ───
    
    def simulate_timing_distribution(
        self, noi: float, valeur_marche: float, asset_phase_idx: int,
        decalage_ans: int, taux_declin: float, taux_surcoute: float,
        capex: float, discount_rate: float = 0.07
    ) -> TimingDistribution:
        """
        Monte Carlo sur le coût du décalage de décision.
        Propage l'incertitude sur NOI, valeur marché, déclin, coût CapEx.
        """
        from config import DECOTE_PCT_BY_PHASE
        
        fin_dists = self.build_financial_distributions(noi, valeur_marche, taux_declin, capex)
        
        noi_samples = fin_dists["noi"].sample(self.n_sims, self.rng)
        vm_samples = fin_dists["valeur_marche"].sample(self.n_sims, self.rng)
        declin_samples = fin_dists["taux_declin_noi"].sample(self.n_sims, self.rng)
        capex_samples = fin_dists["capex_estime"].sample(self.n_sims, self.rng)
        
        # NOI perdu (vectorisé)
        noi_perdu = np.zeros(self.n_sims)
        for y in range(1, decalage_ans + 1):
            noi_theo = noi_samples
            noi_deg = noi_samples * ((1 - declin_samples) ** y)
            perte = noi_theo - noi_deg
            noi_perdu += perte / ((1 + discount_rate) ** y)
        
        # Glissement
        if asset_phase_idx == 3:
            glissement = np.ones(self.n_sims, dtype=bool)
        elif asset_phase_idx == 2:
            glissement = np.full(self.n_sims, decalage_ans >= 2)
        elif asset_phase_idx == 1:
            glissement = np.full(self.n_sims, decalage_ans >= 4)
        else:
            glissement = np.zeros(self.n_sims, dtype=bool)
        
        # Ajout d'incertitude sur le glissement pour phases intermédiaires
        if asset_phase_idx in [1, 2]:
            noise = self.rng.uniform(0, 1, self.n_sims)
            base_prob = 0.7 if asset_phase_idx == 2 else 0.3
            glissement = noise < base_prob if (
                (asset_phase_idx == 2 and decalage_ans >= 1) or
                (asset_phase_idx == 1 and decalage_ans >= 3)
            ) else glissement
        
        # Surcoût CapEx
        surcoute = np.where(glissement, capex_samples * taux_surcoute, 0)
        
        # Décote valeur
        decote_pct = DECOTE_PCT_BY_PHASE.get(asset_phase_idx, 0.05)
        decote = np.zeros(self.n_sims)
        for y in range(1, decalage_ans + 1):
            annual_decote = vm_samples * decote_pct
            decote += np.where(glissement, annual_decote / ((1 + discount_rate) ** y), 0)
        
        total = noi_perdu + surcoute + decote
        
        return TimingDistribution(
            mean_cost=float(np.mean(total)),
            median_cost=float(np.median(total)),
            p5_cost=float(np.percentile(total, 5)),
            p25_cost=float(np.percentile(total, 25)),
            p75_cost=float(np.percentile(total, 75)),
            p95_cost=float(np.percentile(total, 95)),
            glissement_prob=float(np.mean(glissement)),
            cost_samples=total,
        )
    
    # ─── Strategic Risk Index ───
    
    def compute_risk_profile(
        self, phase_dist: PhaseDistribution,
        timing_dist: TimingDistribution,
        roa_reel: float, roa_benchmark: float,
        micro_score: float, asset_phase_idx: int,
        valeur_marche: float,
    ) -> RiskProfile:
        """
        Calcule le profil de risque consolidé.
        
        Strategic Risk Index (SRI) = combinaison pondérée de :
        - Incertitude macro (entropie, P(phase défavorable))
        - Risque financier (ROA gap, VaR)
        - Risque opérationnel (phase asset, micro)
        - Risque de timing (coût P95 / valeur)
        """
        # 1. Risque macro — poids 0.30
        # Entropie normalisée (0=certain, 1=uniforme sur 4 phases → log2(4)=2)
        entropy_norm = phase_dist.entropy / 2.0
        # P(recession) + P(hypersupply) = risque de phase défavorable
        p_adverse = phase_dist.probabilities.get("Recession", 0) + \
                    phase_dist.probabilities.get("Hypersupply", 0)
        macro_risk = (entropy_norm * 0.4 + p_adverse * 0.6) * 100
        
        # 2. Risque financier — poids 0.25
        roa_gap = roa_reel - roa_benchmark
        roa_risk = max(0, min(100, 50 - roa_gap * 100 * 20))
        finance_health = phase_dist.finance_dist["mean"]
        fin_risk = (roa_risk * 0.6 + (100 - finance_health) * 0.4)
        
        # 3. Risque opérationnel — poids 0.25
        phase_risk_map = {0: 10, 1: 30, 2: 60, 3: 90}
        asset_risk = phase_risk_map.get(asset_phase_idx, 50)
        micro_risk = max(0, (2 - micro_score) / 4 * 100)
        ops_risk = asset_risk * 0.7 + micro_risk * 0.3
        
        # 4. Risque de timing — poids 0.20
        cost_p95_pct = timing_dist.p95_cost / valeur_marche * 100 if valeur_marche > 0 else 50
        timing_risk = min(100, cost_p95_pct * 5)
        
        # SRI composite
        sri = (macro_risk * 0.30 + fin_risk * 0.25 + ops_risk * 0.25 + timing_risk * 0.20)
        sri = max(0, min(100, sri))
        
        # VaR et CVaR à partir de timing distribution
        var_95 = timing_dist.p95_cost
        tail = timing_dist.cost_samples[timing_dist.cost_samples >= var_95]
        cvar_95 = float(np.mean(tail)) if len(tail) > 0 else var_95
        
        # Tail risk : P(cost > 2x median)
        tail_threshold = timing_dist.median_cost * 2
        tail_risk = float(np.mean(timing_dist.cost_samples > tail_threshold)) * 100
        
        # Stabilité de la prescription : 1 - entropie normalisée
        stability = max(0, min(100, (1 - entropy_norm) * 100))
        
        # Probabilité de transition de régime
        transition_prob = phase_dist.risk_metrics.get("transition_probability", 0.2)
        
        return RiskProfile(
            strategic_risk_index=round(sri, 1),
            var_95=round(var_95, 0),
            cvar_95=round(cvar_95, 0),
            tail_risk_score=round(tail_risk, 1),
            stability_score=round(stability, 1),
            regime_transition_prob=round(transition_prob * 100, 1),
        )


# ─────────────────────────────────────────
# STRESS TESTING
# ─────────────────────────────────────────

class StressScenarios:
    """
    Scénarios de stress prédéfinis pour l'analyse de sensibilité.
    
    Chaque scénario modifie les inputs par des chocs calibrés
    sur des événements historiques (GFC 2008, COVID 2020, etc.)
    """
    
    SCENARIOS = {
        "Base case": {},
        "Recession modérée": {
            "gdp_growth": -0.02,        # choc absolu
            "tourism_growth": -0.08,
            "cci": -15,
            "bci": -12,
            "air_traffic": -0.10,
            "vix": +12,
            "spread_bps": +100,
            "credit_growth": -0.02,
        },
        "Crise financière (type GFC)": {
            "gdp_growth": -0.04,
            "tourism_growth": -0.15,
            "cci": -25,
            "bci": -20,
            "air_traffic": -0.20,
            "interest_rate": +0.02,
            "spread_bps": +250,
            "vix": +30,
            "credit_growth": -0.05,
        },
        "Choc pandémique (type COVID)": {
            "gdp_growth": -0.06,
            "tourism_growth": -0.40,
            "cci": -30,
            "bci": -25,
            "air_traffic": -0.50,
            "vix": +35,
            "supply_growth": -0.01,
        },
        "Surchauffe / bulle": {
            "gdp_growth": +0.02,
            "tourism_growth": +0.08,
            "supply_growth": +0.03,
            "pipeline_pct": +0.04,
            "interest_rate": +0.015,
            "credit_growth": +0.05,
            "vix": -5,
        },
        "Taux élevés prolongés": {
            "interest_rate": +0.025,
            "spread_bps": +80,
            "credit_growth": -0.03,
            "vix": +8,
        },
    }
    
    @classmethod
    def apply_scenario(cls, base_inputs: Dict[str, float],
                        scenario_name: str) -> Dict[str, float]:
        """Applique un scénario de stress aux inputs."""
        shocks = cls.SCENARIOS.get(scenario_name, {})
        stressed = dict(base_inputs)
        for key, shock in shocks.items():
            if key in stressed:
                stressed[key] = stressed[key] + shock
        return stressed
    
    @classmethod
    def run_all_scenarios(cls, engine: ProbabilisticEngine,
                           base_inputs: Dict[str, float],
                           market_type: str = "developed"
                           ) -> Dict[str, PhaseDistribution]:
        """Exécute tous les scénarios et retourne les distributions."""
        results = {}
        for name in cls.SCENARIOS:
            stressed_inputs = cls.apply_scenario(base_inputs, name)
            results[name] = engine.simulate_market_cycle(stressed_inputs, market_type)
        return results
