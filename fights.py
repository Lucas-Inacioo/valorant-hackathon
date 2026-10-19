"""Detalhes de cada morte: a troca era possível, a que distância e com que arma, se a vítima reagiu, e quanto ela custava.

Uso: python fights.py
"""
import math

import pandas as pd

from explore_fields import DEFAULT_DATA_DIR, find_match_files, load_match
from maps import load_weapons_by_id
from round_map import round_events
from solo_deaths import build_deaths_table, distance

# Aliado a até 20 m do killer e com o olhar a até 45 graus dele estava em condição de trocar
TRADE_RANGE = 2000
FACING_DEGREES = 45
DISTANCE_BANDS = [0, 1000, 2500, float("inf")]
DISTANCE_LABELS = ["curta (até 10 m)", "média (10 a 25 m)", "longa (25 m+)"]
SHORT_RANGE_CATEGORIES = {"SMG", "shotgun"}
TRADE_POSSIBLE = "aliado em alcance olhando para o killer"
NON_WEAPON_LABELS = {"Ability": "habilidade", "Bomb": "spike", "Fall": "queda", "Melee": "faca"}
HALF_END_ROUNDS = {12, 24}


def facing_angle(viewer, target_location):
    """Graus entre o olhar do jogador e a direção até o alvo. viewRadians é atan2(dy, dx) nas coordenadas de jogo, calibrado nas kills com erro mediano de 0,3 grau."""
    direction = math.atan2(target_location["y"] - viewer["location"]["y"], target_location["x"] - viewer["location"]["x"])
    return abs(math.degrees((viewer["viewRadians"] - direction + math.pi) % (2 * math.pi) - math.pi))


def trade_possibility(in_range, facing):
    if not in_range:
        return "sem aliado em alcance"
    if not facing:
        return "aliado em alcance olhando para outro lado"
    return "aliado em alcance olhando para o killer"


def fight_class(assists, damage_to_killer):
    """Foco quando dois ou mais inimigos feriram a vítima, duelo quando a vítima feriu o killer, sem reação no resto."""
    if assists:
        return "foco de time"
    if damage_to_killer:
        return "duelo"
    return "sem reação"


def fight_rows(match, weapons_by_id):
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    rows = []
    for round_result in match["roundResults"]:
        economy_by_puuid = {stats["puuid"]: stats["economy"] for stats in round_result["playerStats"]}
        damage_by_pair = {(stats["puuid"], hit["receiver"]): hit["damage"] for stats in round_result["playerStats"] for hit in stats["damage"]}
        loadout_by_team = {}
        for puuid, economy in economy_by_puuid.items():
            loadout_by_team.setdefault(team_by_puuid[puuid], []).append(economy["loadoutValue"])
        for kill in [event for event in round_events(round_result) if event["kind"] == "kill"]:
            victim, killer = kill["victim"], kill["actor"]
            victim_team = team_by_puuid[victim]
            killer_location = next((alive["location"] for alive in kill["locations"] if alive["puuid"] == killer), None)
            allies = [alive for alive in kill["locations"] if team_by_puuid[alive["puuid"]] == victim_team]
            in_range = [ally for ally in allies if killer_location and distance(ally["location"], killer_location) <= TRADE_RANGE]
            facing = [ally for ally in in_range if facing_angle(ally, killer_location) <= FACING_DEGREES]
            victim_weapon = weapons_by_id.get(economy_by_puuid[victim]["weapon"].upper(), {"arma": "?", "custo": 0, "categoria": "?"})
            victim_loadout = economy_by_puuid[victim]["loadoutValue"]
            teammates_loadout = [loadout for puuid, loadout in zip(economy_by_puuid, [economy_by_puuid[p]["loadoutValue"] for p in economy_by_puuid]) if team_by_puuid[puuid] == victim_team and puuid != victim]
            finishing = kill["finishing"]
            damage_to_killer = damage_by_pair.get((victim, killer), 0)
            rows.append({
                "match_id": match["matchInfo"]["matchId"],
                "round": round_result["roundNum"] + 1,
                "vitima": victim,
                "segundos": kill["time_ms"] / 1000,
                "dist_killer": distance(kill["victim_location"], killer_location) if killer_location else math.nan,
                "tipo_morte": finishing["damageType"],
                "arma_killer": weapons_by_id.get(finishing["damageItem"].upper(), {}).get("arma", NON_WEAPON_LABELS.get(finishing["damageType"], "arma de agente")),
                "arma_vitima": victim_weapon["arma"],
                "categoria_vitima": victim_weapon["categoria"],
                "loadout_vitima": victim_loadout,
                "mais_caro_do_time": victim_loadout > max(teammates_loadout, default=0),
                "dano_no_killer": damage_to_killer,
                "assistencias": len(kill["assistants"]),
                "aliados_em_alcance": len(in_range),
                "aliados_olhando_killer": len(facing),
                "troca_possivel": trade_possibility(in_range, facing) if killer_location else "?",
                "classe_luta": fight_class(kill["assistants"], damage_to_killer),
            })
    return rows


