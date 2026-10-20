"""Associações observacionais e contagens de indicadores de round, sem atribuição de contribuição individual.

Uso: python factors.py
"""
import math

import numpy as np

import pandas as pd

from economy import build_rounds_table
from fights import TRADE_POSSIBLE, build_fights_table
from round_style import build_round_styles
from solo_deaths import SOLO_DISTANCE, with_solo_flag

OTHER_TEAM = {"Blue": "Red", "Red": "Blue"}
LOADOUT_GAP = 5000

# Nome do fator, descrição curta e a coluna booleana da tabela de mortes que o dispara (None para fatores do round inteiro)
DEATH_FACTORS = [
    ("proximidade e direção sem troca", "proximidade/direção compatíveis, sem abate do autor em 5 s; visibilidade e viabilidade desconhecidas", "troca_nao_feita"),
    ("morte isolada", "morreu sem aliado a menos de 10 m, com aliado vivo", "isolada"),
    ("morte separado do grupo", "ao menos dois aliados na mesma super-região, vítima distante; não comprova flanco", "flanco"),
    ("morte em território do adversário", "morreu em região onde o outro lado costuma começar o round", "no_adversario"),
    ("arma inicial curta, abate a longa distância", "loadout inicial registra SMG/shotgun; autor do abate estava a 25 m ou mais, arma no instante desconhecida", "arma_curta_em_duelo_longo"),
    ("sniper inicial, abate a curta distância", "loadout inicial registra sniper; autor do abate estava a 10 m ou menos, arma no instante desconhecida", "sniper_em_duelo_curto"),
    ("sem dano no autor registrado no round", "dano agregado do round no autor do abate é zero; não identifica reação no confronto", "sem_reacao"),
]
GOOD_DEATH_FACTORS = [
    ("morte trocada", "um aliado matou o killer em até 5 s", "trocada"),
    ("dano no autor registrado no round", "há dano agregado no autor do abate durante o round; ordem temporal desconhecida", "duelo"),
]
GOOD_ROUND_FACTORS = [
    ("fez o primeiro abate", "o primeiro a morrer no round era do adversário", "fez_abertura"),
    ("primeiro abate feito e o adversário não trocou", "o primeiro a morrer era do adversário e ninguém vingou em 5 s", "abertura_feita_nao_trocada"),
    ("adversário colapsou", "três mortes do adversário em 10 s sem nenhum abate dele no intervalo", "adversario_colapsou"),
    ("loadout 5 mil acima do adversário", "a diferença de loadout era maior que 5 mil", "loadout_acima"),
    ("ataque plantou", "no ataque, a spike foi plantada", "plantou"),
    ("execução rápida", "no ataque, a spike foi plantada em até 40 s", "execucao_rapida"),
]
ROUND_FACTORS = [
    ("perdeu o primeiro abate", "o primeiro a morrer no round era do time", "perdeu_abertura"),
    ("primeiro abate perdido e não trocado", "o primeiro a morrer era do time e ninguém vingou em 5 s", "abertura_nao_trocada"),
    ("colapso", "três mortes do time em 10 s sem nenhum abate no intervalo", "colapso"),
    ("jogador mais caro morreu primeiro", "a primeira morte do time era de quem tinha o maior loadout", "mais_caro_primeiro"),
    ("loadout 5 mil abaixo do adversário", "a diferença de loadout era menor que -5 mil", "loadout_abaixo"),
    ("ataque sem plant", "no ataque, o round terminou sem plantar a spike", "sem_plant"),
]


def flag_deaths(fights):
    """Acrescenta à tabela de lutas uma coluna booleana por fator de morte."""
    eligible = fights[fights["diagnostico_tatico"]] if "diagnostico_tatico" in fights else fights
    deaths = with_solo_flag(eligible, SOLO_DISTANCE)
    deaths["troca_nao_feita"] = (deaths["troca_possivel"] == TRADE_POSSIBLE) & ~deaths["trocada"]
    deaths["flanco"] = deaths["contexto"] == "flanco"
    deaths["no_adversario"] = deaths["territorio"] == "do adversário"
    deaths["sem_reacao"] = deaths["dano_no_killer"] == 0
    deaths["duelo"] = deaths["dano_no_killer"] > 0
    return deaths


