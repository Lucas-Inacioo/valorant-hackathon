"""Economia por round: quanto o loadout compra de vitória, e o que acontece depois de perder um round.

Uso: python -m valorant.analysis.economy
"""

import math

import pandas as pd

from valorant.data.fields import DEFAULT_DATA_DIR, find_match_files, load_match
from valorant.analysis.prediction import attacking_team_by_round

OTHER_TEAM = {"Blue": "Red", "Red": "Blue"}
LOADOUT_BINS = [-math.inf, 4000, 8000, 12000, 16000, 20000, math.inf]
LOADOUT_LABELS = ["até 4k", "(4k, 8k]", "(8k, 12k]", "(12k, 16k]", "(16k, 20k]", "> 20k"]
DIFF_BINS = [-math.inf, -10000, -5000, -2000, 2000, 5000, 10000, math.inf]
DIFF_LABELS = ["≤ -10k", "(-10k, -5k]", "(-5k, -2k]", "(-2k, 2k]", "(2k, 5k]", "(5k, 10k]", "> 10k"]
EASY_LOSS_CEREMONIES = {"CeremonyClutch", "CeremonyThrifty"}


def round_rows(match, match_file):
    """Uma linha por round e time: loadout, gasto, sobra, resultado, cerimônia e lado."""
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    from valorant.analysis.events import (
        attacking_team,
        round_events,
        alive_puuids,
        final_alive_puuids,
    )
    from valorant.analysis.plants import plant_exclusion

    attacking = {rr["roundNum"] + 1: attacking_team(rr) for rr in match["roundResults"]}
    rows = []
    for round_result in match["roundResults"]:
        totals = {
            "Blue": {"loadout": 0, "spent": 0, "remaining": 0},
            "Red": {"loadout": 0, "spent": 0, "remaining": 0},
        }
        for player_stats in round_result["playerStats"]:
            economy = player_stats["economy"]
            color = team_by_puuid.get(player_stats["puuid"])
            if color not in totals:
                continue
            team = totals[color]
            team["loadout"] += economy["loadoutValue"]
            team["spent"] += economy["spent"]
            team["remaining"] += economy["remaining"]
        round_number = round_result["roundNum"] + 1
        events = round_events(round_result, team_by_puuid)
        plant = next((event for event in events if event["kind"] == "plant"), None)
        attack = attacking.get(round_number)
        plant_valid = bool(plant and not plant_exclusion(round_result, team_by_puuid))
        alive_final = final_alive_puuids(round_result, team_by_puuid)
        for team in ["Blue", "Red"]:
            rows.append(
                {
                    "match_id": match["matchInfo"]["matchId"],
                    "arquivo": match_file.name,
                    "round": round_number,
                    "mapa_interno": match["matchInfo"]["mapId"],
                    "segundos_plant": (
                        round_result.get("plantRoundTime", 0) / 1000
                        if round_result.get("bombPlanter")
                        else math.nan
                    ),
                    "plantou_bruto": bool(round_result.get("bombPlanter")),
                    "plant_valido": plant_valid,
                    "sobreviventes": sum(team_by_puuid.get(p) == team for p in alive_final),
                    "time": team,
                    "lado": (
                        "?"
                        if attacking.get(round_number) is None
                        else ("ataque" if attacking[round_number] == team else "defesa")
                    ),
                    "loadout": totals[team]["loadout"],
                    "loadout_adversario": totals[OTHER_TEAM[team]]["loadout"],
                    "gasto": totals[team]["spent"],
                    "sobra": totals[team]["remaining"],
                    "venceu": round_result["winningTeam"] == team,
                    "cerimonia": round_result["roundCeremony"],
                    "resultado": round_result["roundResult"],
                }
            )
    return rows


