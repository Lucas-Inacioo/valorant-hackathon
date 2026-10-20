"""Eventos de round e regras compartilhadas, sem importar a camada gráfica.

Os JSONs não registram ressurreições como eventos: os snapshots são a fonte de
jogadores vivos. Nenhuma função elimina eventos brutos necessários ao replay.
"""

from copy import deepcopy
from itertools import groupby

PLAYING_TEAMS = {"Blue", "Red"}
OPPOSITE_TEAM = {"Blue": "Red", "Red": "Blue"}


def attacking_team(round_result):
    """Lado descritivo do round; usa o resultado e não serve como feature pré-jogo."""
    winner = round_result.get("winningTeam")
    role = round_result.get("winningTeamRole")
    if winner not in PLAYING_TEAMS or role not in {"Attacker", "Defender"}:
        return None
    return winner if role == "Attacker" else OPPOSITE_TEAM[winner]


def is_enemy_kill(event, team_by_puuid=None):
    """Somente abates entre jogadores de equipes adversárias conhecidas."""
    if event.get("kind") != "kill" or event.get("actor") == event.get("victim"):
        return False
    if event.get("finishing", {}).get("damageType") in {"Bomb", "Fall", "Crush"}:
        return False
    if team_by_puuid is None:
        return event.get("enemy_kill") is True
    actor_team = team_by_puuid.get(event.get("actor"))
    victim_team = team_by_puuid.get(event.get("victim"))
    return (
        actor_team in PLAYING_TEAMS and victim_team in PLAYING_TEAMS and actor_team != victim_team
    )


def alive_puuids(event):
    """Vivos após o grupo de eventos simultâneos; respeita reaparições no snapshot."""
    if "alive_after" in event:
        return set(event["alive_after"])
    alive = {row["puuid"] for row in event.get("locations", [])}
    if event.get("kind") == "kill":
        alive.discard(event.get("victim"))
    return alive


def alive_before_puuids(event):
    if "alive_before" in event:
        return set(event["alive_before"])
    alive = alive_puuids(event)
    if event.get("kind") == "kill":
        alive.add(event["victim"])
    return alive