def team_rounds(deaths, rounds, styles):
    """Uma linha por partida, round e time com os fatores do round inteiro."""
    if "diagnostico_tatico" in deaths:
        deaths = deaths[deaths["diagnostico_tatico"].eq(True)]
    opening = deaths["abertura_valida"] if "abertura_valida" in deaths else deaths["ordem_da_morte"] == 1
    unique_opening = set(zip(deaths.loc[opening & deaths.get("primeira_vitima_unica", pd.Series(True, index=deaths.index)), "match_id"], deaths.loc[opening & deaths.get("primeira_vitima_unica", pd.Series(True, index=deaths.index)), "round"]))
    opening = opening.fillna(False).astype(bool)
    first = deaths[opening][["match_id", "round", "time_vitima", "trocada", "mais_caro_do_time"]]
    first = first.rename(columns={"time_vitima": "time"}).drop_duplicates(["match_id", "round", "time"])
    known_opening = set(zip(first["match_id"], first["round"]))
    table = rounds.merge(first, on=["match_id", "round", "time"], how="left")
    table["abertura_conhecida"] = [(m, r) in known_opening for m, r in zip(table["match_id"], table["round"])]
    table["perdeu_abertura"] = table["trocada"].notna().astype("boolean").where(table["abertura_conhecida"])
    identified_victim = pd.Series([(m, r) in unique_opening for m, r in zip(table["match_id"], table["round"])], index=table.index)
    table["abertura_nao_trocada"] = (table["perdeu_abertura"] & (table["trocada"] == False)).where(identified_victim)
    table["mais_caro_primeiro"] = (table["mais_caro_do_time"] == True).astype("boolean").where(identified_victim)
    table["loadout_abaixo"] = table["diferenca"] < -LOADOUT_GAP
    table = table.merge(styles[["match_id", "round", "time", "colapso", "estilo"]], on=["match_id", "round", "time"], how="left")
    table["colapso"] = table["colapso"].fillna(False).astype(bool)
    table["sem_plant"] = (table["lado"] == "ataque") & (table["estilo"] == "sem plant")
    table["plantou"] = (table["lado"] == "ataque") & table["estilo"].isin(["execução rápida", "default"])
    table["execucao_rapida"] = (table["lado"] == "ataque") & (table["estilo"] == "execução rápida")
    table["loadout_acima"] = table["diferenca"] > LOADOUT_GAP
    opponent = table[["match_id", "round", "time", "perdeu_abertura", "abertura_nao_trocada", "colapso"]].copy()
    opponent["time"] = opponent["time"].map(OTHER_TEAM)
    opponent = opponent.rename(columns={"perdeu_abertura": "fez_abertura", "abertura_nao_trocada": "abertura_feita_nao_trocada", "colapso": "adversario_colapsou"})
    return table.merge(opponent, on=["match_id", "round", "time"], how="left")


ATTACK_ONLY = {"sem_plant", "plantou", "execucao_rapida"}


def cluster_contrast(scope, flag, outcome, repetitions=1000, seed=0):
    """Diferença bruta com−sem; reamostra partidas inteiras, preservando pares."""
    valid = scope[scope[flag].notna() & scope[outcome].notna()].copy()
    with_flag, without = valid[valid[flag].astype(bool)], valid[~valid[flag].astype(bool)]
    difference = with_flag[outcome].mean() - without[outcome].mean()
    valid["n_com"] = valid[flag].astype(int)
    valid["n_sem"] = 1 - valid["n_com"]
    valid["y_com"] = valid[outcome].astype(float) * valid["n_com"]
    valid["y_sem"] = valid[outcome].astype(float) * valid["n_sem"]
    counts = valid.groupby("match_id")[["n_com", "n_sem", "y_com", "y_sem"]].sum().to_numpy()
    if len(counts) < 2 or not len(with_flag) or not len(without):
        return difference, math.nan, math.nan
    rng = np.random.default_rng(seed)
    # Multinomial weights avoid a repetitions × matches × columns allocation.
    weights = rng.multinomial(len(counts), np.full(len(counts), 1/len(counts)), size=repetitions)
    totals = weights @ counts
    supported = (totals[:, 0] > 0) & (totals[:, 1] > 0)
    deltas = totals[supported, 2]/totals[supported, 0] - totals[supported, 3]/totals[supported, 1]
    low, high = np.quantile(deltas, [.025, .975]) if len(deltas) else (math.nan, math.nan)
    return difference, low, high