def build_rounds_table(data_dir=DEFAULT_DATA_DIR, match_ids=None):
    from valorant.data.quality import eligible_match_ids

    allowed = eligible_match_ids(data_dir) if match_ids is None else set(match_ids)
    rows = []
    for match_file in find_match_files(data_dir):
        match = load_match(match_file)
        if match["matchInfo"]["matchId"] in allowed:
            rows += round_rows(match, match_file)
    columns = [
        "match_id",
        "arquivo",
        "round",
        "time",
        "lado",
        "loadout",
        "loadout_adversario",
        "gasto",
        "sobra",
        "venceu",
        "cerimonia",
        "resultado",
        "mapa_interno",
        "segundos_plant",
        "plantou_bruto",
        "plant_valido",
        "sobreviventes",
    ]
    rounds = pd.DataFrame(rows, columns=columns).sort_values(["match_id", "time", "round"])
    rounds["diferenca"] = rounds["loadout"] - rounds["loadout_adversario"]
    rounds["faixa_loadout"] = pd.cut(rounds["loadout"], LOADOUT_BINS, labels=LOADOUT_LABELS)
    rounds["faixa_diferenca"] = pd.cut(rounds["diferenca"], DIFF_BINS, labels=DIFF_LABELS)
    rounds["tipo"] = rounds["round"].map(round_type)
    rounds["metade"] = rounds["round"].map(
        lambda n: "primeira" if n <= 12 else ("segunda" if n <= 24 else f"OT {n - 24}")
    )
    by_team = rounds.groupby(["match_id", "time", "metade"])
    rounds["venceu_anterior"] = by_team["venceu"].shift(1)
    rounds["cerimonia_anterior"] = by_team["cerimonia"].shift(1)
    rounds["derrotas_seguidas"] = by_team["venceu"].transform(losing_streak_before)
    rounds["perdeu_round_facil"] = (rounds["venceu_anterior"] == False) & rounds[
        "cerimonia_anterior"
    ].isin(EASY_LOSS_CEREMONIES)
    expected = (
        rounds[rounds["tipo"] == "outro"].groupby("faixa_diferenca", observed=True)["venceu"].mean()
    )
    rounds["esperado_pelo_dinheiro"] = rounds["faixa_diferenca"].map(expected).astype(float)
    rounds["acima_do_esperado"] = rounds["venceu"].astype(float) - rounds["esperado_pelo_dinheiro"]
    return rounds


def round_type(round_number):
    if round_number in (1, 13):
        return "pistol"
    if round_number in (2, 14):
        return "segundo"
    return "outro"


def losing_streak_before(won_series):
    """Quantos rounds seguidos o time tinha perdido antes deste round."""
    streaks, streak = [], 0
    for won in won_series:
        streaks.append(streak)
        streak = 0 if won else streak + 1
    return pd.Series(streaks, index=won_series.index)


def win_rate_by_loadout(rounds):
    """Vitória por faixa de loadout do time e por faixa de diferença para o adversário."""
    own = rounds.groupby("faixa_loadout", observed=True).agg(
        rounds=("venceu", "size"), vitoria=("venceu", "mean")
    )
    difference = rounds.groupby("faixa_diferenca", observed=True).agg(
        rounds=("venceu", "size"), vitoria=("venceu", "mean")
    )
    return own.round(3), difference.round(3)


def win_rate_matrix(rounds):
    """Vitória e número de rounds por faixa de loadout do time (linhas) e do adversário (colunas), só rounds normais."""
    normal = rounds[rounds["tipo"] == "outro"]
    enemy_band = pd.cut(normal["loadout_adversario"], LOADOUT_BINS, labels=LOADOUT_LABELS)
    rates = pd.crosstab(
        normal["faixa_loadout"], enemy_band, values=normal["venceu"], aggfunc="mean"
    ).round(2)
    counts = pd.crosstab(normal["faixa_loadout"], enemy_band)
    return rates, counts


