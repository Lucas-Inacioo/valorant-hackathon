"""Preparo de tabelas para exibição, sem estado de interface."""

import pandas as pd
from valorant.data.metadata import callout_name, nearest_callout
from valorant.analysis.events import alive_puuids
from valorant.analysis.first_blood import wilson_interval


def display_number(value, spec=".1f", suffix=""):
    return (
        format(value, spec).translate(str.maketrans({",": ".", ".": ","})) + suffix
        if pd.notna(value)
        else "sem amostra"
    )


def openings_by_callout(attack_openings, map_meta):
    """Aberturas do ataque agrupadas pela região (callout) mais próxima de onde o defensor morreu."""
    callouts = attack_openings.assign(
        callout=[
            nearest_callout(x, y, map_meta)
            for x, y in zip(attack_openings["vitima_x"], attack_openings["vitima_y"])
        ]
    )
    by_callout = callouts.groupby("callout").agg(
        aberturas=("round", "size"), ataque_venceu=("abriu_venceu", "mean")
    )
    by_callout["ic95"] = [
        "{:.1%} a {:.1%}".format(*wilson_interval(round(rate * count), count))
        for rate, count in zip(by_callout["ataque_venceu"], by_callout["aberturas"])
    ]
    location_by_name = {
        callout_name(callout): (callout["location"]["x"], callout["location"]["y"])
        for callout in map_meta["callouts"]
    }
    by_callout["x"] = [location_by_name[name][0] for name in by_callout.index]
    by_callout["y"] = [location_by_name[name][1] for name in by_callout.index]
    return by_callout.sort_values("aberturas", ascending=False).round(3)


def first_blood_per_round_table(match_first_blood):
    columns = {
        "round": "round",
        "segundos": "primeira morte (s)",
        "time_abriu": "quem abriu",
        "lado_abriu": "lado",
        "trocada": "trocada",
        "antes_do_plant": "antes do plant",
        "abriu_venceu": "quem abriu venceu",
    }
    return match_first_blood[list(columns)].rename(columns=columns).round(1)


def deaths_per_round_table(match_deaths, round_results):
    """Por round da partida: vencedor e, para cada time, mortes, isoladas e trocadas."""
    per_round = match_deaths.groupby(["round", "time_vitima"]).agg(
        mortes=("vitima", "size"), isoladas=("isolada", "sum"), trocadas=("trocada", "sum")
    )
    per_round = per_round.unstack("time_vitima").fillna(0).astype(int)
    per_round.columns = [f"{team} {stat}" for stat, team in per_round.columns]
    winner_by_round = {
        round_result["roundNum"] + 1: round_result["winningTeam"] for round_result in round_results
    }
    attacker_by_round = {
        round_result["roundNum"] + 1: attacking_team(round_result) for round_result in round_results
    }
    per_round.insert(0, "vencedor", per_round.index.map(winner_by_round))
    per_round.insert(0, "atacante", per_round.index.map(attacker_by_round))
    return per_round.reset_index()


def attacking_team(round_result):
    other_team = {"Blue": "Red", "Red": "Blue"}
    winner = round_result["winningTeam"]
    return winner if round_result["winningTeamRole"] == "Attacker" else other_team[winner]


def players_summary(players):
    summary = players.groupby("puuid").agg(
        jogador=("jogador", "last"),
        partidas=("match_id", "nunique"),
        kills=("kills", "sum"),
        deaths=("deaths", "sum"),
        assists=("assists", "sum"),
        rounds=("rounds", "sum"),
        score=("score", "sum"),
    )
    summary["kd"] = (summary["kills"] / summary["deaths"].where(summary["deaths"] != 0)).round(2)
    summary["score_por_round"] = (summary["score"] / summary["rounds"]).round(0)
    return summary.sort_values("kills", ascending=False).reset_index(drop=True)


def event_position_table(event, names, teams):
    alive = alive_puuids(event)
    rows = [
        {
            "jogador": names.get(p["puuid"], p["puuid"]),
            "equipe": teams.get(p["puuid"], "?"),
            "estado": "vivo" if p["puuid"] in alive else "morto neste instante",
            "x": p["location"]["x"],
            "y": p["location"]["y"],
        }
        for p in event.get("locations", [])
    ]
    if event.get("victim") and event.get("victim_location"):
        puuid = event["victim"]
        if not any((p["puuid"] == puuid for p in event.get("locations", []))):
            rows.append(
                {
                    "jogador": names.get(puuid, puuid),
                    "equipe": teams.get(puuid, "?"),
                    "estado": "morto neste instante",
                    "x": event["victim_location"].get("x"),
                    "y": event["victim_location"].get("y"),
                }
            )
    return pd.DataFrame(rows, columns=["jogador", "equipe", "estado", "x", "y"])
