"""Mortes isoladas: a que distância do aliado vivo mais próximo cada jogador morre, e se o time venceu o round.

Uso: python solo_deaths.py [limite_em_unidades_de_jogo]
"""
import math
import sys

import pandas as pd

from collections import Counter

from explore_fields import DEFAULT_DATA_DIR, find_match_files, load_match
from maps import load_agents_by_id, load_maps_by_url, nearest_callout, super_region
from match_events import alive_puuids, attacking_team, round_events, was_traded as event_was_traded

# Escala aproximada de 100 unidades por metro; não validada nestes arquivos.
SOLO_DISTANCE = 1000
TRADE_WINDOW_MS = 5000
DISTANCE_BANDS = [0, 500, 1000, 1500, 2000, 3000, float("inf")]
DISTANCE_BAND_LABELS = ["0-500", "500-1000", "1000-1500", "1500-2000", "2000-3000", "3000+"]
# Primeiro confronto até 20 s: ocupação observada por lado, sem inferir território normativo.
EARLY_ROUND_MS = 20000
OWN_TERRITORY_MIN_SHARE = 0.65


def distance(location_a, location_b):
    return math.hypot(location_a["x"] - location_b["x"], location_a["y"] - location_b["y"])


def was_traded(kill, later_kills, team_by_puuid=None):
    """Compatibilidade: passe todos os eventos para incluir timestamps empatados."""
    return event_was_traded(kill, later_kills, team_by_puuid, TRADE_WINDOW_MS)


def allies_context(victim_location, ally_locations, ally_regions, solo_distance=SOLO_DISTANCE):
    """Contexto observado; a chave interna flanco significa separado do grupo."""
    if not ally_locations:
        return "último vivo"
    if min(distance(victim_location, location) for location in ally_locations) <= solo_distance:
        return "em grupo"
    if len(ally_locations) >= 2 and ally_regions and "?" not in ally_regions and len(set(ally_regions)) == 1:
        return "flanco"
    return "isolado"


DEATH_COLUMNS = [
    "match_id", "arquivo", "mapa", "round", "event_id", "event_index", "segundos", "segundos_plant",
    "fase", "ordem_da_morte", "ordem_do_abate", "vitima", "killer", "personagem", "vitima_x", "vitima_y",
    "killer_x", "killer_y", "time_vitima", "time_killer", "regiao", "contexto", "aliados_mesma_regiao", "lado",
    "aliados_vivos", "inimigos_vivos", "dist_aliado_mais_proximo", "dist_media_aliados", "dist_inimigo_mais_proximo",
    "trocada", "trade_simultaneous", "venceu_round", "venceu_partida", "rounds_do_time", "rounds_do_time_sem_round",
    "abate_adversario", "apos_decisao", "diagnostico_tatico", "abertura_valida", "abertura_ambigua",
    "abertura_simultanea", "primeira_vitima_unica",
]