def versus_full_buy(rounds):
    """Quanto cada faixa de loadout rende contra um adversário de compra cheia (20k+), que é o caso comum."""
    normal = rounds[(rounds["tipo"] == "outro") & (rounds["loadout_adversario"] > 20000)]
    table = (
        normal.groupby("faixa_loadout", observed=True)
        .agg(
            rounds=("venceu", "size"), vitoria=("venceu", "mean"), loadout_medio=("loadout", "mean")
        )
        .round(3)
    )
    table["ganho_por_1k_a_mais"] = (
        table["vitoria"].diff() / (table["loadout_medio"].diff() / 1000)
    ).round(3)
    return table


def close_match_ids(rounds, max_gap=4):
    """Estrato retrospectivo por placar final; não é controle de força nem teste de abalo."""
    final = rounds.groupby(["match_id", "time"])["venceu"].sum().unstack()
    return set(final[(final["Blue"] - final["Red"]).abs() <= max_gap].index)


def after_previous_round(rounds):
    """Vitória no round seguinte a uma vitória, a uma derrota comum e a uma derrota em round fácil, comparando uma referência descritiva de loadout."""
    following = rounds[rounds["venceu_anterior"].notna() & (rounds["tipo"] == "outro")].copy()
    following["anterior"] = "venceu"
    following.loc[following["venceu_anterior"] == False, "anterior"] = "perdeu"
    following.loc[following["perdeu_round_facil"], "anterior"] = (
        "perdeu round fácil (clutch ou thrifty do adversário)"
    )
    return (
        following.groupby("anterior")
        .agg(
            rounds=("venceu", "size"),
            vitoria=("venceu", "mean"),
            esperado_pelo_dinheiro=("esperado_pelo_dinheiro", "mean"),
            acima_do_esperado=("acima_do_esperado", "mean"),
            diferenca_media=("diferenca", "mean"),
        )
        .round(3)
    )


def after_streak(rounds):
    """Vitória por número de derrotas seguidas antes do round, comparando uma referência descritiva de loadout."""
    normal = rounds[rounds["tipo"] == "outro"].copy()
    normal["derrotas"] = normal["derrotas_seguidas"].clip(upper=4).astype(str).replace("4", "4+")
    return (
        normal.groupby("derrotas")
        .agg(
            rounds=("venceu", "size"),
            vitoria=("venceu", "mean"),
            esperado_pelo_dinheiro=("esperado_pelo_dinheiro", "mean"),
            acima_do_esperado=("acima_do_esperado", "mean"),
            diferenca_media=("diferenca", "mean"),
        )
        .round(3)
    )


def pistol_by_side(rounds):
    pistol = rounds[(rounds["tipo"] == "pistol") & (rounds["lado"] != "?")]
    return (
        pistol.groupby("lado")
        .agg(
            rounds=("venceu", "size"), vitoria=("venceu", "mean"), loadout_medio=("loadout", "mean")
        )
        .round(3)
    )


