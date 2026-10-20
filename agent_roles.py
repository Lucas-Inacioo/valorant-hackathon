"""Função do agente que morreu: a primeira morte e a morte isolada pesam igual para duelista, iniciador, controlador e sentinela?

Uso: python agent_roles.py
"""
import math

import pandas as pd

from first_blood import wilson_interval
from solo_deaths import SOLO_DISTANCE, build_deaths_table, with_solo_flag

ROLE_ORDER = ["duelista", "iniciador", "controlador", "sentinela"]
SIDE_PHRASE = {"ataque": "no ataque", "defesa": "na defesa"}
SIDE_ROLE_INDEX = pd.MultiIndex.from_product([["ataque", "defesa"], ROLE_ORDER], names=["lado", "funcao"])
MIN_ROUNDS_PER_AGENT = 30


def with_interval(table, rate_column, count_column):
    """Wilson descritivo; dependência entre rounds não é incorporada."""
    intervals = [wilson_interval(round(rate * count), count) if pd.notna(rate) and pd.notna(count) and count > 0 else (math.nan, math.nan) for rate, count in zip(table[rate_column], table[count_column])]
    table["ic95_baixo"] = [low for low, _ in intervals]
    table["ic95_alto"] = [high for _, high in intervals]
    return table


def known_roles(deaths):
    return deaths[deaths["funcao"].isin(ROLE_ORDER)]


def first_deaths(deaths, max_seconds=None):
    first_flag = deaths["primeira_vitima_unica"].eq(True) if "primeira_vitima_unica" in deaths else deaths["ordem_da_morte"].eq(1)
    first = known_roles(deaths[first_flag]).copy()
    if max_seconds is not None:
        first = first[first["segundos"] <= max_seconds]
    first["acima_do_time"] = first["venceu_round"].astype(float) - (first["rounds_do_time_sem_round"] if "rounds_do_time_sem_round" in first else first["rounds_do_time"])
    return first


def role_share(deaths, max_seconds=None):
    """Fração de cada função entre os jogadores escalados e entre as primeiras mortes, por lado."""
    picks = known_roles(deaths).drop_duplicates(["match_id", "vitima"])["funcao"].value_counts(normalize=True)
    shares = pd.DataFrame({"escalações": picks})
    for side, side_first in first_deaths(deaths, max_seconds).groupby("lado"):
        shares[f"primeira morte {SIDE_PHRASE[side]}"] = side_first["funcao"].value_counts(normalize=True)
    columns = ["escalações", "primeira morte no ataque", "primeira morte na defesa"]
    return shares.reindex(index=ROLE_ORDER, columns=columns).round(3)


def first_death_by_role(deaths, max_seconds=None):
    """Por lado e função da vítima: rounds, troca, vitória do time da vítima com intervalo, e desvio descritivo da taxa do time nos demais rounds da mesma partida; não é controle independente."""
    table = first_deaths(deaths, max_seconds).groupby(["lado", "funcao"]).agg(rounds=("vitima", "size"), trocada=("trocada", "mean"), vitoria_da_vitima=("venceu_round", "mean"), acima_do_time=("acima_do_time", "mean"))
    return with_interval(table.reindex(SIDE_ROLE_INDEX), "vitoria_da_vitima", "rounds").round(3)


def first_death_by_role_and_trade(deaths, max_seconds=None):
    """Mesma tabela separando primeira morte trocada e não trocada: a função importa quando ninguém troca?"""
    table = first_deaths(deaths, max_seconds).groupby(["lado", "funcao", "trocada"]).agg(rounds=("vitima", "size"), vitoria_da_vitima=("venceu_round", "mean"), acima_do_time=("acima_do_time", "mean"))
    return table.unstack("trocada").rename(columns={False: "não trocada", True: "trocada"}, level="trocada").reindex(SIDE_ROLE_INDEX).round(3)


def first_death_by_agent(deaths, max_seconds=None, min_rounds=MIN_ROUNDS_PER_AGENT):
    """Por agente que morreu primeiro, só com volume: rounds, troca, vitória do time da vítima e descontada a taxa do time."""
    table = first_deaths(deaths, max_seconds).groupby(["funcao", "agente"]).agg(rounds=("vitima", "size"), trocada=("trocada", "mean"), vitoria_da_vitima=("venceu_round", "mean"), acima_do_time=("acima_do_time", "mean"))
    table = table[table["rounds"] >= min_rounds].sort_values("rounds", ascending=False)
    return with_interval(table, "vitoria_da_vitima", "rounds").round(3)


def death_cost_by_role(deaths_with_allies):
    """Toda morte com aliado vivo, por lado e função: vitória acima do esperado pela situação de vivos, acompanhada e isolada."""
    deaths_with_allies = known_roles(deaths_with_allies).copy()
    expected = deaths_with_allies.groupby(["lado", "aliados_vivos", "inimigos_vivos"])["venceu_round"].transform("mean")
    deaths_with_allies["acima_do_esperado"] = deaths_with_allies["venceu_round"].astype(float) - expected
    table = deaths_with_allies.groupby(["lado", "funcao"]).agg(mortes=("vitima", "size"), isolada=("isolada", "mean"), trocada=("trocada", "mean"), acima_do_esperado=("acima_do_esperado", "mean"))
    by_isolation = deaths_with_allies.groupby(["lado", "funcao", "isolada"])["acima_do_esperado"].mean().unstack("isolada").reindex(columns=[False, True])
    table["acompanhada"] = by_isolation[False]
    table["isolada_acima_do_esperado"] = by_isolation[True]
    table["custo_do_isolamento"] = table["isolada_acima_do_esperado"] - table["acompanhada"]
    return table.reindex(SIDE_ROLE_INDEX).round(3)


def main():
    deaths = build_deaths_table()
    shares = role_share(deaths)
    assert abs(shares["escalações"].sum() - 1) < 0.01, shares
    print(f"Mortes: {len(deaths)}, sem agente conhecido: {(~deaths['funcao'].isin(ROLE_ORDER)).sum()}\n")
    print("Fração de cada função nas escalações e nas primeiras mortes:")
    print(shares.to_string(), "\n")
    for label, max_seconds in [("todas", None), ("até 20 s", 20)]:
        print(f"Primeira morte por lado e função da vítima ({label}):")
        print(first_death_by_role(deaths, max_seconds).to_string(), "\n")
    print("Primeira morte por lado, função e troca:")
    print(first_death_by_role_and_trade(deaths).to_string(), "\n")
    print("Primeira morte por agente (30+ rounds):")
    print(first_death_by_agent(deaths).to_string(), "\n")
    print("Qualquer morte por função, descontada a situação de vivos, acompanhada x isolada:")
    print(death_cost_by_role(with_solo_flag(deaths, SOLO_DISTANCE)).to_string())


if __name__ == "__main__":
    main()
