"""Mortes isoladas: a que distância do aliado vivo mais próximo cada jogador morre, e se o time venceu o round.

Uso: python solo_deaths.py [limite_em_unidades_de_jogo]
"""
import math
import sys

import pandas as pd

from collections import Counter

from explore_fields import DEFAULT_DATA_DIR, find_match_files, load_match
from maps import load_maps_by_url, nearest_callout, super_region
from round_map import round_events

# ponytail: assume 100 unidades por metro (Unreal usa cm), confirmar a escala antes de citar metros
SOLO_DISTANCE = 1000
TRADE_WINDOW_MS = 5000
DISTANCE_BANDS = [0, 500, 1000, 1500, 2000, 3000, float("inf")]
DISTANCE_BAND_LABELS = ["0-500", "500-1000", "1000-1500", "1500-2000", "2000-3000", "3000+"]
SIDE_LABELS = {"Attacker": "ataque", "Defender": "defesa"}
OPPOSITE_SIDE = {"Attacker": "Defender", "Defender": "Attacker"}
# Posições vivas nos primeiros 20 s do round definem o território normal de cada lado por região
EARLY_ROUND_MS = 20000
OWN_TERRITORY_MIN_SHARE = 0.65


def distance(location_a, location_b):
    return math.hypot(location_a["x"] - location_b["x"], location_a["y"] - location_b["y"])


def was_traded(kill, later_kills):
    """Troca: o killer morre em até 5 s, o que só o time da vítima pode fazer."""
    return any(later["victim"] == kill["actor"] and later["time_ms"] - kill["time_ms"] <= TRADE_WINDOW_MS for later in later_kills)


def allies_context(victim_location, ally_locations, ally_regions, solo_distance=SOLO_DISTANCE):
    """Pela posição dos aliados vivos: em grupo (alguém perto), flanco (time junto em outro lugar) ou isolado (time espalhado)."""
    if not ally_locations:
        return "último vivo"
    if min(distance(victim_location, location) for location in ally_locations) <= solo_distance:
        return "em grupo"
    if len(set(ally_regions)) == 1:
        return "flanco"
    return "isolado"


def death_rows(match, match_file, map_meta=None):
    """Uma linha por morte com as distâncias aos aliados e inimigos vivos no instante da kill."""
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    won_by_team = {team["teamId"]: team["won"] for team in match["teams"]}
    match_info = match["matchInfo"]
    rows = []
    for round_result in match["roundResults"]:
        kills = [event for event in round_events(round_result) if event["kind"] == "kill"]
        for death_order, kill in enumerate(kills, start=1):
            victim_team = team_by_puuid[kill["victim"]]
            victim_won_round = round_result["winningTeam"] == victim_team
            victim_role = round_result["winningTeamRole"] if victim_won_round else OPPOSITE_SIDE[round_result["winningTeamRole"]]
            killer_location = next((alive["location"] for alive in kill["locations"] if alive["puuid"] == kill["actor"]), {"x": math.nan, "y": math.nan})
            ally_locations = [alive["location"] for alive in kill["locations"] if team_by_puuid[alive["puuid"]] == victim_team]
            ally_distances = [distance(kill["victim_location"], location) for location in ally_locations]
            enemy_distances = [distance(kill["victim_location"], alive["location"]) for alive in kill["locations"] if team_by_puuid[alive["puuid"]] != victim_team]
            ally_regions = [super_region(location["x"], location["y"], map_meta) for location in ally_locations] if map_meta else []
            planted_before = bool(round_result["bombPlanter"]) and kill["time_ms"] >= round_result["plantRoundTime"]
            rows.append({
                "match_id": match_info["matchId"],
                "arquivo": match_file.name,
                "mapa": match_info["mapId"].rsplit("/", 1)[-1],
                "round": round_result["roundNum"] + 1,
                "segundos": kill["time_ms"] / 1000,
                "segundos_plant": round_result["plantRoundTime"] / 1000 if round_result["bombPlanter"] else math.nan,
                "fase": "pós-plant" if planted_before else "pré-plant",
                "ordem_da_morte": death_order,
                "vitima": kill["victim"],
                "vitima_x": kill["victim_location"]["x"],
                "vitima_y": kill["victim_location"]["y"],
                "killer_x": killer_location["x"],
                "killer_y": killer_location["y"],
                "time_vitima": victim_team,
                "regiao": nearest_callout(kill["victim_location"]["x"], kill["victim_location"]["y"], map_meta) if map_meta else "?",
                "contexto": allies_context(kill["victim_location"], ally_locations, ally_regions),
                "lado": SIDE_LABELS[victim_role],
                "aliados_vivos": len(ally_distances),
                "inimigos_vivos": len(enemy_distances),
                "dist_aliado_mais_proximo": min(ally_distances, default=math.nan),
                "dist_media_aliados": sum(ally_distances) / len(ally_distances) if ally_distances else math.nan,
                "dist_inimigo_mais_proximo": min(enemy_distances, default=math.nan),
                "trocada": was_traded(kill, kills[death_order:]),
                "venceu_round": victim_won_round,
                "venceu_partida": won_by_team[victim_team],
            })
    return rows


