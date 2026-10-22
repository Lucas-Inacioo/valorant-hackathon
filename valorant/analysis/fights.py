"""Dano agregado no round, equipamento inicial e proxies geométricas nas mortes.

Uso: python -m valorant.analysis.fights
"""

import math
from collections import defaultdict

import pandas as pd

from valorant.data.fields import DEFAULT_DATA_DIR
from valorant.data.quality import eligible_match_ids, iter_selected_matches
from valorant.analysis.events import alive_puuids, final_alive_puuids, round_events
from valorant.analysis.deaths import build_deaths_table, distance

# Proximidade e direção não verificam linha de tiro, paredes, smokes ou recarga.
TRADE_RANGE = 2000
FACING_DEGREES = 45
TRADE_POSSIBLE = "proximidade e direção compatíveis"
MULTIPLE_DAMAGE = "dano de múltiplos adversários no round"
SINGLE_DAMAGE = "dano de um adversário no round"
NO_DAMAGE = "sem dano adversário registrado no round"
HALF_END_ROUNDS = {12, 24}


def facing_angle(viewer, target_location):
    """Graus entre o olhar do jogador e a direção até o alvo. viewRadians é atan2(dy, dx) nas coordenadas de jogo, calibrado nas kills com erro mediano de 0,3 grau."""
    if viewer.get("viewRadians") is None:
        return math.nan
    direction = math.atan2(
        target_location["y"] - viewer["location"]["y"],
        target_location["x"] - viewer["location"]["x"],
    )
    return abs(
        math.degrees((viewer["viewRadians"] - direction + math.pi) % (2 * math.pi) - math.pi)
    )


def trade_possibility(in_range, facing):
    if not in_range:
        return "sem aliado em alcance"
    if not facing:
        return "aliado em alcance olhando para outro lado"
    return TRADE_POSSIBLE


def fight_class(enemy_damage_sources):
    """Fontes distintas de dano no round; não identifica simultaneidade ou reação."""
    if enemy_damage_sources >= 2:
        return MULTIPLE_DAMAGE
    return SINGLE_DAMAGE if enemy_damage_sources == 1 else NO_DAMAGE


def aggregate_damage(round_result):
    damage = defaultdict(float)
    for stats in round_result.get("playerStats", []):
        for hit in stats.get("damage", []):
            damage[stats["puuid"], hit["receiver"]] += hit.get("damage", 0)
    return dict(damage)


def tactical_fights(fights):
    return (
        fights[fights["diagnostico_tatico"].eq(True)] if "diagnostico_tatico" in fights else fights
    )


def fight_coverage(fights):
    tactical = tactical_fights(fights)
    return {
        "mortes_brutas": len(fights),
        "mortes_diagnostico": len(tactical),
        "mortes_excluidas": len(fights) - len(tactical),
        "com_posicao_autor": int(tactical["dist_killer"].notna().sum()),
        "com_proxy_geometrica": int(tactical["troca_possivel"].ne("?").sum()),
    }