def build_fights_table(deaths=None, data_dir=DEFAULT_DATA_DIR):
    """A tabela de mortes com as colunas de luta. Recebe a tabela de mortes pronta para não recalcular."""
    weapons_by_id = load_weapons_by_id()
    rows = []
    for match_file in find_match_files(data_dir):
        rows += fight_rows(load_match(match_file), weapons_by_id)
    deaths = build_deaths_table(data_dir) if deaths is None else deaths
    # A chave leva o tempo porque um jogador ressuscitado morre duas vezes no mesmo round
    fights = deaths.merge(pd.DataFrame(rows), on=["match_id", "round", "vitima", "segundos"], how="left")
    fights["faixa_distancia"] = pd.cut(fights["dist_killer"], DISTANCE_BANDS, labels=DISTANCE_LABELS)
    fights["arma_curta_em_duelo_longo"] = fights["categoria_vitima"].isin(SHORT_RANGE_CATEGORIES) & (fights["dist_killer"] >= DISTANCE_BANDS[2])
    fights["sniper_em_duelo_curto"] = (fights["categoria_vitima"] == "sniper") & (fights["dist_killer"] <= DISTANCE_BANDS[1])
    return fights


def trade_possibility_summary(fights, group_columns=()):
    """Por condição de troca: mortes, quantas foram trocadas e quanto o time da vítima venceu."""
    known = fights[fights["troca_possivel"] != "?"]
    return known.groupby([*group_columns, "troca_possivel"]).agg(mortes=("vitima", "size"), trocada=("trocada", "mean"), venceu_round=("venceu_round", "mean")).round(3)


def distance_summary(fights):
    """Por categoria da arma da vítima: mortes por arma, distância mediana do killer, fração de duelos longos, troca e vitória."""
    weapon_deaths = fights[(fights["tipo_morte"] == "Weapon") & fights["dist_killer"].notna()].copy()
    weapon_deaths["longa"] = weapon_deaths["dist_killer"] >= DISTANCE_BANDS[2]
    return weapon_deaths.groupby("categoria_vitima").agg(mortes=("vitima", "size"), dist_mediana=("dist_killer", "median"), duelo_longo=("longa", "mean"), trocada=("trocada", "mean"), venceu_round=("venceu_round", "mean")).sort_values("mortes", ascending=False).round(3)


def distance_matrix(fights):
    """Fração das mortes de cada categoria de arma por faixa de distância do killer."""
    weapon_deaths = fights[(fights["tipo_morte"] == "Weapon") & fights["dist_killer"].notna()]
    return pd.crosstab(weapon_deaths["categoria_vitima"], weapon_deaths["faixa_distancia"], normalize="index").round(3)


def player_range_discipline(fights, name_by_puuid, min_deaths=10):
    """Duas tabelas por jogador: mortes com SMG ou shotgun e a fração em duelo longo, mortes com sniper e a fração em duelo curto."""
    weapon_deaths = fights[(fights["tipo_morte"] == "Weapon") & fights["dist_killer"].notna()]
    short = weapon_deaths[weapon_deaths["categoria_vitima"].isin(SHORT_RANGE_CATEGORIES)].groupby("vitima").agg(mortes_arma_curta=("vitima", "size"), em_duelo_longo=("arma_curta_em_duelo_longo", "mean"))
    snipers = weapon_deaths[weapon_deaths["categoria_vitima"] == "sniper"].groupby("vitima").agg(mortes_sniper=("vitima", "size"), em_duelo_curto=("sniper_em_duelo_curto", "mean"))
    tables = []
    for table, count_column, rate_column in [(short, "mortes_arma_curta", "em_duelo_longo"), (snipers, "mortes_sniper", "em_duelo_curto")]:
        table = table[table[count_column] >= min_deaths].copy()
        table.insert(0, "jogador", table.index.map(name_by_puuid))
        tables.append(table.sort_values(rate_column, ascending=False).round(3))
    return tables