def early_positions(match, map_meta, round_result):
    """Posições vivas nos primeiros segundos do round: (região, lado) por jogador em cada snapshot de kill."""
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    attacking_team = round_result["winningTeam"] if round_result["winningTeamRole"] == "Attacker" else OPPOSITE_TEAM[round_result["winningTeam"]]
    for event in round_events(round_result):
        if event["kind"] != "kill" or event["time_ms"] > EARLY_ROUND_MS:
            continue
        for alive in event["locations"]:
            side = "ataque" if team_by_puuid[alive["puuid"]] == attacking_team else "defesa"
            yield nearest_callout(alive["location"]["x"], alive["location"]["y"], map_meta), side


OPPOSITE_TEAM = {"Blue": "Red", "Red": "Blue"}


def defender_share_by_region(matches_with_meta):
    """Por mapa e região, fração de defensores entre as posições vivas do começo do round."""
    counts = Counter()
    for match, map_meta in matches_with_meta:
        map_name = match["matchInfo"]["mapId"].rsplit("/", 1)[-1]
        for round_result in match["roundResults"]:
            for region, side in early_positions(match, map_meta, round_result):
                counts[(map_name, region, side)] += 1
    rows = {}
    for (map_name, region, side), count in counts.items():
        rows.setdefault((map_name, region), {"ataque": 0, "defesa": 0})[side] += count
    return {key: sides["defesa"] / (sides["ataque"] + sides["defesa"]) for key, sides in rows.items()}


def build_deaths_table(data_dir=DEFAULT_DATA_DIR):
    maps_by_url = load_maps_by_url()
    matches_with_meta = []
    for match_file in find_match_files(data_dir):
        match = load_match(match_file)
        matches_with_meta.append((match, match_file, maps_by_url.get(match["matchInfo"]["mapId"])))
    rows = []
    for match, match_file, map_meta in matches_with_meta:
        rows += death_rows(match, match_file, map_meta)
    deaths = pd.DataFrame(rows)
    defender_share = defender_share_by_region([(match, map_meta) for match, _, map_meta in matches_with_meta if map_meta])
    deaths["territorio_defesa"] = [defender_share.get((map_name, region), math.nan) for map_name, region in zip(deaths["mapa"], deaths["regiao"])]
    own_side_share = deaths["territorio_defesa"].where(deaths["lado"] == "defesa", 1 - deaths["territorio_defesa"])
    deaths["territorio"] = own_side_share.map(territory_label)
    return deaths


def territory_label(own_side_share):
    """Território próprio, disputado ou do adversário, pela fração do próprio lado entre as posições do começo do round."""
    if math.isnan(own_side_share):
        return "?"
    if own_side_share >= OWN_TERRITORY_MIN_SHARE:
        return "próprio"
    if own_side_share <= 1 - OWN_TERRITORY_MIN_SHARE:
        return "do adversário"
    return "disputado"


def with_solo_flag(deaths, solo_distance):
    """Só mortes com algum aliado vivo contam: sem aliado não existe distância para medir."""
    deaths_with_allies = deaths[deaths["aliados_vivos"] > 0].copy()
    deaths_with_allies["isolada"] = deaths_with_allies["dist_aliado_mais_proximo"] > solo_distance
    return deaths_with_allies


