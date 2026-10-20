"""Referências empíricas contextuais fora da partida, sem crédito individual.

Não é um modelo calibrado. Compara taxas observadas por estado, faixa de loadout
inicial e relógio. Estados sem suporte permanecem ausentes, sem trocar população.
"""
import math

import numpy as np
import pandas as pd

from economy import build_rounds_table
from plants import plant_exclusion
from explore_fields import DEFAULT_DATA_DIR, find_match_files, load_match
from match_events import alive_before_puuids, alive_puuids, round_events, is_enemy_kill, was_traded

OTHER_TEAM = {"Blue": "Red", "Red": "Blue"}
OTHER_SIDE = {"ataque": "defesa", "defesa": "ataque"}
MIN_STATE_ROUNDS = 20
MIN_STATE_MATCHES = 5
EVENT_COLUMNS = ["round", "evento", "segundos", "tipo", "autor", "vitima", "time_autor", "antes_ataque", "depois_ataque", "n_antes", "n_depois", "partidas_antes", "partidas_depois", "ic_baixo", "ic_alto", "faixa_diferenca", "faixa_tempo", "fase", "estado", "observacao"]


def time_band(time_ms, plant_time=None):
    """Pré-plant: relógio do round; pós-plant: tempo decorrido desde o plant."""
    elapsed = max(0, time_ms - (plant_time or 0)) / 1000
    if plant_time is not None:
        return f"pós: [{int(elapsed // 10) * 10}, {int(elapsed // 10) * 10 + 10}) s"
    lower = min(int(elapsed // 20) * 20, 100)
    return f"pré: [{lower}, {lower + 20}) s" if lower < 100 else "pré: ≥100 s"


def _counts(alive, teams, attack):
    return (sum(teams.get(p) == attack for p in alive), sum(teams.get(p) == OTHER_TEAM[attack] for p in alive))


def _key(side, alive, enemy, planted, economy, clock):
    return side, int(alive), int(enemy), "pós-plant" if planted else "pré-plant", str(economy), clock


def _reference(group):
    n, matches = len(group), group["match_id"].nunique()
    p = group["venceu"].mean()
    sufficient = n >= MIN_STATE_ROUNDS and matches >= MIN_STATE_MATCHES
    # Bootstrap por partida mantém os rounds dependentes do mesmo jogo juntos.
    counts = group.groupby("match_id")["venceu"].agg(["sum", "size"]).to_numpy()
    low = high = math.nan
    if matches >= 2:
        rng = np.random.default_rng(0)
        weights = rng.multinomial(matches, np.full(matches, 1/matches), size=1000)
        totals = weights @ counts
        low, high = np.quantile(totals[:, 0]/totals[:, 1], [.025, .975])
    return {"probabilidade": float(p) if sufficient else math.nan, "rounds": n, "partidas": matches, "ic_baixo": float(low) if sufficient else math.nan, "ic_alto": float(high) if sufficient else math.nan, "suporte_suficiente": sufficient}


def _missing():
    return {"probabilidade": math.nan, "rounds": 0, "partidas": 0, "ic_baixo": math.nan, "ic_alto": math.nan, "suporte_suficiente": False}


def _phase_contexts(rr, teams, events):
    """Antes/depois comuns ao grupo simultâneo, incluindo plant+abate."""
    planted, plant_time, contexts = False, None, {}
    valid_plant_round = bool(rr.get("bombPlanter")) and not plant_exclusion(rr, teams)
    for timestamp in sorted({e["time_ms"] for e in events}):
        before = planted, plant_time
        if valid_plant_round and any(e["time_ms"] == timestamp and e["kind"] == "plant" for e in events):
            planted, plant_time = True, timestamp
        contexts[timestamp] = (*before, planted, plant_time)
    return contexts


def _round_states(rr, teams, attack, economy):
    """Um estado por instante; simultâneos compartilham snapshot, sem ordem artificial."""
    initial = _key("ataque", sum(t == attack for t in teams.values()), sum(t == OTHER_TEAM[attack] for t in teams.values()), False, economy, time_band(0))
    yield initial
    events = round_events(rr, teams)
    contexts = _phase_contexts(rr, teams, events)
    for timestamp in sorted(contexts):
        group = [e for e in events if e["time_ms"] == timestamp]
        event = group[0]
        _, _, planted, plant_time = contexts[timestamp]
        if event.get("after_decision") or any(e["kind"] == "defuse" for e in group):
            continue
        if not any(is_enemy_kill(e, teams) or (e["kind"] == "plant" and planted) for e in group):
            continue
        if not event.get("snapshot_available"):
            continue
        own, enemy = _counts(alive_puuids(event), teams, attack)
        if (not planted and (not own or not enemy)) or (planted and not enemy):
            continue
        yield _key("ataque", own, enemy, planted, economy, time_band(timestamp, plant_time))


def build_state_table(deaths, plants, rounds, exclude_match_id=None, data_dir=DEFAULT_DATA_DIR):
    """Referências somente no escopo de rounds, excluindo a partida selecionada.

    Deaths/plants são aceitos para compatibilidade; snapshots brutos determinam
    os vivos, incluindo reaparições. Cada round conta uma vez em cada contexto.
    """
    from predict import attacking_team_by_round
    known = rounds[(rounds["lado"] == "ataque") & (rounds["match_id"] != exclude_match_id)]
    allowed = set(known["match_id"])
    economy_by_round = {(r.match_id, r.round): r.faixa_diferenca for r in known.itertuples()}
    observations = []
    for path in find_match_files(data_dir):
        match = load_match(path)
        mid = match["matchInfo"]["matchId"]
        if mid not in allowed:
            continue
        teams = {p["puuid"]: p["teamId"] for p in match["players"] if not p.get("isObserver") and p["teamId"] in OTHER_TEAM}
        attacks = attacking_team_by_round(match)
        for rr in match["roundResults"]:
            number = rr["roundNum"] + 1
            attack, economy = attacks.get(number), economy_by_round.get((mid, number))
            if attack is None or pd.isna(economy):
                continue
            for key in set(_round_states(rr, teams, attack, economy)):
                observations.append({"key": key, "match_id": mid, "round": number, "venceu": rr["winningTeam"] == attack})
    frame = pd.DataFrame(observations)
    refs = {key: _reference(group) for key, group in frame.groupby("key")} if not frame.empty else {}
    # Estes registros iniciais têm exatamente o mesmo contexto econômico e de
    # relógio da consulta inicial, não uma referência geral de outra população.
    starts = {("ataque", key[4]): record for key, record in refs.items() if key[1:4] == (5, 5, "pré-plant") and key[5] == time_band(0)}
    return refs, starts


def state_reference(state_table, side, alive, alive_opponent, planted, economy=None, clock=None):
    """Sem fallback entre relógios, fases ou faixas econômicas."""
    key = _key(side, alive, alive_opponent, planted, economy, clock)
    if key in state_table:
        record = state_table[key]
        return dict(record) if isinstance(record, dict) else {**_missing(), "probabilidade": record}
    inverse = _key(OTHER_SIDE[side], alive_opponent, alive, planted, economy, clock)
    if inverse in state_table:
        result = dict(state_table[inverse])
        result["probabilidade"] = 1 - result["probabilidade"]
        result["ic_baixo"], result["ic_alto"] = 1-result["ic_alto"], 1-result["ic_baixo"]
        return result
    return _missing()


def state_probability(state_table, side, alive, alive_opponent, planted, economy=None, clock=None):
    """Wrapper seguro; NaN significa referência insuficiente, nunca certeza inventada."""
    # Compatibilidade para tabelas sintéticas antigas: o complemento é obrigatório.
    legacy = (side, alive, alive_opponent, "pós-plant" if planted else "pré-plant")
    if legacy in state_table:
        return state_table[legacy]
    opposite = (OTHER_SIDE[side], alive_opponent, alive, legacy[3])
    if opposite in state_table:
        return 1 - state_table[opposite]
    return state_reference(state_table, side, alive, alive_opponent, planted, economy, clock)["probabilidade"]


def round_win_added(round_result, team_by_puuid, attacking_team, state_table, start_probability):
    """Referência antes/depois por evento; nenhum valor é atribuído ao jogador."""
    economy = start_probability.get("faixa_diferenca") if isinstance(start_probability, dict) else start_probability
    if economy is None or not isinstance(economy, str):
        economy = "contexto econômico desconhecido"
    rows = []
    events = round_events(round_result, team_by_puuid)
    contexts = _phase_contexts(round_result, team_by_puuid, events)
    kills = [e for e in events if is_enemy_kill(e, team_by_puuid)]
    for index, event in enumerate(events):
        before_planted, before_plant_time, planted, plant_time = contexts[event["time_ms"]]
        before_clock = time_band(event["time_ms"], before_plant_time)
        before_alive = _counts(alive_before_puuids(event), team_by_puuid, attacking_team)
        after_alive = _counts(alive_puuids(event), team_by_puuid, attacking_team)
        valid_plant = event["kind"] == "plant" and planted and not plant_exclusion(round_result, team_by_puuid)
        clock = time_band(event["time_ms"], plant_time)
        terminal = any(e["kind"] == "defuse" and e["time_ms"] == event["time_ms"] for e in events) or (not planted and (not after_alive[0] or not after_alive[1])) or (planted and not after_alive[1])
        excluded = event.get("after_decision") or (event["kind"] == "kill" and not is_enemy_kill(event, team_by_puuid)) or (event["kind"] == "plant" and not valid_plant) or not event.get("snapshot_available")
        before = state_reference(state_table, "ataque", *before_alive, before_planted, economy, before_clock) if not excluded else _missing()
        after = state_reference(state_table, "ataque", *after_alive, planted, economy, clock) if not excluded and not terminal else _missing()
        notes = []
        if excluded:
            notes.append("evento excluído da referência tática")
        elif terminal:
            notes.append("decisão observada; resultado não é probabilidade estimada")
        elif not before["suporte_suficiente"] or not after["suporte_suficiente"]:
            notes.append("amostra insuficiente em pelo menos um estado")
        if event.get("simultaneous"):
            notes.append("eventos simultâneos: mesmo estado antes/depois; ordem desconhecida")
        traded = event["kind"] == "kill" and any(e.get("actor") == event.get("victim") and was_traded(e, [event], team_by_puuid) for e in kills)
        rows.append({"evento": index, "segundos": event["time_ms"]/1000, "tipo": "troca temporal" if traded else event["kind"], "autor": event["actor"], "vitima": event.get("victim"), "time_autor": team_by_puuid.get(event["actor"]), "antes_ataque": before["probabilidade"], "depois_ataque": after["probabilidade"], "n_antes": before["rounds"], "n_depois": after["rounds"], "partidas_antes": before["partidas"], "partidas_depois": after["partidas"], "ic_baixo": after["ic_baixo"], "ic_alto": after["ic_alto"], "faixa_diferenca": economy, "faixa_tempo": clock, "fase": "pós-plant" if planted else "pré-plant", "estado": f"{after_alive[0]}v{after_alive[1]}", "observacao": "; ".join(notes)})
    return pd.DataFrame(rows, columns=EVENT_COLUMNS[1:])


def match_win_added(match, attacking_by_round, state_table, start_by_round):
    """Nome legado: devolve referências por evento, sem ganho ou saldo individual."""
    teams = {p["puuid"]: p["teamId"] for p in match["players"] if not p.get("isObserver") and p["teamId"] in OTHER_TEAM}
    frames = []
    for rr in match["roundResults"]:
        number = rr["roundNum"] + 1
        attack = attacking_by_round.get(number)
        if attack not in OTHER_TEAM or number not in start_by_round:
            continue
        frame = round_win_added(rr, teams, attack, state_table, start_by_round[number])
        frame.insert(0, "round", number)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=EVENT_COLUMNS)


def player_win_added(events, name_by_puuid, team_by_puuid):
    """Nome legado: somente contagens de eventos, sem atribuição de probabilidade."""
    counts = pd.crosstab(events["autor"], events["tipo"]) if not events.empty else pd.DataFrame()
    counts.insert(0, "time", pd.Series(team_by_puuid).reindex(counts.index))
    counts.index = counts.index.map(name_by_puuid)
    counts.index.name = "jogador"
    return counts


def main():
    refs, _ = build_state_table(None, None, build_rounds_table())
    print(pd.DataFrame([{**dict(zip(["lado", "vivos", "adversários", "fase", "economia", "tempo"], key)), **value} for key, value in refs.items()]).to_string(index=False))


if __name__ == "__main__":
    main()