def death_rows(match, match_file, map_meta=None):
    """Uma linha por morte bruta, com flags explícitas para a análise tática."""
    team_by_puuid = {p["puuid"]: p["teamId"] for p in match["players"]}
    character_by_puuid = {p["puuid"]: p.get("characterId") for p in match["players"]}
    won_by_team = {team["teamId"]: team["won"] for team in match["teams"]}
    team_totals = {team["teamId"]: team for team in match["teams"]}
    match_info = match["matchInfo"]
    rows = []
    for rr in match["roundResults"]:
        events = round_events(rr, team_by_puuid)
        kills = [e for e in events if e["kind"] == "kill"]
        tactical = [e for e in kills if e["tactical_valid"]]
        first_time = min((e["time_ms"] for e in tactical), default=None)
        opening = [e for e in tactical if e["time_ms"] == first_time]
        opening_teams = {team_by_puuid.get(e["actor"]) for e in opening}
        order_by_id = {e["event_id"]: i for i, e in enumerate(tactical, 1)}
        attacker = attacking_team(rr)
        for death_order, kill in enumerate(kills, 1):
            victim_team = team_by_puuid.get(kill["victim"])
            victim_won = rr.get("winningTeam") == victim_team
            known_alive = alive_puuids(kill)
            locations = {p["puuid"]: p["location"] for p in kill["locations"] if p["puuid"] in known_alive}
            killer_location = locations.get(kill["actor"], {"x": math.nan, "y": math.nan})
            victim_location = kill["victim_location"]
            ally_locations = [loc for puuid, loc in locations.items() if team_by_puuid.get(puuid) == victim_team and puuid != kill["victim"]]
            ally_distances = [distance(victim_location, loc) for loc in ally_locations]
            enemy_distances = [distance(victim_location, loc) for puuid, loc in locations.items() if team_by_puuid.get(puuid) in {"Blue", "Red"} and team_by_puuid[puuid] != victim_team]
            ally_regions = [super_region(loc["x"], loc["y"], map_meta) for loc in ally_locations] if map_meta else []
            plant_seconds = rr.get("plantRoundTime", 0) / 1000 if rr.get("bombPlanter") else math.nan
            team_total = team_totals.get(victim_team, {})
            played, wins = team_total.get("roundsPlayed", 0), team_total.get("roundsWon", 0)
            is_opening = kill["tactical_valid"] and kill["time_ms"] == first_time
            trade = was_traded(kill, events, team_by_puuid)
            simultaneous_trade = trade and any(
                e["time_ms"] == kill["time_ms"] and e.get("victim") == kill["actor"]
                and e["tactical_valid"] and team_by_puuid.get(e["actor"]) == victim_team for e in kills)
            rows.append({
                "match_id": match_info["matchId"], "arquivo": match_file.name,
                "mapa": match_info["mapId"].rsplit("/", 1)[-1], "round": rr["roundNum"] + 1,
                "event_id": kill["event_id"], "event_index": kill["index"], "segundos": kill["time_ms"] / 1000,
                "segundos_plant": plant_seconds,
                "fase": "pós-plant" if rr.get("bombPlanter") and kill["time_ms"] >= rr["plantRoundTime"] else "pré-plant",
                "ordem_da_morte": death_order, "ordem_do_abate": order_by_id.get(kill["event_id"]),
                "vitima": kill["victim"], "killer": kill["actor"], "personagem": character_by_puuid.get(kill["victim"]),
                "vitima_x": victim_location.get("x", math.nan), "vitima_y": victim_location.get("y", math.nan),
                "killer_x": killer_location["x"], "killer_y": killer_location["y"],
                "time_vitima": victim_team, "time_killer": team_by_puuid.get(kill["actor"]),
                "regiao": nearest_callout(victim_location["x"], victim_location["y"], map_meta) if map_meta else "?",
                "contexto": allies_context(victim_location, ally_locations, ally_regions),
                "aliados_mesma_regiao": len(ally_locations) >= 2 and bool(ally_regions) and "?" not in ally_regions and len(set(ally_regions)) == 1,
                "lado": "?" if attacker is None else ("ataque" if victim_team == attacker else "defesa"),
                "aliados_vivos": len(ally_distances), "inimigos_vivos": len(enemy_distances),
                "dist_aliado_mais_proximo": min(ally_distances, default=math.nan),
                "dist_media_aliados": sum(ally_distances) / len(ally_distances) if ally_distances else math.nan,
                "dist_inimigo_mais_proximo": min(enemy_distances, default=math.nan),
                "trocada": trade, "trade_simultaneous": simultaneous_trade,
                "venceu_round": victim_won, "venceu_partida": won_by_team.get(victim_team, False),
                "rounds_do_time": wins / played if played else math.nan,
                "rounds_do_time_sem_round": (wins - int(victim_won)) / (played - 1) if played > 1 else math.nan,
                "abate_adversario": kill["enemy_kill"], "apos_decisao": kill["after_decision"],
                "diagnostico_tatico": kill["tactical_valid"],
                "abertura_valida": is_opening and len(opening_teams) == 1,
                "abertura_ambigua": is_opening and len(opening_teams) > 1,
                "abertura_simultanea": is_opening and len(opening) > 1,
                "primeira_vitima_unica": is_opening and len(opening) == 1,
            })
    return rows


def early_positions(match, map_meta, round_result):
    """Primeiro instante de confronto até 20 s, com vítimas, uma posição por pessoa."""
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    attacking = attacking_team(round_result)
    if attacking is None:
        return
    events = [e for e in round_events(round_result, team_by_puuid)
              if e["tactical_valid"] and e["time_ms"] <= EARLY_ROUND_MS]
    if not events:
        return
    first_group = [e for e in events if e["time_ms"] == events[0]["time_ms"]]
    positions = {p["puuid"]: p["location"] for e in first_group for p in e["locations"]}
    positions.update({e["victim"]: e["victim_location"] for e in first_group})
    for puuid, location in positions.items():
        if team_by_puuid.get(puuid) not in {"Blue", "Red"}:
            continue
        side = "ataque" if team_by_puuid[puuid] == attacking else "defesa"
        yield nearest_callout(location["x"], location["y"], map_meta), side


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