def fight_rows(match):
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    rows = []
    for round_result in match["roundResults"]:
        economy_by_puuid = {
            stats["puuid"]: stats["economy"] for stats in round_result["playerStats"]
        }
        damage_by_pair = aggregate_damage(round_result)
        loadout_by_team = {}
        for puuid, economy in economy_by_puuid.items():
            loadout_by_team.setdefault(team_by_puuid[puuid], []).append(economy["loadoutValue"])
        for kill in [
            event for event in round_events(round_result, team_by_puuid) if event["kind"] == "kill"
        ]:
            victim, killer = kill["victim"], kill["actor"]
            victim_team = team_by_puuid[victim]
            killer_location = next(
                (alive["location"] for alive in kill["locations"] if alive["puuid"] == killer), None
            )
            allies = [
                alive
                for alive in kill["locations"]
                if alive["puuid"] in alive_puuids(kill)
                and team_by_puuid.get(alive["puuid"]) == victim_team
                and alive["puuid"] != victim
            ]
            in_range = [
                ally
                for ally in allies
                if killer_location and distance(ally["location"], killer_location) <= TRADE_RANGE
            ]
            facing = [
                ally for ally in in_range if facing_angle(ally, killer_location) <= FACING_DEGREES
            ]
            victim_loadout = economy_by_puuid[victim]["loadoutValue"]
            teammates_loadout = [
                loadout
                for puuid, loadout in zip(
                    economy_by_puuid,
                    [economy_by_puuid[p]["loadoutValue"] for p in economy_by_puuid],
                )
                if team_by_puuid[puuid] == victim_team and puuid != victim
            ]
            finishing = kill["finishing"]
            damage_to_killer = damage_by_pair.get((victim, killer), 0)
            damage_sources = {
                actor
                for (actor, receiver), amount in damage_by_pair.items()
                if receiver == victim
                and amount > 0
                and team_by_puuid.get(actor) in {"Blue", "Red"}
                and team_by_puuid.get(actor) != victim_team
            }
            rows.append(
                {
                    "match_id": match["matchInfo"]["matchId"],
                    "round": round_result["roundNum"] + 1,
                    "vitima": victim,
                    "event_id": kill["event_id"],
                    "segundos": kill["time_ms"] / 1000,
                    "dist_killer": (
                        distance(kill["victim_location"], killer_location)
                        if killer_location
                        else math.nan
                    ),
                    "tipo_morte": finishing["damageType"],
                    "loadout_vitima": victim_loadout,
                    "mais_caro_do_time": victim_loadout > max(teammates_loadout, default=0),
                    "dano_no_killer": damage_to_killer,
                    "dano_no_killer_registrado": damage_to_killer > 0,
                    "fontes_dano_adversario_round": len(damage_sources),
                    "assistencias": len(kill["assistants"]),
                    "aliados_em_alcance": len(in_range),
                    "aliados_olhando_killer": len(facing),
                    "troca_possivel": (
                        trade_possibility(in_range, facing)
                        if killer_location
                        and not any(ally.get("viewRadians") is None for ally in in_range)
                        else "?"
                    ),
                    "classe_luta": (
                        fight_class(len(damage_sources))
                        if kill["tactical_valid"]
                        else "fora do diagnóstico tático"
                    ),
                    "exclusao_diagnostico": (
                        "após decisão do round"
                        if kill["after_decision"]
                        else (
                            "evento sem abate adversário tático"
                            if not kill["tactical_valid"]
                            else ""
                        )
                    ),
                }
            )
    return rows


def build_fights_table(deaths=None, data_dir=DEFAULT_DATA_DIR, match_ids=None):
    """A tabela de mortes com as colunas de luta. Recebe a tabela de mortes pronta para não recalcular."""
    match_ids = eligible_match_ids(data_dir) if match_ids is None else set(match_ids)
    rows = []
    for _, match in iter_selected_matches(data_dir, match_ids):
        rows += fight_rows(match)
    deaths = build_deaths_table(data_dir, match_ids=match_ids) if deaths is None else deaths
    if match_ids is not None:
        deaths = deaths[deaths["match_id"].isin(match_ids)]
    columns = [
        "match_id",
        "round",
        "vitima",
        "event_id",
        "segundos",
        "dist_killer",
        "tipo_morte",
        "loadout_vitima",
        "mais_caro_do_time",
        "dano_no_killer",
        "dano_no_killer_registrado",
        "fontes_dano_adversario_round",
        "assistencias",
        "aliados_em_alcance",
        "aliados_olhando_killer",
        "troca_possivel",
        "classe_luta",
        "exclusao_diagnostico",
    ]
    details = pd.DataFrame(rows, columns=columns)
    keys = ["match_id", "round", "vitima", "segundos"]
    if "event_id" in deaths:
        keys.append("event_id")
    else:
        details = details.drop(columns="event_id")
    fights = deaths.merge(details, on=keys, how="left", validate="one_to_one")
    return fights


def trade_possibility_summary(fights, group_columns=()):
    """Por condição de troca: mortes, quantas foram trocadas e quanto o time da vítima venceu."""
    fights = tactical_fights(fights)
    known = fights[fights["troca_possivel"] != "?"]
    return (
        known.groupby([*group_columns, "troca_possivel"])
        .agg(
            mortes=("vitima", "size"),
            trocada=("trocada", "mean"),
            venceu_round=("venceu_round", "mean"),
        )
        .round(3)
    )