def factor_ranking(deaths, rounds_with_flags, round_factors=ROUND_FACTORS, death_factors=DEATH_FACTORS, ascending=True):
    """Contrastes brutos por unidade, ordenados dentro de cada população.

    Todos os valores usam P(vitória|com) − P(vitória|sem). São associações de
    populações diferentes, sem controle causal ou soma em contribuição.
    """
    rows = []
    for factors, source, outcome, unit in [(round_factors, rounds_with_flags, "venceu", "round do time"), (death_factors, deaths, "venceu_round", "morte com aliado vivo")]:
        for name, description, column in factors:
            scope = source[source["lado"] == "ataque"] if column in ATTACK_ONLY else source
            scope = scope[scope[column].notna()]
            with_flag, without = scope[scope[column].astype(bool)], scope[~scope[column].astype(bool)]
            difference, low, high = cluster_contrast(scope, column, outcome)
            rows.append({"fator": name, "o que é": description, "unidade": unit, "contraste": "taxa bruta com − sem", "casos": len(with_flag), "casos_sem": len(without), "partidas": scope["match_id"].nunique(), "vitoria_sem": without[outcome].mean(), "vitoria_com": with_flag[outcome].mean(), "diferenca": difference, "ic_baixo": low, "ic_alto": high})
    return pd.DataFrame(rows).sort_values(["unidade", "diferenca"], ascending=[True, ascending]).reset_index(drop=True)


def good_factor_ranking(deaths, rounds_with_flags):
    return factor_ranking(deaths, rounds_with_flags, GOOD_ROUND_FACTORS, GOOD_DEATH_FACTORS, ascending=False)


def build_factor_tables(fights=None, rounds=None, styles=None):
    fights = build_fights_table() if fights is None else fights
    rounds = build_rounds_table() if rounds is None else rounds
    styles = build_round_styles() if styles is None else styles
    fights = fights[fights["match_id"].isin(rounds["match_id"])].copy()
    styles = styles[styles["match_id"].isin(rounds["match_id"])].copy()
    deaths = flag_deaths(fights)
    return deaths, team_rounds(fights, rounds, styles)


def main():
    deaths, rounds_with_flags = build_factor_tables()
    pd.set_option("display.width", 250)
    print(factor_ranking(deaths, rounds_with_flags).round(3).to_string())
    print(good_factor_ranking(deaths, rounds_with_flags).round(3).to_string())


if __name__ == "__main__":
    main()


def player_decisions(events, team_by_puuid, puuid, round_deaths, costs=None, name_of=lambda puuid: puuid[:8]):
    """Observações individuais, sem pontos, saldo ou inferência de erro/viabilidade."""
    from fights import FACING_DEGREES, TRADE_RANGE, facing_angle
    from solo_deaths import distance
    from match_events import is_enemy_kill, was_traded
    costs = costs or {}
    kills = [e for e in events if is_enemy_kill(e, team_by_puuid) and not e.get("after_decision", False)]
    flags_by_key = {(row.segundos, row.vitima): row for row in round_deaths.itertuples()}
    decisions = []
    def add(index, name, detail):
        decisions.append({"evento": index, "fator": name, "associacao": costs.get(name, math.nan), "detalhe": detail})
    opening_time = min((e["time_ms"] for e in kills), default=None)
    opening = [e for e in kills if e["time_ms"] == opening_time]
    unique_opening = len(opening) == 1
    for index, event in enumerate(events):
        if event.get("after_decision", False):
            continue
        if event["kind"] == "plant" and event["actor"] == puuid and event.get("plant_valid", False):
            add(index, "ataque plantou", "plantou a spike")
        if event not in kills:
            continue
        if event["actor"] == puuid:
            if unique_opening and event is opening[0]:
                add(index, "fez o primeiro abate", "fez a abertura com ordem temporal identificada")
            avenged = [earlier for earlier in kills if earlier["victim"] != puuid and earlier["actor"] == event["victim"] and team_by_puuid.get(earlier["victim"]) == team_by_puuid[puuid] and 0 <= event["time_ms"] - earlier["time_ms"] <= 5000]
            if avenged:
                simultaneous = any(e["time_ms"] == event["time_ms"] for e in avenged)
                add(index, "trocou um aliado", f"abate do autor da morte de {name_of(avenged[-1]['victim'])} em até 5 s" + ("; simultâneo, sem ordem de reação conhecida" if simultaneous else ""))
            continue
        if team_by_puuid.get(event["victim"]) != team_by_puuid.get(puuid):
            continue
        flags = flags_by_key.get((event["time_ms"] / 1000, event["victim"]))
        if event["victim"] == puuid:
            if flags is not None and unique_opening and event is opening[0]:
                add(index, "perdeu o primeiro abate", "foi a primeira vítima de abate adversário, com ordem identificada")
                if flags.mais_caro_do_time:
                    add(index, "jogador mais caro morreu primeiro", "tinha o maior loadout do time")
            if flags is not None and flags.sem_reacao:
                add(index, "sem dano no autor registrado no round", "não há dano registrado no autor do abate no agregado do round; reação no confronto é desconhecida")
            continue
        killer_location = next((p["location"] for p in event["locations"] if p["puuid"] == event["actor"]), None)
        me = next((p for p in event["locations"] if p["puuid"] == puuid), None)
        if killer_location is None or me is None or was_traded(event, events, team_by_puuid):
            continue
        if distance(me["location"], killer_location) <= TRADE_RANGE and facing_angle(me, killer_location) <= FACING_DEGREES:
            add(index, "proximidade e direção sem troca", f"estava a {distance(me['location'], killer_location) / 100:.0f} m do autor, com direção compatível, sem troca em 5 s; paredes, visão e viabilidade não são registradas")
    return decisions


