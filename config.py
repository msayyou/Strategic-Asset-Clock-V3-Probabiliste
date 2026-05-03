"""
Strategic Asset Clock™ V3 — Configuration centrale
Constantes, matrices de prescription, seuils, distributions a priori.
"""

# ─────────────────────────────────────────
# PHASES & LABELS
# ─────────────────────────────────────────
MACRO_PHASES = ["Recovery", "Expansion", "Hypersupply", "Recession"]
ASSET_PHASES = [
    "Phase 1 — Post-réno",
    "Phase 2 — Maturité",
    "Phase 3 — Fin de cycle",
    "Phase 4 — Urgence",
]
DIRECTIONS = ["Ascending ↑", "Stable →", "Descending ↓"]
VELOCITIES = ["Lente", "Normale", "Rapide"]

# ─────────────────────────────────────────
# COULEURS
# ─────────────────────────────────────────
MACRO_COLORS = {
    "Recovery":    "#1D9E75",
    "Expansion":   "#185FA5",
    "Hypersupply": "#BA7517",
    "Recession":   "#A32D2D",
}
ASSET_COLORS = {
    "Phase 1 — Post-réno":    "#1D9E75",
    "Phase 2 — Maturité":     "#185FA5",
    "Phase 3 — Fin de cycle": "#BA7517",
    "Phase 4 — Urgence":      "#D85A30",
}

# ─────────────────────────────────────────
# BENCHMARKS ROA
# ─────────────────────────────────────────
ROA_BENCHMARKS = {
    "Budget / Économique (1-2★)": 0.060,
    "Milieu de gamme (3★)":       0.055,
    "Haut de gamme (4★)":         0.050,
    "Luxe (5★)":                  0.045,
}

# ─────────────────────────────────────────
# PARAMÈTRES FINANCIERS
# ─────────────────────────────────────────
DISCOUNT_RATE = 0.07
PHASE_PENALTY = {0: 1.0, 1: 0.9, 2: 0.7, 3: 0.5}
DECOTE_PCT_BY_PHASE = {0: 0.02, 1: 0.04, 2: 0.06, 3: 0.08}

# ─────────────────────────────────────────
# DISTRIBUTIONS A PRIORI (paramètres)
# Pour chaque variable macro, on définit :
#   - type: "normal", "triangular", "uniform"
#   - params: selon le type
#   - sigma_pct: incertitude relative (%) pour Monte Carlo
# ─────────────────────────────────────────
PRIOR_DISTRIBUTIONS = {
    "gdp_growth":       {"type": "normal",     "sigma_pct": 0.30, "min": -5.0, "max": 15.0},
    "tourism_growth":   {"type": "normal",     "sigma_pct": 0.35, "min": -20.0, "max": 30.0},
    "cci":              {"type": "normal",     "sigma_pct": 0.08, "min": 50.0, "max": 150.0},
    "bci":              {"type": "normal",     "sigma_pct": 0.08, "min": 50.0, "max": 150.0},
    "air_traffic":      {"type": "normal",     "sigma_pct": 0.30, "min": -30.0, "max": 30.0},
    "supply_growth":    {"type": "triangular", "sigma_pct": 0.20, "min": 0.0, "max": 15.0},
    "pipeline_pct":     {"type": "triangular", "sigma_pct": 0.25, "min": 0.0, "max": 30.0},
    "absorption_months":{"type": "normal",     "sigma_pct": 0.20, "min": 3.0, "max": 48.0},
    "revpar_growth_3y": {"type": "normal",     "sigma_pct": 0.25, "min": -10.0, "max": 20.0},
    "interest_rate":    {"type": "normal",     "sigma_pct": 0.15, "min": 0.0, "max": 15.0},
    "spread_bps":       {"type": "normal",     "sigma_pct": 0.25, "min": 0.0, "max": 1000.0},
    "vix":              {"type": "normal",     "sigma_pct": 0.20, "min": 5.0, "max": 80.0},
    "credit_growth":    {"type": "normal",     "sigma_pct": 0.30, "min": -5.0, "max": 20.0},
    # Variables financières asset
    "noi":              {"type": "normal",     "sigma_pct": 0.12, "min": 0, "max": None},
    "valeur_marche":    {"type": "normal",     "sigma_pct": 0.15, "min": 0, "max": None},
    "taux_declin_noi":  {"type": "triangular", "sigma_pct": 0.30, "min": 0.0, "max": 0.25},
    "capex_estime":     {"type": "triangular", "sigma_pct": 0.20, "min": 0, "max": None},
}

# ─────────────────────────────────────────
# SIGNAUX & INITIATIVES
# ─────────────────────────────────────────
SIGNAL_CONFIG = {
    "opportunite":  {"label": "Opportunité forte",  "bg": "#E1F5EE", "color": "#0F6E56", "border": "#1D9E75"},
    "urgent":       {"label": "Action urgente",     "bg": "#FAEEDA", "color": "#633806", "border": "#BA7517"},
    "sortie":       {"label": "Décision de sortie", "bg": "#FAECE7", "color": "#712B13", "border": "#D85A30"},
    "optimisation": {"label": "Optimisation",       "bg": "#E6F1FB", "color": "#0C447C", "border": "#185FA5"},
    "attente":      {"label": "Attente / Hold",     "bg": "#F1EFE8", "color": "#444441", "border": "#888780"},
}