def build_deaths_table(data_dir=DEFAULT_DATA_DIR, match_ids=None):
    from data_quality import eligible_match_ids
    if match_ids is None:
        match_ids = eligible_match_ids(data_dir)
    maps_by_url = load_maps_by_url()
    matches_with_meta = []
    for match_file in find_match_files(data_dir):
        match = load_match(match_file)
        if match_ids is not None and match["matchInfo"]["matchId"] not in match_ids:
            continue
        matches_with_meta.append((match, match_file, maps_by_url.get(match["matchInfo"]["mapId"])))
    rows = []
    for match, match_file, map_meta in matches_with_meta:
        rows += death_rows(match, match_file, map_meta)
    deaths = pd.DataFrame(rows, columns=DEATH_COLUMNS)
    agents_by_id = load_agents_by_id()
    deaths["agente"] = deaths["personagem"].map(lambda character: agents_by_id.get(character, {}).get("agente", "?"))
    deaths["funcao"] = deaths["personagem"].map(lambda character: agents_by_id.get(character, {}).get("funcao", "?"))
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
    valid = deaths["diagnostico_tatico"].eq(True) if "diagnostico_tatico" in deaths else pd.Series(True, index=deaths.index)
    deaths_with_allies = deaths[valid & (deaths["aliados_vivos"] > 0)].copy()
    deaths_with_allies["isolada"] = deaths_with_allies["dist_aliado_mais_proximo"] > solo_distance
    separated = deaths_with_allies.get("aliados_mesma_regiao", pd.Series(False, index=deaths_with_allies.index)).eq(True) & (deaths_with_allies["aliados_vivos"] >= 2)
    deaths_with_allies["contexto"] = "isolado"
    deaths_with_allies.loc[separated, "contexto"] = "flanco"
    deaths_with_allies.loc[~deaths_with_allies["isolada"], "contexto"] = "em grupo"
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
    return pd.cut(deaths_with_allies["dist_aliado_mais_proximo"], DISTANCE_BANDS, labels=DISTANCE_BAND_LABELS, include_lowest=True)


def summary_by_distance_band(deaths_with_allies, group_columns=()):
    """Por faixa de distância ao aliado mais próximo: quantas mortes, quantas trocadas e quantas em rounds vencidos."""
    return deaths_with_allies.groupby([*group_columns, distance_bands(deaths_with_allies)], observed=True).agg(
        mortes=("vitima", "size"),
        fracao_trocadas=("trocada", "mean"),
        venceu_round=("venceu_round", "mean"),
    ).round(3)


def first_death_summary(deaths_with_allies, group_columns=()):
    """Primeira morte do round, isolada ou não e trocada ou não: quanto o time da vítima ainda venceu o round."""
    first_deaths = deaths_with_allies[deaths_with_allies["primeira_vitima_unica"].eq(True)] if "primeira_vitima_unica" in deaths_with_allies else deaths_with_allies[deaths_with_allies["ordem_da_morte"] == 1]
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
    """Por lado e situação (aliados x inimigos vivos): vitória do round sem e com a condição. Comparação descritiva estratificada por vivos; não estima efeito causal."""
    rows = []
    for (side, allies, enemies), cell in deaths_with_allies.groupby(["lado", "aliados_vivos", "inimigos_vivos"]):
        with_flag, without_flag = cell[cell[flag_column]], cell[~cell[flag_column]]
        if len(cell) < min_deaths or len(with_flag) < min_each_group or len(without_flag) < min_each_group:
            continue
        rows.append({"lado": side, "situacao": f"{allies}v{enemies}", "mortes": len(cell), "sem": without_flag["venceu_round"].mean(), "com": with_flag["venceu_round"].mean()})
    table = pd.DataFrame(rows, columns=["lado", "situacao", "mortes", "sem", "com"])
    table["diferenca"] = table["com"] - table["sem"]
    return table.round(2)


def territory_summary(deaths_with_allies, group_columns=()):
    return deaths_with_allies.groupby([*group_columns, "territorio"]).agg(mortes=("vitima", "size"), trocada=("trocada", "mean"), venceu_round=("venceu_round", "mean")).round(3)


if __name__ == "__main__":
    main()
