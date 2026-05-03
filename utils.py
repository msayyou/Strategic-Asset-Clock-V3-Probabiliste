"""
Strategic Asset Clock™ V3 — Utilitaires partagés
"""

def present_value(value: float, year: int, rate: float = 0.07) -> float:
    """Valeur actualisée."""
    return value / ((1 + rate) ** year)


def normalize_1_5(score: float) -> float:
    """Normalise un score 1-5 vers [-2, +2]."""
    return (score - 3.0) * 1.0


def clamp(value: float, lo: float, hi: float) -> float:
    """Borne une valeur entre lo et hi."""
    return max(lo, min(hi, value))


def format_eur(value: float) -> str:
    """Format monétaire français."""
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M€"
    elif abs(value) >= 1_000:
        return f"{value / 1_000:.0f}k€"
    return f"{value:.0f}€"


def format_pct(value: float, decimals: int = 1) -> str:
    """Format pourcentage."""
    return f"{value * 100:.{decimals}f}%"