def team_summary(fights, min_deaths=150):
    """Por time (colunas nome_time e nome_killer já resolvidas): trocas possíveis e convertidas nas próprias mortes, mortes sem reação, e kills em foco."""
    known = fights[fights["troca_possivel"] != "?"]
    possible = known[known["troca_possivel"] == TRADE_POSSIBLE]
    table = known.groupby("nome_time").agg(mortes=("vitima", "size"), troca_possivel=("troca_possivel", lambda values: (values == TRADE_POSSIBLE).mean()), sem_reacao=("classe_luta", lambda values: (values == "sem reação").mean()))
    table["troca_convertida"] = possible.groupby("nome_time")["trocada"].mean()
    table["kills_em_foco"] = fights.groupby("nome_killer")["classe_luta"].agg(lambda values: (values == "foco de time").mean())
    return table[table["mortes"] >= min_deaths].sort_values("troca_convertida", ascending=False).round(3)


def fight_class_summary(fights, group_columns=()):
    return fights.groupby([*group_columns, "classe_luta"]).agg(mortes=("vitima", "size"), dist_killer=("dist_killer", "median"), trocada=("trocada", "mean"), venceu_round=("venceu_round", "mean")).round(3)


def economic_first_death(fights, flag_column):
    """Primeira morte do round com e sem a condição (jogador mais caro do time, Operator): troca, vitória e vitória descontada a taxa do time."""
    first = fights[fights["ordem_da_morte"] == 1].copy()
    first["acima_do_time"] = first["venceu_round"].astype(float) - first["rounds_do_time"]
    return first.groupby(["lado", flag_column]).agg(rounds=("vitima", "size"), loadout_vitima=("loadout_vitima", "mean"), trocada=("trocada", "mean"), vitoria_da_vitima=("venceu_round", "mean"), acima_do_time=("acima_do_time", "mean")).round(3)


def save_effect(rounds, deaths):
    """Rounds perdidos fora do fim de metade: sobreviventes do time contra loadout e vitória do round seguinte."""
    deaths_per_round = deaths.groupby(["match_id", "round", "time_vitima"])["vitima"].nunique().rename("mortes")
    rounds = rounds.merge(deaths_per_round, left_on=["match_id", "round", "time"], right_index=True, how="left").fillna({"mortes": 0})
    rounds = rounds.sort_values(["match_id", "time", "round"])
    by_team = rounds.groupby(["match_id", "time"])
    rounds["loadout_seguinte"] = by_team["loadout"].shift(-1)
    rounds["venceu_seguinte"] = by_team["venceu"].shift(-1)
    rounds["sobreviventes"] = (5 - rounds["mortes"]).astype(int)
    lost = rounds[~rounds["venceu"] & rounds["loadout_seguinte"].notna() & ~rounds["round"].isin(HALF_END_ROUNDS)]
    return lost.groupby("sobreviventes").agg(rounds=("venceu", "size"), loadout=("loadout", "mean"), loadout_seguinte=("loadout_seguinte", "mean"), venceu_seguinte=("venceu_seguinte", "mean")).round(3)


def main():
    fights = build_fights_table()
    print(f"Mortes: {len(fights)}, com posição do killer: {fights['dist_killer'].notna().sum()}\n")
    print("Troca possível, por lado:")
    print(trade_possibility_summary(fights, ["lado"]).to_string(), "\n")
    print("Distância por categoria da arma da vítima:")
    print(distance_summary(fights).to_string(), "\n")
    print(distance_matrix(fights).to_string(), "\n")
    print("Classe da luta, por lado:")
    print(fight_class_summary(fights, ["lado"]).to_string(), "\n")
    print("Primeira morte do jogador mais caro do time:")
    print(economic_first_death(fights, "mais_caro_do_time").to_string(), "\n")
    fights["operator"] = fights["arma_vitima"] == "Operator"
    print("Primeira morte de quem tem Operator:")
    print(economic_first_death(fights, "operator").to_string(), "\n")
    from economy import build_rounds_table
    print("Sobreviventes de um round perdido e o round seguinte:")
    print(save_effect(build_rounds_table(), fights).to_string())


if __name__ == "__main__":
    main()
