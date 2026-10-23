"""Comparação descritiva de rankings, com empates e reamostragem de partidas."""

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RankComparison:
    spearman: float
    concordance: float
    comparable_pairs: int
    performance_ties: int
    review_ties: int
    teams: int
    spearman_low: float = math.nan
    spearman_high: float = math.nan
    concordance_low: float = math.nan
    concordance_high: float = math.nan
    valid_resamples: int = 0


def spearman_correlation(scores, outcomes):
    table = pd.DataFrame({"score": scores, "outcome": outcomes})
    table = table.replace([np.inf, -np.inf], np.nan).dropna()
    if len(table) < 3 or table["score"].nunique() < 2 or table["outcome"].nunique() < 2:
        return math.nan
    ranks = table.rank(method="average")
    return float(np.corrcoef(ranks["score"], ranks["outcome"])[0, 1])


def pairwise_concordance(scores, outcomes):
    table = pd.DataFrame({"score": scores, "outcome": outcomes})
    table = table.replace([np.inf, -np.inf], np.nan).dropna()
    left, right = np.triu_indices(len(table), 1)
    score_difference = table["score"].to_numpy()[left] - table["score"].to_numpy()[right]
    outcome_difference = table["outcome"].to_numpy()[left] - table["outcome"].to_numpy()[right]
    different = outcome_difference != 0
    tied_scores = (score_difference == 0) & different
    concordant = score_difference * outcome_difference > 0
    count = int(different.sum())
    value = (concordant.sum() + .5 * tied_scores.sum()) / count if count else math.nan
    return float(value), count, int((~different).sum()), int(tied_scores.sum())


def compare_rankings(ranking, performance="round_win_rate"):
    table = ranking[["review_per_100", performance]].replace([np.inf, -np.inf], np.nan).dropna()
    scores, outcomes = -table["review_per_100"], table[performance]
    concordance, pairs, outcome_ties, review_ties = pairwise_concordance(scores, outcomes)
    return RankComparison(
        spearman_correlation(scores, outcomes), concordance, pairs, outcome_ties, review_ties, len(table)
    )


def centered_interval(values, point, floor):
    """Reamostrar partidas deixa as taxas das equipes mais ruidosas e puxa as correlações para baixo.
    Por isso só a variação das reamostragens é usada, em volta do valor observado."""
    if not values:
        return math.nan, math.nan
    low, high = np.quantile(values, [.025, .975]) - np.mean(values) + point
    return max(floor, low), min(1, high)


def bootstrap_comparison(team_matches, ranking, performance="round_win_rate", repetitions=500, seed=0):
    """Reamostra partidas inteiras, mantendo as duas equipes juntas e a coorte original.

    Equipes sem exposição em uma reamostra ficam fora daquela conta. Os
    intervalos descrevem esta agenda. Não se tratam rounds ou pares de equipes
    como observações independentes, e o resultado não escolhe os lances.
    """
    point = compare_rankings(ranking, performance)
    names = ranking["team_name"].tolist()
    if point.teams < 3 or team_matches["match_id"].nunique() < 2 or repetitions < 1:
        return point
    matches = sorted(team_matches["match_id"].unique())
    cohort = team_matches[team_matches["team_name"].isin(names)]
    numerator, denominator = (
        ("round_wins", "round_outcomes") if performance == "round_win_rate"
        else ("match_wins", "decided_matches")
    )
    rng = np.random.default_rng(seed)
    weights = rng.multinomial(len(matches), np.full(len(matches), 1 / len(matches)), size=repetitions)
    totals = {}
    for column in ["review_events", "rounds", numerator, denominator]:
        matrix = cohort.pivot_table(
            index="match_id", columns="team_name", values=column, aggfunc="sum", fill_value=0
        ).reindex(index=matches, columns=names, fill_value=0).to_numpy(dtype=float)
        totals[column] = weights @ matrix
    with np.errstate(divide="ignore", invalid="ignore"):
        scores = -totals["review_events"] / totals["rounds"]
        outcomes = totals[numerator] / totals[denominator]
    correlations, concordances = [], []
    for score, outcome in zip(scores, outcomes):
        correlation = spearman_correlation(score, outcome)
        concordance, _, _, _ = pairwise_concordance(score, outcome)
        if np.isfinite(correlation):
            correlations.append(correlation)
        if np.isfinite(concordance):
            concordances.append(concordance)
    low, high = centered_interval(correlations, point.spearman, -1)
    c_low, c_high = centered_interval(concordances, point.concordance, 0)
    return RankComparison(
        point.spearman, point.concordance, point.comparable_pairs, point.performance_ties,
        point.review_ties, point.teams, float(low), float(high), float(c_low), float(c_high),
        len(correlations),
    )
