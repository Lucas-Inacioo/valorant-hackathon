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
    return table


def mean_interval(values, z=1.96):
    """Média com intervalo de 95% pela aproximação normal."""
    values = pd.Series(values, dtype=float)
    half_width = z * values.std(ddof=1) / math.sqrt(len(values)) if len(values) > 1 else math.nan
    return values.mean(), values.mean() - half_width, values.mean() + half_width


def factor_ranking(deaths, rounds_with_flags):
    """Por fator: quantos casos, vitória sem e com, diferença com intervalo. Mortes são comparadas ao esperado pelos vivos, rounds à vitória sem o fator."""
    rows = []
    for name, description, column in ROUND_FACTORS:
        scope = rounds_with_flags[rounds_with_flags["lado"] == "ataque"] if column == "sem_plant" else rounds_with_flags
        with_flag, without_flag = scope[scope[column]], scope[~scope[column]]
        low, high = difference_interval(with_flag["venceu"].mean(), len(with_flag), without_flag["venceu"].mean(), len(without_flag))
        rows.append({"fator": name, "o que é": description, "unidade": "round do time", "casos": len(with_flag), "vitoria_sem": without_flag["venceu"].mean(), "vitoria_com": with_flag["venceu"].mean(), "diferenca": with_flag["venceu"].mean() - without_flag["venceu"].mean(), "ic_baixo": low, "ic_alto": high})
    for name, description, column in DEATH_FACTORS:
        with_flag, without_flag = deaths[deaths[column]], deaths[~deaths[column]]
        mean, low, high = mean_interval(with_flag["acima_do_esperado"])
        rows.append({"fator": name, "o que é": description, "unidade": "morte, descontado o esperado pelos vivos", "casos": len(with_flag), "vitoria_sem": without_flag["venceu_round"].mean(), "vitoria_com": with_flag["venceu_round"].mean(), "diferenca": mean, "ic_baixo": low, "ic_alto": high})
    return pd.DataFrame(rows).sort_values("diferenca").reset_index(drop=True)


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


if __name__ == "__main__":
    main()


def player_decisions(events, team_by_puuid, puuid, round_deaths, costs):
    """Eventos do round em que o jogador perdeu chance de vencer: morreu primeiro, morreu sem reação ou não trocou um aliado que podia trocar."""
    from fights import FACING_DEGREES, TRADE_RANGE, facing_angle
    from solo_deaths import distance, was_traded
    kills = [event for event in events if event["kind"] == "kill"]
    flags_by_time = {row.segundos: row for row in round_deaths.itertuples()}
    decisions = []
    for index, event in enumerate(events):
        if event["kind"] != "kill" or team_by_puuid[event["victim"]] != team_by_puuid[puuid]:
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
    """Fatores do round inteiro que o time disparou, do mais caro ao mais barato."""
    triggered = [(name, costs[name]) for name, _, column in ROUND_FACTORS if bool(round_flags[column])]
    return sorted(triggered, key=lambda item: item[1])