def summary_by_round_outcome(deaths_with_allies, group_columns=()):
    return deaths_with_allies.groupby([*group_columns, "venceu_round"]).agg(
        mortes=("vitima", "size"),
        dist_aliado_media=("dist_aliado_mais_proximo", "mean"),
        dist_aliado_mediana=("dist_aliado_mais_proximo", "median"),
        dist_inimigo_media=("dist_inimigo_mais_proximo", "mean"),
        fracao_isoladas=("isolada", "mean"),
        fracao_trocadas=("trocada", "mean"),
    ).round(2)


def distance_bands(deaths_with_allies):
    return pd.cut(deaths_with_allies["dist_aliado_mais_proximo"], DISTANCE_BANDS, labels=DISTANCE_BAND_LABELS)


def summary_by_distance_band(deaths_with_allies, group_columns=()):
    """Por faixa de distância ao aliado mais próximo: quantas mortes, quantas trocadas e quantas em rounds vencidos."""
    return deaths_with_allies.groupby([*group_columns, distance_bands(deaths_with_allies)], observed=True).agg(
        mortes=("vitima", "size"),
        fracao_trocadas=("trocada", "mean"),
        venceu_round=("venceu_round", "mean"),
    ).round(3)


def first_death_summary(deaths_with_allies, group_columns=()):
    """Primeira morte do round, isolada ou não e trocada ou não: quanto o time da vítima ainda venceu o round."""
    first_deaths = deaths_with_allies[deaths_with_allies["ordem_da_morte"] == 1]
    return first_deaths.groupby([*group_columns, "isolada", "trocada"]).agg(rounds=("vitima", "size"), vitoria_da_vitima=("venceu_round", "mean")).round(3)


def main():
    solo_distance = float(sys.argv[1]) if len(sys.argv) > 1 else SOLO_DISTANCE
    deaths = build_deaths_table()
    deaths_with_allies = with_solo_flag(deaths, solo_distance)
    print(f"Mortes: {len(deaths)}, com aliado vivo: {len(deaths_with_allies)}, limite de isolamento: {solo_distance:.0f} unidades\n")
    print("Por lado e resultado do round da vítima:")
    print(summary_by_round_outcome(deaths_with_allies, ["lado"]).to_string(), "\n")
    print("Por lado e faixa de distância ao aliado mais próximo:")
    print(summary_by_distance_band(deaths_with_allies, ["lado"]).to_string(), "\n")
    print("Primeira morte do round por lado (isolada x trocada):")
    print(first_death_summary(deaths_with_allies, ["lado"]).to_string(), "\n")
    print("Contexto pela posição dos aliados, por lado e fase:")
    print(context_summary(deaths_with_allies, ["lado", "fase"]).to_string())


def context_summary(deaths_with_allies, group_columns=()):
    """Por contexto (em grupo, flanco, isolado): mortes, trocadas e rounds vencidos."""
    return deaths_with_allies.groupby([*group_columns, "contexto"]).agg(mortes=("vitima", "size"), trocada=("trocada", "mean"), venceu_round=("venceu_round", "mean")).round(3)


def win_rate_by_situation(deaths_with_allies, flag_column, min_deaths=60, min_each_group=15):
    """Por lado e situação (aliados x inimigos vivos): vitória do round sem e com a condição. Separa a vantagem numérica do efeito."""
    rows = []
    for (side, allies, enemies), cell in deaths_with_allies.groupby(["lado", "aliados_vivos", "inimigos_vivos"]):
        with_flag, without_flag = cell[cell[flag_column]], cell[~cell[flag_column]]
        if len(cell) < min_deaths or len(with_flag) < min_each_group or len(without_flag) < min_each_group:
            continue
        rows.append({"lado": side, "situacao": f"{allies}v{enemies}", "mortes": len(cell), "sem": without_flag["venceu_round"].mean(), "com": with_flag["venceu_round"].mean()})
    table = pd.DataFrame(rows)
    table["diferenca"] = table["com"] - table["sem"]
    return table.round(2)


def territory_summary(deaths_with_allies, group_columns=()):
    return deaths_with_allies.groupby([*group_columns, "territorio"]).agg(mortes=("vitima", "size"), trocada=("trocada", "mean"), venceu_round=("venceu_round", "mean")).round(3)


if __name__ == "__main__":
    main()