def second_round_cycle(rounds):
    """Ciclos após perder o pistol; soma somente coortes completas, com censura explícita.

    O agrupamento geral e por lado mostra as metades separadamente. As taxas por
    offset e a soma usam os mesmos ciclos completos nos três offsets.
    A taxa prévia é apenas descritiva e nunca inclui o horizonte 2–4/14–16.
    """
    second = rounds[(rounds["tipo"] == "segundo") & (rounds["venceu_anterior"] == False)].copy()
    second["metade"] = second["round"].map({2: "primeira", 14: "segunda"})
    second["compra"] = pd.cut(
        second["loadout"],
        [-math.inf, 4000, 8000, math.inf],
        labels=["eco (até 4k)", "leve (4-8k)", "force (> 8k)"],
    )
    later = rounds[["match_id", "time", "round", "venceu", "loadout"]]
    for offset, name in [(1, "3"), (2, "4")]:
        shifted = later.copy()
        shifted["round"] -= offset
        second = second.merge(
            shifted.rename(
                columns={"venceu": f"venceu_round_{name}", "loadout": f"loadout_round_{name}"}
            ),
            on=["match_id", "time", "round"],
            how="left",
        )
    second["completo"] = second[["venceu_round_3", "venceu_round_4"]].notna().all(axis=1)
    for name, column in [("2", "venceu"), ("3", "venceu_round_3"), ("4", "venceu_round_4")]:
        second[f"vitoria_completa_{name}"] = second[column].astype(float).where(second["completo"])
    second["ganhos_completos"] = (
        second["venceu"].astype(float)
        + second["venceu_round_3"].astype(float)
        + second["venceu_round_4"].astype(float)
    ).where(second["completo"])
    prior = []
    for row in second.itertuples():
        past = rounds[
            (rounds["match_id"] == row.match_id)
            & (rounds["time"] == row.time)
            & (rounds["round"] < row.round - 1)
        ]
        prior.append(past["venceu"].mean())
    second["vitoria_anterior_ao_pistol"] = prior
    aggregations = dict(
        rounds=("venceu", "size"),
        disponiveis_round_2=("venceu", "count"),
        disponiveis_round_3=("venceu_round_3", "count"),
        disponiveis_round_4=("venceu_round_4", "count"),
        ciclos_completos=("completo", "sum"),
        loadout_medio=("loadout", "mean"),
        vitoria_disponiveis_round_2=("venceu", "mean"),
        vitoria_disponiveis_round_3=("venceu_round_3", "mean"),
        vitoria_disponiveis_round_4=("venceu_round_4", "mean"),
        vitoria_round_2=("vitoria_completa_2", "mean"),
        vitoria_round_3=("vitoria_completa_3", "mean"),
        vitoria_round_4=("vitoria_completa_4", "mean"),
        loadout_round_3=("loadout_round_3", "mean"),
        taxa_previa=("vitoria_anterior_ao_pistol", "mean"),
        rounds_ganhos_2_a_4=("ganhos_completos", "mean"),
    )
    overall = second.groupby(["metade", "compra"], observed=True).agg(**aggregations)
    by_side = (
        second[second["lado"] != "?"]
        .groupby(["metade", "lado", "compra"], observed=True)
        .agg(**aggregations)
    )
    for table in (overall, by_side):
        table["ciclos_censurados"] = table["rounds"] - table["ciclos_completos"]
    return overall.round(3), by_side.round(3)


def main():
    rounds = build_rounds_table()
    close = rounds[rounds["match_id"].isin(close_match_ids(rounds))]
    print(
        f"Rounds: {len(rounds) // 2}, partidas equilibradas (até 4 rounds de diferença): {close['match_id'].nunique()}\n"
    )
    own, difference = win_rate_by_loadout(rounds)
    print("1. Vitória por faixa de loadout do time:")
    print(own.to_string(), "\n")
    print("   Vitória por diferença de loadout (time menos adversário):")
    print(difference.to_string(), "\n")
    rates, counts = win_rate_matrix(rounds)
    print("   Vitória por loadout do time (linhas) x do adversário (colunas), rounds normais:")
    print(rates.to_string(), "\n")
    print(counts.to_string(), "\n")
    print("   Contra compra cheia (20k+):")
    print(versus_full_buy(rounds).to_string(), "\n")
    print(
        "2. Round seguinte, por o que aconteceu no anterior (todas as partidas e só as equilibradas):"
    )
    print(after_previous_round(rounds).to_string(), "\n")
    print(after_previous_round(close).to_string(), "\n")
    print("3. Pistol por lado:")
    print(pistol_by_side(rounds).to_string(), "\n")
    overall, by_side = second_round_cycle(rounds)
    print("   Perdedor do pistol, compra no round 2:")
    print(overall.to_string(), "\n")
    print(by_side.to_string(), "\n")
    print("4. Derrotas seguidas antes do round (todas as partidas e só as equilibradas):")
    print(after_streak(rounds).to_string(), "\n")
    print(after_streak(close).to_string())


if __name__ == "__main__":
    main()