def team_round_factors(round_flags, costs=None):
    """Indicadores presentes, com associação populacional separada, sem soma."""
    costs = costs or {}
    return [(name, costs.get(name, math.nan)) for name, _, column in GOOD_ROUND_FACTORS + ROUND_FACTORS if pd.notna(round_flags[column]) and bool(round_flags[column])]


def match_team_summary(rounds_with_flags, match_id, costs=None):
    """Contagens por equipe; indicadores sobrepostos não são contribuições."""
    rows = []
    for team, group in rounds_with_flags[rounds_with_flags["match_id"] == match_id].groupby("time"):
        row = {"time": team, "rounds vencidos": int(group["venceu"].sum()), "rounds": len(group)}
        row.update({name: int(group[column].fillna(False).sum()) for name, _, column in GOOD_ROUND_FACTORS + ROUND_FACTORS})
        rows.append(row)
    return pd.DataFrame(rows).set_index("time") if rows else pd.DataFrame()


def match_player_summary(match, deaths, costs=None):
    """Contagens de observações por jogador, sem pontos ou ranking de contribuição."""
    from match_events import round_events
    team_by_puuid = {p["puuid"]: p["teamId"] for p in match["players"]}
    names = {p["puuid"]: f'{p["gameName"]}#{p["tagLine"]}' for p in match["players"]}
    match_deaths = deaths[deaths["match_id"] == match["matchInfo"]["matchId"]]
    rows = {p["puuid"]: {"jogador": names[p["puuid"]], "time": p["teamId"]} for p in match["players"] if not p.get("isObserver") and p["teamId"] in OTHER_TEAM}
    for rr in match["roundResults"]:
        events = round_events(rr, team_by_puuid)
        round_deaths = match_deaths[match_deaths["round"] == rr["roundNum"] + 1]
        for puuid, row in rows.items():
            for observation in player_decisions(events, team_by_puuid, puuid, round_deaths):
                row[observation["fator"]] = row.get(observation["fator"], 0) + 1
    table = pd.DataFrame(rows.values()).fillna(0)
    if table.empty:
        return table
    counts = table.columns.difference(["jogador", "time"])
    table[counts] = table[counts].astype(int)
    return table.sort_values(["time", "jogador"]).set_index("jogador")


def match_timeline(rounds_with_flags, match_id, costs=None):
    """Indicadores por round e time, em ordem de apresentação, sem classificação."""
    rows = []
    for round_number, pair in rounds_with_flags[rounds_with_flags["match_id"] == match_id].sort_values(["round", "time"]).groupby("round"):
        row = {"round": round_number}
        for flags in pair.itertuples():
            factors = ", ".join(name for name, _ in team_round_factors(flags._asdict()))
            row[flags.time] = f"{flags.lado}, " + ("venceu" if flags.venceu else "perdeu") + (f" · {factors}" if factors else "")
        rows.append(row)
    return pd.DataFrame(rows).set_index("round") if rows else pd.DataFrame()