INIT_COLORS = {
    "critique": ("#A32D2D", "●"),
    "haut":     ("#BA7517", "●"),
    "moyen":    ("#185FA5", "●"),
}

# ─────────────────────────────────────────
# MATRICE 4×4 PRESCRIPTIONS
# ─────────────────────────────────────────
MATRIX = {
    "Recovery": {
        "Phase 1 — Post-réno": {
            "titre": "Acquérir et optimiser",
            "signal": "opportunite",
            "detail": "Fenêtre d'acquisition idéale. Asset récent + marché en redémarrage = risque opérationnel minimal, upside maximal.",
            "initiatives": [
                ("Sourcer actifs comparables sur le marché", "NOI", "haut"),
                ("Optimiser RevPAR — montée en gamme tarifaire", "NOI", "haut"),
                ("Déclencher plan de repositionnement commercial", "Valeur", "moyen"),
            ],
        },
        "Phase 2 — Maturité": {
            "titre": "Optimiser les revenus",
            "signal": "optimisation",
            "detail": "Asset solide en phase de pleine performance. Capitaliser sur la reprise macro pour maximiser GOP.",
            "initiatives": [
                ("Revenue management offensif — pricing dynamique", "NOI", "haut"),
                ("Renégocier contrats de distribution (OTA → direct)", "NOI", "moyen"),
                ("Planifier prochaine réno en amont du cycle", "Valeur", "moyen"),
            ],
        },
        "Phase 3 — Fin de cycle": {
            "titre": "Lancer la rénovation — fenêtre critique",
            "signal": "urgent",
            "detail": "Combinaison la plus actionnable. Marché en recovery = les travaux profiteront à la remontée.",
            "initiatives": [
                ("Lancer appels d'offres CapEx maintenant", "NOI", "critique"),
                ("Sécuriser financement — taux bas en début de cycle", "Valeur", "critique"),
                ("Négocier contrats en bas de cycle fournisseurs", "NOI", "haut"),
                ("Protéger GOP pendant travaux — plan de continuité", "NOI", "moyen"),
            ],
        },
        "Phase 4 — Urgence": {
            "titre": "Vendre ou recapitaliser d'urgence",
            "signal": "sortie",
            "detail": "Asset sous-investi sur marché en reprise. La valeur décline plus vite que le marché ne monte.",
            "initiatives": [
                ("Mandater un broker — window de cession ouverte", "Valeur", "critique"),
                ("Evaluer option changement d'usage ou rebranding", "Valeur", "critique"),
                ("Refinancement d'urgence si sortie impossible", "Valeur", "haut"),
            ],
        },
    },
    "Expansion": {
        "Phase 1 — Post-réno": {
            "titre": "Refinancer — recycler le capital",
            "signal": "optimisation",
            "detail": "Asset récent sur marché au sommet. NOI en pic = levier de refinancement maximal.",
            "initiatives": [
                ("Refinancement à valeur de marché maximale", "Valeur", "haut"),
                ("Recycler capital vers actifs Recovery + Ph.3", "Valeur", "haut"),
                ("Maximiser RevPAR — demande au pic", "NOI", "haut"),
            ],
        },
        "Phase 2 — Maturité": {
            "titre": "Maximiser RevPAR — pic du cycle",
            "signal": "optimisation",
            "detail": "Combinaison idéale de performance. Extraire le maximum de NOI avant le retournement macro.",
            "initiatives": [
                ("Pricing maximum — segmentation demande haut de gamme", "NOI", "haut"),
                ("Optimiser F&B et revenus annexes", "NOI", "moyen"),
                ("Surveiller signaux de retournement macro", "Valeur", "moyen"),
            ],
        },
        "Phase 3 — Fin de cycle": {
            "titre": "CapEx — décision critique avant retournement",
            "signal": "urgent",
            "detail": "Marché encore porteur mais asset en dégradation. Lancer les travaux maintenant.",
            "initiatives": [
                ("Lancer CapEx — profiter des marges actuelles pour financer", "NOI", "critique"),
                ("Planifier fermeture partielle en période creuse", "NOI", "haut"),
                ("Revoir structure de management si GOP comprimé", "NOI", "moyen"),
            ],
        },
        "Phase 4 — Urgence": {
            "titre": "Sortie optimale — pic de valorisation",
            "signal": "sortie",
            "detail": "Marché au sommet = valorisation maximale. Meilleur moment de cession pour un actif dégradé.",
            "initiatives": [
                ("Mandat de cession immédiat — capitaliser sur le pic", "Valeur", "critique"),
                ("Due diligence acquéreur — valorisation asset management premium", "Valeur", "critique"),
                ("Ne pas investir en CapEx avant cession", "NOI", "haut"),
            ],
        },
    },
    "Hypersupply": {
        "Phase 1 — Post-réno": {
            "titre": "Attendre — position défensive",
            "signal": "attente",
            "detail": "Asset en bonne forme mais marché sous pression concurrentielle.",
            "initiatives": [
                ("Défendre les parts de marché vs nouveaux entrants", "NOI", "moyen"),
                ("Réduire exposition OTA — renforcer direct", "NOI", "moyen"),
                ("Monitorer pipeline concurrentiel local", "Valeur", "moyen"),
            ],
        },
        "Phase 2 — Maturité": {
            "titre": "Planifier réno anticyclique",
            "signal": "optimisation",
            "detail": "Moment idéal pour planifier les travaux. Entreprises moins occupées = prix compétitifs.",
            "initiatives": [
                ("Lancer études et chiffrages CapEx à coût réduit", "NOI", "haut"),
                ("Négocier contrats fournisseurs en bas de cycle", "NOI", "haut"),
                ("Sécuriser financement anticipé avant Recession", "Valeur", "moyen"),
            ],
        },
        "Phase 3 — Fin de cycle": {
            "titre": "Rénover maintenant — fenêtre anticyclique",
            "signal": "opportunite",
            "detail": "Rénover en Hypersupply permet de sortir prêt pour la Recovery avec un actif neuf et des coûts bas.",
            "initiatives": [
                ("Lancer rénovation pendant la phase molle du marché", "Valeur", "critique"),
                ("Coûts travaux au plus bas — maximiser le chantier", "NOI", "critique"),
                ("Repositionner le produit pour le prochain cycle", "Valeur", "haut"),
            ],
        },
        "Phase 4 — Urgence": {
            "titre": "Repositionnement ou changement d'usage",
            "signal": "sortie",
            "detail": "Double pression : marché saturé + asset dégradé.",
            "initiatives": [
                ("Evaluer changement d'usage (résidentiel, co-living)", "Valeur", "critique"),
                ("Etude de rebranding segment sous-représenté localement", "Valeur", "haut"),
                ("Vente à opérateur spécialisé en retournement", "Valeur", "haut"),
            ],
        },
    },
    "Recession": {
        "Phase 1 — Post-réno": {
            "titre": "Conserver — cash flow défensif",
            "signal": "attente",
            "detail": "Asset récent en bas de cycle = position la plus confortable. Minimiser les coûts, protéger le cash flow.",
            "initiatives": [
                ("Réduire structure de coûts variables", "NOI", "moyen"),
                ("Renégocier contrats de management et de distribution", "NOI", "moyen"),
                ("Préparer le plan offensif pour la Recovery", "Valeur", "moyen"),
            ],
        },
        "Phase 2 — Maturité": {
            "titre": "Rénover en bas de cycle",
            "signal": "opportunite",
            "detail": "Recession = coûts travaux au minimum historique. Meilleur moment pour lancer le CapEx.",
            "initiatives": [
                ("Lancer la rénovation — coûts au plancher", "Valeur", "critique"),
                ("Financement — taux bas en Recession", "NOI", "haut"),
                ("Sortir rénové pour la Recovery : avantage concurrentiel majeur", "Valeur", "critique"),
            ],
        },
        "Phase 3 — Fin de cycle": {
            "titre": "Urgence structurelle",
            "signal": "urgent",
            "detail": "Situation la plus délicate. Asset dégradé + bas de marché = double pression sur la valeur.",
            "initiatives": [
                ("CapEx d'urgence partiel pour stopper la dégradation", "NOI", "haut"),
                ("Evaluer option cession — même en bas de cycle", "Valeur", "haut"),
                ("Refinancer avant que la valeur chute encore", "Valeur", "moyen"),
            ],
        },
        "Phase 4 — Urgence": {
            "titre": "Option changement d'usage",
            "signal": "sortie",
            "detail": "Valeur de continuation hôtelière probablement inférieure à la valeur d'usage alternatif.",
            "initiatives": [
                ("Analyse valeur foncière vs valeur hôtelière", "Valeur", "critique"),
                ("Etude changement d'usage — résidentiel, bureaux", "Valeur", "critique"),
                ("Cession terrain si plus-value résiduelle possible", "Valeur", "haut"),
            ],
        },
    },
}

# ─────────────────────────────────────────
# OPTIONS ANALYSIS — BASE SCORES
# ─────────────────────────────────────────
BASE_OPTION_SCORES = {
    "sortie":       {"Cession": 5, "Changement d'usage": 4, "Refinancement": 2, "Repositionnement": 2},
    "urgent":       {"Refinancement": 4, "Repositionnement": 3, "Cession": 2, "Changement d'usage": 2},
    "optimisation": {"Refinancement": 5, "Repositionnement": 3, "Cession": 2, "Changement d'usage": 1},
    "opportunite":  {"Repositionnement": 4, "Refinancement": 3, "Cession": 1, "Changement d'usage": 1},
    "attente":      {"Refinancement": 2, "Repositionnement": 2, "Cession": 2, "Changement d'usage": 2},
}