def team_summary(fights, min_deaths=150):
    """Proxies por time; assistência e dano agregado não identificam um confronto."""
    fights = tactical_fights(fights)
    known = fights[fights["troca_possivel"] != "?"]
    possible = known[known["troca_possivel"] == TRADE_POSSIBLE]
    table = fights.groupby("nome_time").agg(
        mortes=("vitima", "size"),
        sem_dano_no_autor=("dano_no_killer", lambda values: (values == 0).mean()),
    )
    table["mortes_com_geometria"] = known.groupby("nome_time").size()
    table["troca_possivel"] = known.groupby("nome_time")["troca_possivel"].agg(
        lambda values: (values == TRADE_POSSIBLE).mean()
    )
    table["troca_convertida"] = possible.groupby("nome_time")["trocada"].mean()
    table["multiplas_fontes_dano_round"] = fights.groupby("nome_killer")["classe_luta"].agg(
        lambda values: (values == MULTIPLE_DAMAGE).mean()
    )
    return (
        table[table["mortes"] >= min_deaths]
        .sort_values("troca_convertida", ascending=False)
        .round(3)
    )


def fight_class_summary(fights, group_columns=()):
    fights = tactical_fights(fights)
    return (
        fights.groupby([*group_columns, "classe_luta"])
        .agg(
            mortes=("vitima", "size"),
            dist_killer=("dist_killer", "median"),
            trocada=("trocada", "mean"),
            venceu_round=("venceu_round", "mean"),
        )
        .round(3)
    )


def economic_first_death(fights, flag_column):
    """Primeira morte do round com e sem a condição (jogador mais caro do time, Operator): troca, vitória e vitória descontada a taxa do time."""
    fights = tactical_fights(fights)
    first = (
        fights[fights["primeira_vitima_unica"].eq(True)].copy()
        if "primeira_vitima_unica" in fights
        else fights[fights["ordem_da_morte"] == 1].copy()
    )
    first["acima_do_time"] = first["venceu_round"].astype(float) - first["rounds_do_time"]
    return (
        first.groupby(["lado", flag_column])
        .agg(
            rounds=("vitima", "size"),
            loadout_vitima=("loadout_vitima", "mean"),
            trocada=("trocada", "mean"),
            vitoria_da_vitima=("venceu_round", "mean"),
            acima_do_time=("acima_do_time", "mean"),
        )
        .round(3)
    )


def final_survivors_table(data_dir=DEFAULT_DATA_DIR, match_ids=None):
    match_ids = eligible_match_ids(data_dir) if match_ids is None else set(match_ids)
    rows = []
    for _, match in iter_selected_matches(data_dir, match_ids):
        teams = {p["puuid"]: p["teamId"] for p in match["players"]}
        for result in match["roundResults"]:
            alive = final_alive_puuids(result, teams)
            for team in {"Blue", "Red"}:
                rows.append(
                    {
                        "match_id": match["matchInfo"]["matchId"],
                        "round": result["roundNum"] + 1,
                        "time": team,
                        "sobreviventes": sum(teams.get(p) == team for p in alive),
                    }
                )
    return pd.DataFrame(rows, columns=["match_id", "round", "time", "sobreviventes"])


def rounds_with_next(rounds, deaths=None, data_dir=DEFAULT_DATA_DIR):
    """Médias observacionais de continuidade econômica em regulação, sem resets.

    Ressurreições são reconhecidas pelos snapshots finais; o dano bruto não é
    suficiente para contar sobreviventes. Overtime tem outro regime econômico.
    """
    rounds = rounds.copy()
    if "sobreviventes" not in rounds:
        survivors = final_survivors_table(data_dir, set(rounds["match_id"]))
        rounds = rounds.merge(
            survivors, on=["match_id", "round", "time"], how="left", validate="one_to_one"
        )
    rounds = rounds.sort_values(["match_id", "time", "round"])
    by_team = rounds.groupby(["match_id", "time"])
    rounds["loadout_seguinte"] = by_team["loadout"].shift(-1)
    rounds["venceu_seguinte"] = by_team["venceu"].shift(-1)
    rounds["round_seguinte"] = by_team["round"].shift(-1)
    return rounds[
        rounds["loadout_seguinte"].notna()
        & rounds["sobreviventes"].notna()
        & (rounds["round_seguinte"] == rounds["round"] + 1)
        & (rounds["round"] < 24)
        & (rounds["round"] != 12)
    ].copy()


