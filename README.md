# Strategic-Asset-Clock-V3-Probabiliste
Ce que la V3 apporte vs V2
Dimension	V2	V3
Scoring	Point unique (déterministe)	Distribution de probabilité P(phase)
Confiance	Heuristique simple	Entropie de Shannon + IC 90%
Timing	Coût unique	Distribution MC avec VaR/CVaR
Risque	Aucun index	Strategic Risk Index composite
Stress	Aucun	6 scénarios calibrés (GFC, COVID, etc.)
Robustesse	Non mesurée	% scénarios qui changent la prescription
Transition	Non mesurée	P(changement de phase 12 mois)
Rapport	Texte simple	Sections probabilistes + risk + stress
🧠 Fondements méthodologiques

    Monte Carlo : propagation d'incertitude standard (Crystal Ball / @RISK)
    Entropie de Shannon : mesure d'incertitude informationnelle pure
    VaR / CVaR : standard risk management (Bâle III adapté)
    Stress testing : scénarios calibrés sur événements historiques
    Strategic Risk Index : composite pondéré multi-dimensionnel
    Bayesian updating ready : architecture prête pour mise à jour avec données réelles
