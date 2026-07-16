"""
Match outcome prediction + a simple player-performance projection.

Honesty note upfront: there's no free historical-results dataset here to
train a real ML model on, so match outcome uses a simplified Poisson
goal-expectancy model — a real, transparent statistical method that's been
a baseline in football analytics for decades. It is NOT as sophisticated
as a modern trained model (no home-advantage weighting, no current-form
momentum, no injuries) — an honest baseline, not state-of-the-art.

Player projection is a plain linear extrapolation from tracked-clip data —
explicitly not a forecast, since real output isn't constant over 90 minutes.
"""
import math


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def predict_match_outcome(team_a: dict, team_b: dict, league_avg_goals_per_game: float, max_goals: int = 8):
    """team_a / team_b: dicts with 'goals_for', 'goals_against', 'played'.
    Returns win/draw/loss probabilities and each side's expected goals, or
    None if there isn't enough data."""
    if not team_a["played"] or not team_b["played"] or league_avg_goals_per_game <= 0:
        return None

    a_attack = (team_a["goals_for"] / team_a["played"]) / league_avg_goals_per_game
    a_defense = (team_a["goals_against"] / team_a["played"]) / league_avg_goals_per_game
    b_attack = (team_b["goals_for"] / team_b["played"]) / league_avg_goals_per_game
    b_defense = (team_b["goals_against"] / team_b["played"]) / league_avg_goals_per_game

    lambda_a = a_attack * b_defense * league_avg_goals_per_game
    lambda_b = b_attack * a_defense * league_avg_goals_per_game

    a_win = draw = b_win = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = _poisson_pmf(i, lambda_a) * _poisson_pmf(j, lambda_b)
            if i > j:
                a_win += p
            elif i == j:
                draw += p
            else:
                b_win += p

    total = a_win + draw + b_win
    if total == 0:
        return None

    return {
        "team_a_win": a_win / total,
        "draw": draw / total,
        "team_b_win": b_win / total,
        "lambda_a": round(lambda_a, 2),
        "lambda_b": round(lambda_b, 2),
    }


def project_full_match_stats(clip_distance_m: float, clip_duration_min: float, target_minutes: float = 90):
    """Linear extrapolation from observed clip work-rate to a full match
    duration. Not a forecast — just scaling what was actually measured."""
    if clip_duration_min <= 0:
        return None
    rate_m_per_min = clip_distance_m / clip_duration_min
    return {
        "projected_distance_m": round(rate_m_per_min * target_minutes),
        "rate_m_per_min": round(rate_m_per_min, 1),
    }