def round_events(round_result, team_by_puuid=None):
    """Kills, plant e defuse em ordem estável; mantém snapshots e marca exclusões.

    ``after_decision`` só é marcado quando o timestamp da decisão é observável
    (defuse, eliminação confirmada pelo resultado e snapshot ou dano Bomb
    confirmando detonação). Sem esse dano não se inventa timestamp de explosão
    nem de fim do timer.
    """
    events = []
    for stats in round_result.get("playerStats", []):
        for kill in stats.get("kills", []) or []:
            events.append(
                {
                    "time_ms": kill["timeSinceRoundStartMillis"],
                    "kind": "kill",
                    "actor": kill.get("killer"),
                    "victim": kill.get("victim"),
                    "victim_location": deepcopy(kill.get("victimLocation", {})),
                    "locations": deepcopy(kill.get("playerLocations") or []),
                    "assistants": list(kill.get("assistants") or []),
                    "finishing": deepcopy(kill.get("finishingDamage") or {}),
                }
            )
    for kind, actor_field, time_field, locations_field in [
        ("plant", "bombPlanter", "plantRoundTime", "plantPlayerLocations"),
        ("defuse", "bombDefuser", "defuseRoundTime", "defusePlayerLocations"),
    ]:
        if round_result.get(actor_field) and round_result.get(time_field) is not None:
            events.append(
                {
                    "time_ms": round_result[time_field],
                    "kind": kind,
                    "actor": round_result[actor_field],
                    "locations": deepcopy(round_result.get(locations_field) or []),
                }
            )
    events.sort(
        key=lambda e: (
            e["time_ms"],
            {"kill": 0, "plant": 1, "defuse": 2}[e["kind"]],
            str(e.get("victim", "")),
            str(e.get("actor", "")),
        )
    )
    counts = {}
    for index, event in enumerate(events):
        key = (
            f'{event["time_ms"]}:{event["kind"]}:{event.get("victim", "")}:{event.get("actor", "")}'
        )
        counts[key] = counts.get(key, 0) + 1
        event.update(index=index, event_id=f"{key}:{counts[key]}")
        event["enemy_kill"] = (
            is_enemy_kill(event, team_by_puuid) if team_by_puuid is not None else None
        )
        event["actor_team"] = (team_by_puuid or {}).get(event.get("actor"))
        event["victim_team"] = (team_by_puuid or {}).get(event.get("victim"))
    previous_alive = {
        puuid for puuid, team in (team_by_puuid or {}).items() if team in PLAYING_TEAMS
    }
    decision_ms = round_result.get("defuseRoundTime") if round_result.get("bombDefuser") else None
    if decision_ms is None and round_result.get("roundResultCode") == "Detonate":
        decision_ms = min(
            (
                event["time_ms"]
                for event in events
                if event.get("finishing", {}).get("damageType") == "Bomb"
            ),
            default=None,
        )
    for time_ms, iterable in groupby(events, key=lambda event: event["time_ms"]):
        group = list(iterable)
        victims = {event["victim"] for event in group if event["kind"] == "kill"}
        observed = {row["puuid"] for event in group for row in event["locations"]}
        # O snapshot é posterior ao evento. Em instantes iguais, nenhuma ordem
        # entre vítimas é identificável; remove todas do estado posterior comum.
        after = (observed if observed else previous_alive) - victims
        before = after | victims
        teams_killing = {
            team_by_puuid.get(event["actor"])
            for event in group
            if team_by_puuid and is_enemy_kill(event, team_by_puuid)
        }
        for event in group:
            event.update(
                alive_before=sorted(before),
                alive_after=sorted(after),
                snapshot_available=bool(observed),
                simultaneous=len(group) > 1,
                simultaneous_enemy_teams=sorted(teams_killing),
            )
        if (
            decision_ms is None
            and team_by_puuid
            and observed
            and round_result.get("roundResultCode") == "Elimination"
        ):
            winner = round_result.get("winningTeam")
            loser = OPPOSITE_TEAM.get(winner)
            if (
                loser
                and any(team_by_puuid.get(p) == winner for p in after)
                and not any(team_by_puuid.get(p) == loser for p in after)
            ):
                decision_ms = time_ms
        previous_alive = after
    for event in events:
        event["decision_time_ms"] = decision_ms
        event["after_decision"] = decision_ms is not None and event["time_ms"] > decision_ms
        event["tactical_valid"] = event["enemy_kill"] is True and not event["after_decision"]
        if event["kind"] == "plant":
            reasons = []
            if round_result.get("roundResult") == "Round timer expired":
                reasons.append("round encerrado por tempo")
            if not event["locations"]:
                reasons.append("snapshot do plant ausente")
            elif team_by_puuid and not any(
                team_by_puuid.get(p) in PLAYING_TEAMS
                and team_by_puuid.get(p) != team_by_puuid.get(event["actor"])
                for p in alive_puuids(event)
            ):
                reasons.append("plant sem defensor vivo")
            if event["after_decision"]:
                reasons.append("plant após decisão do round")
            if not round_result.get("plantLocation"):
                reasons.append("posição do plant ausente")
            event["plant_exclusion"] = "; ".join(reasons)
            event["plant_valid"] = not reasons if team_by_puuid is not None else None
    return events


def was_traded(kill, events, team_by_puuid=None, window_ms=5000):
    """O killer foi abatido pela equipe da vítima em 0–5 s, inclusive empate."""
    if not is_enemy_kill(kill, team_by_puuid) or kill.get("after_decision", False):
        return False
    victim_team = team_by_puuid.get(kill["victim"]) if team_by_puuid else kill.get("victim_team")
    for candidate in events:
        delta = candidate["time_ms"] - kill["time_ms"]
        if not (0 <= delta <= window_ms) or candidate.get("victim") != kill["actor"]:
            continue
        if not is_enemy_kill(candidate, team_by_puuid) or candidate.get("after_decision", False):
            continue
        actor_team = (
            team_by_puuid.get(candidate["actor"]) if team_by_puuid else candidate.get("actor_team")
        )
        if victim_team is not None and actor_team == victim_team:
            return True
    return False


def final_alive_puuids(round_result, team_by_puuid):
    events = round_events(round_result, team_by_puuid)
    if events:
        return alive_puuids(events[-1])
    return {puuid for puuid, team in team_by_puuid.items() if team in PLAYING_TEAMS}
