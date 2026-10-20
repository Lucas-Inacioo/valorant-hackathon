"""Chance de vencer o round por estado (lado, vivos de cada time, spike plantada) e quanto cada evento do round mudou essa chance.

Só usa as tabelas já revisadas: mortes (vivos e fase), plants (vivos no plant) e rounds (lado e faixa de loadout).

Uso: python winprob.py
"""
import pandas as pd

from economy import build_rounds_table
from plants import build_plants_table
from round_map import round_events
from solo_deaths import TRADE_WINDOW_MS, build_deaths_table

OTHER_TEAM = {"Blue": "Red", "Red": "Blue"}
OTHER_SIDE = {"ataque": "defesa", "defesa": "ataque"}
MIN_STATE_ROUNDS = 20


def build_state_table(deaths, plants, rounds):
    """Chance de vencer por (lado, vivos do time, vivos do adversário, fase), vista pelos dois times de cada morte e de cada plant, mais o estado inicial por lado e faixa de loadout."""
    victim_view = deaths[["lado", "aliados_vivos", "inimigos_vivos", "fase", "venceu_round"]].rename(columns={"aliados_vivos": "vivos", "inimigos_vivos": "vivos_adversario", "venceu_round": "venceu"})
    killer_view = pd.DataFrame({"lado": deaths["lado"].map(OTHER_SIDE), "vivos": deaths["inimigos_vivos"], "vivos_adversario": deaths["aliados_vivos"], "fase": deaths["fase"], "venceu": ~deaths["venceu_round"]})
    attack_plant = pd.DataFrame({"lado": "ataque", "vivos": plants["ataque_vivos"], "vivos_adversario": plants["defesa_vivos"], "fase": "pós-plant", "venceu": plants["ataque_venceu"]})
    defense_plant = pd.DataFrame({"lado": "defesa", "vivos": plants["defesa_vivos"], "vivos_adversario": plants["ataque_vivos"], "fase": "pós-plant", "venceu": ~plants["ataque_venceu"]})
    states = pd.concat([victim_view, killer_view, attack_plant, defense_plant])
    table = states.groupby(["lado", "vivos", "vivos_adversario", "fase"])["venceu"].agg(["mean", "size"])
    table = table[table["size"] >= MIN_STATE_ROUNDS]
    known = rounds[rounds["lado"] != "?"]
    start = known.groupby(["lado", "faixa_diferenca"], observed=True)["venceu"].mean()
    return table["mean"].to_dict(), start.to_dict()


def state_probability(state_table, side, alive, alive_opponent, planted):
    """Chance de vencer no estado. Sem morto e sem plant não há linha, então cai no mesmo número de vivos como se fosse pós ou pré-plant mais próximo."""
    key = (side, alive, alive_opponent, "pós-plant" if planted else "pré-plant")
    if key in state_table:
        return state_table[key]
    if alive == 0:
        return 0.0
    if alive_opponent == 0:
        return 0.0 if planted and side == "defesa" else 1.0
    return state_table.get((OTHER_SIDE[side], alive_opponent, alive, key[3]), None)


def round_win_added(round_result, team_by_puuid, attacking_team, state_table, start_probability):
    """Uma linha por evento com a chance de vencer do time atacante antes e depois, e o crédito para quem agiu."""
    side_of = {attacking_team: "ataque", OTHER_TEAM[attacking_team]: "defesa"}
    alive = {attacking_team: 5, OTHER_TEAM[attacking_team]: 5}
    planted = False
    events = round_events(round_result)
    kills = [event for event in events if event["kind"] == "kill"]
    rows = []
    probability = start_probability
    for index, event in enumerate(events):
        before = probability
        actor_team = team_by_puuid[event["actor"]]
        if event["kind"] == "kill":
            alive[team_by_puuid[event["victim"]]] -= 1
        elif event["kind"] == "plant":
            planted = True
        if event["kind"] == "defuse":
            probability = 0.0
        else:
            probability = state_probability(state_table, "ataque", alive[attacking_team], alive[OTHER_TEAM[attacking_team]], planted)
            if probability is None:
                probability = 1 - state_probability(state_table, "defesa", alive[OTHER_TEAM[attacking_team]], alive[attacking_team], planted)
        actor_gain = (probability - before) if actor_team == attacking_team else (before - probability)
        traded = event["kind"] == "kill" and any(earlier["actor"] == event["victim"] and team_by_puuid[earlier["victim"]] == actor_team and event["time_ms"] - earlier["time_ms"] <= TRADE_WINDOW_MS for earlier in kills[:kills.index(event)])
        rows.append({"evento": index, "segundos": event["time_ms"] / 1000, "tipo": "troca" if traded else event["kind"], "autor": event["actor"], "vitima": event.get("victim"), "time_autor": actor_team, "antes_ataque": before, "depois_ataque": probability, "ganho_do_autor": actor_gain})
    # O fim do round (tempo esgotado, spike explodiu) leva a chance ao resultado real, sem autor
    final = 1.0 if round_result["winningTeam"] == attacking_team else 0.0
    if probability != final:
        rows.append({"evento": len(events), "segundos": None, "tipo": "fim do round", "autor": None, "vitima": None, "time_autor": None, "antes_ataque": probability, "depois_ataque": final, "ganho_do_autor": 0.0})
    return pd.DataFrame(rows)


def match_win_added(match, attacking_by_round, state_table, start_by_round):
    """Todos os eventos da partida com o ganho de chance de cada um, para somar por jogador."""
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    frames = []
    for round_result in match["roundResults"]:
        round_number = round_result["roundNum"] + 1
        attacking_team = attacking_by_round.get(round_number)
        if attacking_team is None or round_number not in start_by_round:
            continue
        frame = round_win_added(round_result, team_by_puuid, attacking_team, state_table, start_by_round[round_number])
        frame.insert(0, "round", round_number)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def player_win_added(events, name_by_puuid, team_by_puuid):
    """Por jogador: chance ganha como autor (abates, trocas, plants, desarmes) e perdida como vítima, somadas na partida."""
    gained = events.groupby("autor")["ganho_do_autor"].sum()
    lost = events[events["tipo"].isin(["kill", "troca"])].groupby("vitima")["ganho_do_autor"].sum()
    trades = events[events["tipo"] == "troca"].groupby("autor").size()
    table = pd.DataFrame({"time": pd.Series(team_by_puuid), "chance ganha": gained, "chance perdida": lost, "trocas": trades}).fillna(0)
    table = table[table["time"].notna()]
    table["saldo"] = table["chance ganha"] - table["chance perdida"]
    table.index = table.index.map(name_by_puuid)
    table.index.name = "jogador"
    table[["chance ganha", "chance perdida", "saldo"]] = (table[["chance ganha", "chance perdida", "saldo"]] * 100).round(0)
    table["trocas"] = table["trocas"].astype(int)
    return table.sort_values(["time", "saldo"], ascending=[True, False])[["time", "saldo", "chance ganha", "chance perdida", "trocas"]]


def main():
    deaths, plants, rounds = build_deaths_table(), build_plants_table(), build_rounds_table()
    state_table, start = build_state_table(deaths, plants, rounds)
    pd.set_option("display.width", 200)
    print(pd.Series(state_table).unstack(3).round(2).to_string())
    print(pd.Series(start).unstack().round(2).to_string())


if __name__ == "__main__":
    main()
