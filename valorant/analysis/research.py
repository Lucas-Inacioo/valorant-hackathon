"""Achados e ranking com as mesmas observações usadas na revisão pós-jogo."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from valorant.analysis.first_blood import first_blood_table
from valorant.analysis.post_match import PATTERNS, build_match_review
from valorant.analysis.prediction import parse_match_name, team_names_by_color

REVIEW_PATTERNS = tuple(
    key for key, pattern in PATTERNS.items() if not pattern.positive and not pattern.context_only
)
MATCH_TOTALS = [
    "matches", "decided_matches", "match_wins", "rounds", "round_outcomes", "round_wins",
    "review_events", "review_rounds", "position_opportunities", "position_candidates", "deaths",
]
TEAM_MATCH_COLUMNS = [
    "match_id", "arquivo", "torneio", "inicio", "team_id", "team_name", *MATCH_TOTALS,
]


@dataclass(frozen=True)
class ResearchData:
    team_matches: pd.DataFrame
    observations: pd.DataFrame
    opportunities: pd.DataFrame
    team_rounds: pd.DataFrame
    openings: pd.DataFrame
    support_deaths: pd.DataFrame


def review_events(observations):
    """Uma equipe tem um lance por evento, mesmo quando vários padrões coincidem."""
    concerns = observations[observations["pattern_id"].isin(REVIEW_PATTERNS)]
    keys = ["team_id", "round", "event_index"]
    if "match_id" in concerns:
        keys.insert(0, "match_id")
    return concerns.drop_duplicates(keys)


def summarize_review_match(info, match, review, fights):
    names = team_names_by_color(match, parse_match_name(Path(info["arquivo"])))
    decided = sum(bool(team.get("won")) for team in match["teams"]) == 1
    won = {team["teamId"]: bool(team.get("won")) for team in match["teams"]}
    events = review_events(review.observations)
    candidates = fights[fights["diagnostico_tatico"].eq(True) & fights["aliados_vivos"].gt(0)]
    known_rounds = [
        result for result in match["roundResults"] if result.get("winningTeam") in {"Blue", "Red"}
    ]
    rows = []
    for team_id, team_name in names.items():
        rounds = review.rounds[review.rounds["team_id"].eq(team_id)]
        own_events = events[events["team_id"].eq(team_id)]
        eligible = review.opportunities[
            review.opportunities["pattern_id"].eq("isolated_death")
            & review.opportunities["team_id"].eq(team_id)
        ]
        rows.append({
            **{key: info[key] for key in ["match_id", "arquivo", "torneio", "inicio"]},
            "team_id": team_id,
            "team_name": team_name,
            "matches": 1,
            "decided_matches": int(decided),
            "match_wins": int(decided and won[team_id]),
            "rounds": len(rounds),
            "round_outcomes": len(known_rounds),
            "round_wins": sum(result["winningTeam"] == team_id for result in known_rounds),
            "review_events": len(own_events),
            "review_rounds": own_events["round"].nunique(),
            "position_opportunities": len(eligible),
            "position_candidates": int(candidates["time_vitima"].eq(team_id).sum()),
            "deaths": int((fights["time_vitima"].eq(team_id) & fights["diagnostico_tatico"].eq(True)).sum()),
        })
    return rows


def build_research_data(records, fights, rounds):
    """Recebe pares de inventário e JSON e tabelas já calculadas da mesma seleção."""
    team_rows, observations, opportunities, team_rounds = [], [], [], []
    fight_groups = {key: group for key, group in fights.groupby("match_id")}
    round_groups = {key: group for key, group in rounds.groupby("match_id")}
    for info, match in records:
        match_fights = fight_groups.get(info["match_id"], fights.iloc[:0])
        review = build_match_review(
            match, match_fights, round_groups.get(info["match_id"], rounds.iloc[:0])
        )
        team_rows.extend(summarize_review_match(info, match, review, match_fights))
        for target, frame in [
            (observations, review.observations[review.observations["pattern_id"].isin(REVIEW_PATTERNS)]),
            (opportunities, review.opportunities[review.opportunities["pattern_id"].isin(REVIEW_PATTERNS)]),
            (team_rounds, review.rounds),
        ]:
            target.append(frame.assign(match_id=info["match_id"]))

    def combine(frames):
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    openings = first_blood_table(fights)
    support = fights[
        fights["abertura_valida"].eq(True)
        & fights["primeira_vitima_unica"].eq(True)
        & fights["diagnostico_tatico"].eq(True)
        & fights["aliados_vivos"].gt(0)
        & fights["dist_aliado_mais_proximo"].notna()
    ][["match_id", "round", "dist_aliado_mais_proximo", "trocada", "venceu_round"]].copy()
    return ResearchData(
        pd.DataFrame(team_rows, columns=TEAM_MATCH_COLUMNS), combine(observations),
        combine(opportunities), combine(team_rounds), openings, support,
    )


def team_ranking(team_matches, minimum_matches=3):
    """Total e frequência por exposição, sem usar o resultado para contar lances."""
    summary = team_matches.groupby("team_name", as_index=False)[MATCH_TOTALS].sum()
    summary = summary[summary["matches"].ge(minimum_matches)].copy()
    for name, numerator, denominator, scale in [
        ("review_per_100", "review_events", "rounds", 100),
        ("review_round_rate", "review_rounds", "rounds", 1),
        ("match_win_rate", "match_wins", "decided_matches", 1),
        ("round_win_rate", "round_wins", "round_outcomes", 1),
        ("position_coverage", "position_opportunities", "position_candidates", 1),
        ("deaths_per_100", "deaths", "rounds", 100),
    ]:
        summary[name] = scale * summary[numerator] / summary[denominator].replace(0, np.nan)
    summary["review_rank"] = summary["review_per_100"].rank(ascending=False, method="min")
    return summary.sort_values(["review_per_100", "team_name"], ascending=[False, True], ignore_index=True)


def pattern_findings(data, match_ids):
    seen = data.observations[data.observations["match_id"].isin(match_ids)]
    eligible = data.opportunities[data.opportunities["match_id"].isin(match_ids)]
    rows = []
    for key in REVIEW_PATTERNS:
        observations = seen[seen["pattern_id"].eq(key)]
        opportunities = eligible[eligible["pattern_id"].eq(key)]
        unique_rounds = observations.drop_duplicates(["match_id", "team_id", "round"])
        rows.append({
            "pattern_id": key, "pattern": PATTERNS[key].name,
            "description": PATTERNS[key].description,
            "opportunity_label": PATTERNS[key].opportunity_label,
            "occurrences": len(observations), "opportunities": len(opportunities),
            "rate": len(observations) / len(opportunities) if len(opportunities) else np.nan,
            "rounds": len(unique_rounds),
            "round_win_rate": unique_rounds["won_round"].mean(),
        })
    return pd.DataFrame(rows).sort_values("occurrences", ascending=False, ignore_index=True)
