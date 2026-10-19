"""Mortes isoladas: a que distância do aliado vivo mais próximo cada jogador morre, e se o time venceu o round.

Uso: python solo_deaths.py [limite_em_unidades_de_jogo]
"""
import math
import sys

import pandas as pd

from explore_fields import DEFAULT_DATA_DIR, find_match_files, load_match
from round_map import round_events

# ponytail: assume 100 unidades por metro (Unreal usa cm), confirmar a escala antes de citar metros
SOLO_DISTANCE = 1000
TRADE_WINDOW_MS = 5000
DISTANCE_BANDS = [0, 500, 1000, 1500, 2000, 3000, float("inf")]
DISTANCE_BAND_LABELS = ["0-500", "500-1000", "1000-1500", "1500-2000", "2000-3000", "3000+"]


def distance(location_a, location_b):
    return math.hypot(location_a["x"] - location_b["x"], location_a["y"] - location_b["y"])


def was_traded(kill, later_kills):
    """Troca: o killer morre em até 5 s, o que só o time da vítima pode fazer."""
    return any(later["victim"] == kill["actor"] and later["time_ms"] - kill["time_ms"] <= TRADE_WINDOW_MS for later in later_kills)


def death_rows(match, match_file):
    """Uma linha por morte com as distâncias aos aliados e inimigos vivos no instante da kill."""
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    won_by_team = {team["teamId"]: team["won"] for team in match["teams"]}
    match_info = match["matchInfo"]
    rows = []
    for round_result in match["roundResults"]:
        kills = [event for event in round_events(round_result) if event["kind"] == "kill"]
        for death_order, kill in enumerate(kills, start=1):
            victim_team = team_by_puuid[kill["victim"]]
            ally_distances = [distance(kill["victim_location"], alive["location"]) for alive in kill["locations"] if team_by_puuid[alive["puuid"]] == victim_team]
            enemy_distances = [distance(kill["victim_location"], alive["location"]) for alive in kill["locations"] if team_by_puuid[alive["puuid"]] != victim_team]
            rows.append({
                "match_id": match_info["matchId"],
                "arquivo": match_file.name,
                "mapa": match_info["mapId"].rsplit("/", 1)[-1],
                "round": round_result["roundNum"] + 1,
                "segundos": kill["time_ms"] / 1000,
                "ordem_da_morte": death_order,
                "vitima": kill["victim"],
                "time_vitima": victim_team,
                "aliados_vivos": len(ally_distances),
                "inimigos_vivos": len(enemy_distances),
                "dist_aliado_mais_proximo": min(ally_distances, default=math.nan),
                "dist_media_aliados": sum(ally_distances) / len(ally_distances) if ally_distances else math.nan,
                "dist_inimigo_mais_proximo": min(enemy_distances, default=math.nan),
                "trocada": was_traded(kill, kills[death_order:]),
                "venceu_round": round_result["winningTeam"] == victim_team,
                "venceu_partida": won_by_team[victim_team],
            })
    return rows


def build_deaths_table(data_dir=DEFAULT_DATA_DIR):
    rows = []
    for match_file in find_match_files(data_dir):
        rows += death_rows(load_match(match_file), match_file)
    return pd.DataFrame(rows)


def with_solo_flag(deaths, solo_distance):
    """Só mortes com algum aliado vivo contam: sem aliado não existe distância para medir."""
    deaths_with_allies = deaths[deaths["aliados_vivos"] > 0].copy()
    deaths_with_allies["isolada"] = deaths_with_allies["dist_aliado_mais_proximo"] > solo_distance
    return deaths_with_allies


def summary_by_round_outcome(deaths_with_allies):
    return deaths_with_allies.groupby("venceu_round").agg(
        mortes=("vitima", "size"),
        dist_aliado_media=("dist_aliado_mais_proximo", "mean"),
        dist_aliado_mediana=("dist_aliado_mais_proximo", "median"),
        dist_inimigo_media=("dist_inimigo_mais_proximo", "mean"),
        fracao_isoladas=("isolada", "mean"),
        fracao_trocadas=("trocada", "mean"),
    ).round(2)


def distance_bands(deaths_with_allies):
    return pd.cut(deaths_with_allies["dist_aliado_mais_proximo"], DISTANCE_BANDS, labels=DISTANCE_BAND_LABELS)


def summary_by_distance_band(deaths_with_allies):
    """Por faixa de distância ao aliado mais próximo: quantas mortes, quantas trocadas e quantas em rounds vencidos."""
    return deaths_with_allies.groupby(distance_bands(deaths_with_allies), observed=True).agg(
        mortes=("vitima", "size"),
        fracao_trocadas=("trocada", "mean"),
        venceu_round=("venceu_round", "mean"),
    ).round(3)


def first_death_summary(deaths_with_allies):
    """Primeira morte do round, isolada ou não e trocada ou não: quanto o time da vítima ainda venceu o round."""
    first_deaths = deaths_with_allies[deaths_with_allies["ordem_da_morte"] == 1]
    return first_deaths.groupby(["isolada", "trocada"]).agg(rounds=("vitima", "size"), vitoria_da_vitima=("venceu_round", "mean")).round(3)


def main():
    solo_distance = float(sys.argv[1]) if len(sys.argv) > 1 else SOLO_DISTANCE
    deaths = build_deaths_table()
    deaths_with_allies = with_solo_flag(deaths, solo_distance)
    print(f"Mortes: {len(deaths)}, com aliado vivo: {len(deaths_with_allies)}, limite de isolamento: {solo_distance:.0f} unidades\n")
    print("Por resultado do round da vítima (venceu_round):")
    print(summary_by_round_outcome(deaths_with_allies).to_string(), "\n")
    print("Por faixa de distância ao aliado mais próximo:")
    print(summary_by_distance_band(deaths_with_allies).to_string(), "\n")
    print("Primeira morte do round (isolada x trocada):")
    print(first_death_summary(deaths_with_allies).to_string())


if __name__ == "__main__":
    main()