def save_effect(rounds, deaths=None, data_dir=DEFAULT_DATA_DIR):
    """Rounds perdidos fora do fim de metade: sobreviventes do time contra loadout e vitória do round seguinte."""
    lost = rounds_with_next(rounds, deaths, data_dir).query("~venceu")
    return (
        lost.groupby("sobreviventes")
        .agg(
            rounds=("venceu", "size"),
            loadout=("loadout", "mean"),
            loadout_seguinte=("loadout_seguinte", "mean"),
            venceu_seguinte=("venceu_seguinte", "mean"),
        )
        .round(3)
    )


def next_loadout_by_outcome(rounds, deaths=None, min_rounds=20, data_dir=DEFAULT_DATA_DIR):
    """Loadout do round seguinte por sobreviventes, vencedor e perdedor do round lado a lado, com a contagem de rounds."""
    table = rounds_with_next(rounds, deaths, data_dir).query("sobreviventes <= 4")
    table["resultado_round"] = table["venceu"].map(
        {True: "venceu o round", False: "perdeu o round"}
    )
    grouped = table.groupby(["sobreviventes", "resultado_round"]).agg(
        rounds=("venceu", "size"), loadout_seguinte=("loadout_seguinte", "mean")
    )
    grouped = grouped[grouped["rounds"] >= min_rounds]
    loadouts = (
        grouped["loadout_seguinte"]
        .unstack("resultado_round")
        .reindex(columns=["venceu o round", "perdeu o round"])
        .round(0)
    )
    counts = (
        grouped["rounds"]
        .unstack("resultado_round")
        .reindex(columns=["venceu o round", "perdeu o round"])
    )
    return loadouts, counts


def post_plant_exchange(plants, deaths, min_rounds=30):
    """Mortes brutas pós-plant em vitórias do ataque; não identifica quem caçou.

    Inclui eventos após a decisão, relevantes à perda de equipamento, e conta
    mortes repetidas após retorno à vida. Não estima retorno causal de caçar.
    """
    if "plant_valido" in plants:
        plants = plants[plants["plant_valido"].eq(True)]
    won = plants[plants["ataque_venceu"]][["match_id", "round", "situacao", "segundos_plant"]]
    post = deaths.merge(won, on=["match_id", "round"], suffixes=("", "_plant"))
    post = post[post["segundos"] > post["segundos_plant_plant"]]
    by_round = (
        post.groupby(["match_id", "round", "situacao", "lado"])["vitima"]
        .size()
        .unstack("lado")
        .reindex(columns=["ataque", "defesa"])
        .fillna(0)
    )
    table = by_round.groupby("situacao").agg(
        mortes_ataque=("ataque", "sum"), mortes_defesa=("defesa", "sum")
    )
    table["rounds"] = won.groupby("situacao").size()
    table["mortes_pos_plant"] = (table["mortes_ataque"] + table["mortes_defesa"]).astype(int)
    table["parte_do_ataque"] = (table["mortes_ataque"] / table["mortes_pos_plant"]).round(3)
    table = table[(table["rounds"] >= min_rounds) & (table["mortes_pos_plant"] > 0)]
    table["ordem"] = table.index.map(
        lambda situation: tuple(-int(part) for part in situation.split("v")[::-1])
    )
    return table.sort_values("ordem").drop(columns="ordem")


def main():
    fights = build_fights_table()
    print(f"Mortes: {len(fights)}, com posição do killer: {fights['dist_killer'].notna().sum()}\n")
    print("Proximidade e direção compatíveis, por lado:")
    print(trade_possibility_summary(fights, ["lado"]).to_string(), "\n")
    print("Classe da luta, por lado:")
    print(fight_class_summary(fights, ["lado"]).to_string(), "\n")
    print("Primeira morte do jogador mais caro do time:")
    print(economic_first_death(fights, "mais_caro_do_time").to_string(), "\n")
    from valorant.analysis.economy import build_rounds_table

    print("Sobreviventes de um round perdido e o round seguinte:")
    print(save_effect(build_rounds_table(), fights).to_string())


if __name__ == "__main__":
    main()
