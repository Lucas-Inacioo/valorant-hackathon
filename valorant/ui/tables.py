"""Preparo de tabelas para exibição, sem estado de interface."""

import pandas as pd
from valorant.data.metadata import callout_name, nearest_callout
from valorant.analysis.events import alive_puuids
from valorant.analysis.first_blood import wilson_interval


def display_number(value, spec=".1f", suffix=""):
    return (
        format(value, spec.replace(",", "").replace("_", "")).replace(".", ",") + suffix
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
