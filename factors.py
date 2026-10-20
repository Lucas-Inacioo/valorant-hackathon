"""Fatores que derrubam a chance de vencer o round, com intervalo de 95%, e os eventos de cada round que os disparam.

Uso: python factors.py
"""
import math

import pandas as pd

from economy import build_rounds_table
from fights import TRADE_POSSIBLE, build_fights_table
from first_blood import difference_interval
from round_style import build_round_styles
from solo_deaths import SOLO_DISTANCE, with_solo_flag

OTHER_TEAM = {"Blue": "Red", "Red": "Blue"}
LOADOUT_GAP = 5000

# Nome do fator, descrição curta e a coluna booleana da tabela de mortes que o dispara (None para fatores do round inteiro)
DEATH_FACTORS = [
    ("troca possível não feita", "um aliado estava em alcance olhando para o killer e não vingou a morte", "troca_nao_feita"),
    ("morte isolada", "morreu sem aliado a menos de 10 m, com aliado vivo", "isolada"),
    ("morte em flanco", "o time estava junto em outra região", "flanco"),
    ("morte em território do adversário", "morreu em região onde o outro lado costuma começar o round", "no_adversario"),
    ("arma curta em duelo longo", "morreu com SMG ou shotgun a 25 m ou mais", "arma_curta_em_duelo_longo"),
    ("sniper em duelo curto", "morreu com sniper a 10 m ou menos", "sniper_em_duelo_curto"),
    ("morte sem reação", "não feriu quem a matou e ninguém mais a feriu", "sem_reacao"),
]
GOOD_DEATH_FACTORS = [
    ("morte trocada", "um aliado matou o killer em até 5 s", "trocada"),
    ("morte em duelo", "feriu quem a matou antes de morrer", "duelo"),
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
    deaths = with_solo_flag(fights, SOLO_DISTANCE)
    deaths["troca_nao_feita"] = (deaths["troca_possivel"] == TRADE_POSSIBLE) & ~deaths["trocada"]
    deaths["flanco"] = deaths["contexto"] == "flanco"
    deaths["no_adversario"] = deaths["territorio"] == "do adversário"
    deaths["sem_reacao"] = deaths["classe_luta"] == "sem reação"
    deaths["duelo"] = deaths["classe_luta"] == "duelo"
    expected = deaths.groupby(["lado", "aliados_vivos", "inimigos_vivos"])["venceu_round"].transform("mean")
    deaths["acima_do_esperado"] = deaths["venceu_round"].astype(float) - expected
    return deaths


def team_rounds(deaths, rounds, styles):
    """Uma linha por partida, round e time com os fatores do round inteiro."""
    first = deaths[deaths["ordem_da_morte"] == 1][["match_id", "round", "time_vitima", "trocada", "mais_caro_do_time"]]
    first = first.rename(columns={"time_vitima": "time"})
    table = rounds.merge(first, on=["match_id", "round", "time"], how="left")
    table["perdeu_abertura"] = table["trocada"].notna()
    table["abertura_nao_trocada"] = table["perdeu_abertura"] & (table["trocada"] == False)
    table["mais_caro_primeiro"] = table["mais_caro_do_time"] == True
    table["loadout_abaixo"] = table["diferenca"] < -LOADOUT_GAP
    table = table.merge(styles[["match_id", "round", "time", "colapso", "estilo"]], on=["match_id", "round", "time"], how="left")
    table["colapso"] = table["colapso"].fillna(False).astype(bool)
    table["sem_plant"] = (table["lado"] == "ataque") & (table["estilo"] == "sem plant")
    table["plantou"] = (table["lado"] == "ataque") & (table["estilo"] != "sem plant")
    table["execucao_rapida"] = (table["lado"] == "ataque") & (table["estilo"] == "execução rápida")
    table["loadout_acima"] = table["diferenca"] > LOADOUT_GAP
    opponent = table[["match_id", "round", "time", "perdeu_abertura", "abertura_nao_trocada", "colapso"]].copy()
    opponent["time"] = opponent["time"].map(OTHER_TEAM)
    opponent = opponent.rename(columns={"perdeu_abertura": "fez_abertura", "abertura_nao_trocada": "abertura_feita_nao_trocada", "colapso": "adversario_colapsou"})
    return table.merge(opponent, on=["match_id", "round", "time"], how="left")


def mean_interval(values, z=1.96):
    """Média com intervalo de 95% pela aproximação normal."""
    values = pd.Series(values, dtype=float)
    half_width = z * values.std(ddof=1) / math.sqrt(len(values)) if len(values) > 1 else math.nan
    return values.mean(), values.mean() - half_width, values.mean() + half_width


ATTACK_ONLY = {"sem_plant", "plantou", "execucao_rapida"}


def factor_ranking(deaths, rounds_with_flags, round_factors=ROUND_FACTORS, death_factors=DEATH_FACTORS, ascending=True):
    """Por fator: quantos casos, vitória sem e com, diferença com intervalo. Mortes são comparadas ao esperado pelos vivos, rounds à vitória sem o fator."""
    rows = []
    for name, description, column in round_factors:
        scope = rounds_with_flags[rounds_with_flags["lado"] == "ataque"] if column in ATTACK_ONLY else rounds_with_flags
        with_flag, without_flag = scope[scope[column]], scope[~scope[column]]
        low, high = difference_interval(with_flag["venceu"].mean(), len(with_flag), without_flag["venceu"].mean(), len(without_flag))
        rows.append({"fator": name, "o que é": description, "unidade": "round do time", "casos": len(with_flag), "vitoria_sem": without_flag["venceu"].mean(), "vitoria_com": with_flag["venceu"].mean(), "diferenca": with_flag["venceu"].mean() - without_flag["venceu"].mean(), "ic_baixo": low, "ic_alto": high})
    for name, description, column in death_factors:
        with_flag, without_flag = deaths[deaths[column]], deaths[~deaths[column]]
        mean, low, high = mean_interval(with_flag["acima_do_esperado"])
        rows.append({"fator": name, "o que é": description, "unidade": "morte, descontado o esperado pelos vivos", "casos": len(with_flag), "vitoria_sem": without_flag["venceu_round"].mean(), "vitoria_com": with_flag["venceu_round"].mean(), "diferenca": mean, "ic_baixo": low, "ic_alto": high})
    return pd.DataFrame(rows).sort_values("diferenca", ascending=ascending).reset_index(drop=True)


def good_factor_ranking(deaths, rounds_with_flags):
    return factor_ranking(deaths, rounds_with_flags, GOOD_ROUND_FACTORS, GOOD_DEATH_FACTORS, ascending=False)


def build_factor_tables(fights=None, rounds=None, styles=None):
    fights = build_fights_table() if fights is None else fights
    rounds = build_rounds_table() if rounds is None else rounds
    styles = build_round_styles() if styles is None else styles
    deaths = flag_deaths(fights)
    return deaths, team_rounds(deaths, rounds, styles)


def main():
    deaths, rounds_with_flags = build_factor_tables()
    pd.set_option("display.width", 250)
    print(factor_ranking(deaths, rounds_with_flags).round(3).to_string())
    print(good_factor_ranking(deaths, rounds_with_flags).round(3).to_string())


if __name__ == "__main__":
    main()


def player_decisions(events, team_by_puuid, puuid, round_deaths, costs, name_of=lambda puuid: puuid[:8]):
    """Eventos do round em que o jogador mexeu na chance de vencer: morreu primeiro, morreu sem reação, não trocou um aliado que podia trocar, abriu o round, trocou, plantou."""
    from fights import FACING_DEGREES, TRADE_RANGE, facing_angle
    from solo_deaths import distance, was_traded
    kills = [event for event in events if event["kind"] == "kill"]
    flags_by_time = {row.segundos: row for row in round_deaths.itertuples()}
    decisions = []
    for index, event in enumerate(events):
        if event["kind"] == "plant" and event["actor"] == puuid:
            decisions.append({"evento": index, "fator": "ataque plantou", "custo": costs["ataque plantou"], "detalhe": "plantou a spike"})
        if event["kind"] != "kill":
            continue
        if event["actor"] == puuid:
            if kills.index(event) == 0:
                decisions.append({"evento": index, "fator": "fez o primeiro abate", "custo": costs["fez o primeiro abate"], "detalhe": "abriu o round"})
            avenged = [earlier for earlier in kills[:kills.index(event)] if earlier["actor"] == event["victim"] and team_by_puuid[earlier["victim"]] == team_by_puuid[puuid] and event["time_ms"] - earlier["time_ms"] <= 5000]
            if avenged:
                decisions.append({"evento": index, "fator": "trocou um aliado", "custo": costs["morte trocada"], "detalhe": f"trocou a morte de {name_of(avenged[-1]['victim'])}"})
            continue
        if team_by_puuid[event["victim"]] != team_by_puuid[puuid]:
            continue
        flags = flags_by_time.get(event["time_ms"] / 1000)
        if event["victim"] == puuid:
            if flags is not None and flags.ordem_da_morte == 1:
                decisions.append({"evento": index, "fator": "perdeu o primeiro abate", "custo": costs["perdeu o primeiro abate"], "detalhe": "foi o primeiro a morrer no round" + ("" if flags.trocada else " e ninguém trocou")})
                if flags.mais_caro_do_time:
                    decisions.append({"evento": index, "fator": "jogador mais caro morreu primeiro", "custo": costs["jogador mais caro morreu primeiro"], "detalhe": "tinha o maior loadout do time"})
            if flags is not None and flags.sem_reacao:
                decisions.append({"evento": index, "fator": "morte sem reação", "custo": costs["morte sem reação"], "detalhe": "não feriu quem o matou"})
            continue
        killer_location = next((alive["location"] for alive in event["locations"] if alive["puuid"] == event["actor"]), None)
        me = next((alive for alive in event["locations"] if alive["puuid"] == puuid), None)
        if killer_location is None or me is None or was_traded(event, kills[kills.index(event) + 1:]):
            continue
        if distance(me["location"], killer_location) <= TRADE_RANGE and facing_angle(me, killer_location) <= FACING_DEGREES:
            decisions.append({"evento": index, "fator": "troca possível não feita", "custo": costs["troca possível não feita"], "detalhe": f"estava a {distance(me['location'], killer_location) / 100:.0f} m do killer, olhando para ele, e não trocou"})
    return sorted(decisions, key=lambda decision: decision["custo"])


def team_round_factors(round_flags, costs):
    """Fatores do round inteiro que o time disparou, do que mais ajudou ao que mais custou."""
    triggered = [(name, costs[name]) for name, _, column in GOOD_ROUND_FACTORS + ROUND_FACTORS if bool(round_flags[column])]
    return sorted(triggered, key=lambda item: -item[1])


def match_team_summary(rounds_with_flags, match_id, costs):
    """Por time da partida: rounds vencidos e, para cada fator do round, quantas vezes aconteceu e quantos pontos de vitória isso custou somados."""
    match_rounds = rounds_with_flags[rounds_with_flags["match_id"] == match_id]
    rows = []
    for team, team_rounds_ in match_rounds.groupby("time"):
        row = {"time": team, "rounds vencidos": int(team_rounds_["venceu"].sum()), "rounds": len(team_rounds_)}
        gained, lost = 0.0, 0.0
        for name, _, column in GOOD_ROUND_FACTORS + ROUND_FACTORS:
            count = int(team_rounds_[column].sum())
            row[name] = count
            if costs[name] > 0:
                gained += count * costs[name]
            else:
                lost += count * costs[name]
        row["pontos ganhos"] = round(gained * 100)
        row["pontos perdidos"] = round(lost * 100)
        rows.append(row)
    return pd.DataFrame(rows).set_index("time")


def match_player_summary(match, deaths, costs):
    """Por jogador da partida: quantas vezes cada decisão apareceu nos rounds e a soma dos pontos de vitória que custaram."""
    from round_map import round_events
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    name_by_puuid = {player["puuid"]: f'{player["gameName"]}#{player["tagLine"]}' for player in match["players"]}
    match_deaths = deaths[deaths["match_id"] == match["matchInfo"]["matchId"]]
    rows = {puuid: {"jogador": name_by_puuid[puuid], "time": team_by_puuid[puuid], "pontos ganhos": 0.0, "pontos perdidos": 0.0} for puuid in team_by_puuid if not next(player for player in match["players"] if player["puuid"] == puuid)["isObserver"]}
    for round_result in match["roundResults"]:
        events = round_events(round_result)
        round_deaths = match_deaths[match_deaths["round"] == round_result["roundNum"] + 1]
        for puuid, row in rows.items():
            for decision in player_decisions(events, team_by_puuid, puuid, round_deaths, costs):
                row[decision["fator"]] = row.get(decision["fator"], 0) + 1
                row["pontos ganhos" if decision["custo"] > 0 else "pontos perdidos"] += decision["custo"] * 100
    table = pd.DataFrame(list(rows.values())).fillna(0)
    table["saldo"] = (table["pontos ganhos"] + table["pontos perdidos"]).round(0)
    table[["pontos ganhos", "pontos perdidos"]] = table[["pontos ganhos", "pontos perdidos"]].round(0)
    count_columns = [column for column in table.columns if column not in {"jogador", "time", "pontos ganhos", "pontos perdidos", "saldo"}]
    table[count_columns] = table[count_columns].astype(int)
    return table.sort_values(["time", "saldo"], ascending=[True, False]).set_index("jogador")[["time", "saldo", "pontos ganhos", "pontos perdidos", *count_columns]]


def match_timeline(rounds_with_flags, match_id, costs):
    """Round a round: lado e resultado de cada time e os fatores que cada um disparou, do mais caro ao mais barato."""
    match_rounds = rounds_with_flags[rounds_with_flags["match_id"] == match_id].sort_values(["round", "time"])
    rows = []
    for round_number, pair in match_rounds.groupby("round"):
        row = {"round": round_number}
        for flags in pair.itertuples():
            factors = ", ".join(name for name, _ in team_round_factors(flags._asdict(), costs))
            row[flags.time] = f"{flags.lado}, " + ("venceu" if flags.venceu else "perdeu") + (f" · {factors}" if factors else "")
        rows.append(row)
    return pd.DataFrame(rows).set_index("round")
