"""Observações de uma partida para revisão pós-jogo.

Uma ocorrência descreve o que o registro permite ver. O resultado do round é
mostrado ao lado da observação, sem transformar associação em culpa individual.
Cada padrão possui suas próprias oportunidades e não se somam rounds de padrões
diferentes. Eventos simultâneos compartilham um estado e ressurreições vêm dos
snapshots, conforme as regras de ``events``.
"""

from dataclasses import dataclass
from itertools import groupby
import math

import pandas as pd

from valorant.analysis.deaths import SOLO_DISTANCE
from valorant.analysis.events import (
    PLAYING_TEAMS,
    alive_before_puuids,
    alive_puuids,
    attacking_team,
    round_events,
    was_traded,
)
from valorant.analysis.fights import (
    FACING_DEGREES,
    TRADE_POSSIBLE,
    TRADE_RANGE,
    facing_angle,
)


@dataclass(frozen=True)
class ReviewPattern:
    name: str
    description: str
    question: str
    opportunity_label: str
    positive: bool = False
    context_only: bool = False
    # Frase do card de revisão, com a contagem já embutida.
    summary: str = ""


PATTERNS = {
    "isolated_death": ReviewPattern(
        "Morte longe do apoio",
        "Morreu com aliado vivo, mas nenhum aliado estava a até 1000 unidades de jogo.",
        "O jogador precisava fazer esse contato sozinho ou poderia esperar apoio?",
        "Mortes com aliado vivo e posição disponível",
        summary="{occurrences} de {opportunities} mortes tinham um ou mais aliados vivos, mas nenhum a até 1000 unidades.",
    ),
    "away_from_group": ReviewPattern(
        "Morte longe do grupo",
        "Morreu a mais de 1000 unidades do aliado mais próximo enquanto pelo menos dois aliados ocupavam a mesma região do mapa.",
        "A separação tinha um objetivo combinado com a equipe?",
        "Mortes com ao menos dois aliados vivos e regiões identificadas",
        summary="{occurrences} de {opportunities} mortes tinham dois ou mais aliados vivos. Morreu a mais de 1000 unidades do aliado mais próximo enquanto pelo menos dois aliados ocupavam a mesma região do mapa.",
    ),
    "isolated_opening_untraded": ReviewPattern(
        "Primeira morte longe do apoio e sem troca",
        "O autor do primeiro abate do round eliminou um jogador que estava longe dos aliados e não morreu em até 5 segundos.",
        "Como preparar esse primeiro contato para que haja apoio ou uma saída?",
        "Primeiras mortes individuais com aliado vivo e posição disponível",
        summary="{occurrences} de {opportunities} primeiras mortes da rodada tinham um ou mais aliados vivos, mas nenhum a até 1000 unidades, e o autor do abate não foi eliminado em até 5 segundos.",
    ),
    "untraded_with_nearby_ally": ReviewPattern(
        "Sem troca com aliado perto",
        "Havia aliado a até 2000 unidades do autor do abate e olhando em sua direção, mas a equipe não o abateu em até 5 segundos. Paredes, visão e habilidades não são verificadas.",
        "O aliado tinha visão e condições de trocar ou a posição apenas parecia próxima no mapa?",
        "Mortes com aliado vivo e proximidade e direção conhecidas",
        context_only=True,
    ),
    "nearby_ally_without_trade": ReviewPattern(
        "Aliado próximo de uma morte sem troca",
        "Estava a até 2000 unidades do adversário que matou um colega e olhando em sua direção, mas a equipe não o abateu em até 5 segundos. A geometria não verifica paredes, visão, habilidades ou condições de agir.",
        "O jogador tinha condições de ajudar o colega ou a posição parecia próxima apenas nas coordenadas?",
        "Mortes de colegas com o jogador vivo e posições e direção conhecidas",
        context_only=True,
    ),
    "trade_kill": ReviewPattern(
        "Abate que trocou um colega",
        "Abateu o adversário que havia matado um colega nos 5 segundos anteriores. Eventos simultâneos também entram e não demonstram uma reação.",
        "Que distância e combinação de contatos permitiram essa troca?",
        "Abates adversários do jogador",
        positive=True,
    ),
    "opening_kill": ReviewPattern(
        "Fez o primeiro abate",
        "Fez o primeiro abate adversário do round quando havia um único abate naquele instante. Aberturas simultâneas não são atribuídas a uma pessoa.",
        "Como repetir a preparação desse primeiro contato?",
        "Rounds com primeiro abate individual identificado e participação do jogador",
        positive=True,
    ),
    "numerical_advantage_lost": ReviewPattern(
        "Vantagem numérica invertida",
        "A equipe chegou a ter mais jogadores vivos e depois ficou com menos que o adversário. Igualar não conta como perda. A mudança pode ocorrer inclusive por ressurreição.",
        "O que mudou entre conseguir a vantagem e passar a ter menos?",
        "Rounds com vantagem numérica observada",
        summary="{occurrences} de {opportunities} rounds tinham vantagem numérica. A equipe chegou a ter mais jogadores vivos e depois ficou com menos que o adversário.",
    ),
    "collapse": ReviewPattern(
        "Três mortes sem resposta em até 10 segundos",
        "Três jogadores diferentes da equipe morreram em até 10 segundos sem abater adversários.",
        "Foi um erro mecânico ou de decisão?",
        "Rounds da equipe",
        summary="{occurrences} de {opportunities} rounds tiveram três jogadores diferentes da equipe mortos em até 10 segundos sem abater adversários.",
    ),
    "won_after_disadvantage": ReviewPattern(
        "Vitória após desvantagem numérica",
        "A equipe venceu um round em que teve menos jogadores vivos em algum instante registrado. Cada round entra uma vez.",
        "Que decisões e contatos ajudaram a recuperar esse round?",
        "Rounds com desvantagem numérica observada",
        positive=True,
    ),
    "lower_starting_equipment": ReviewPattern(
        "Equipamento inicial inferior",
        "O equipamento inicial da equipe valia mais de 5000 créditos a menos que o do adversário. É uma condição do round e não um erro de compra identificado.",
        "O plano de jogo considerou a diferença de equipamento?",
        "Rounds com valor de equipamento conhecido para as duas equipes",
        context_only=True,
    ),
    "attack_without_plant": ReviewPattern(
        "Ataque terminou sem plant",
        "A equipe atacou e o registro não contém um plant. Esse resultado sozinho não informa o motivo nem indica um erro.",
        "Em que momento o plano de ataque perdeu a possibilidade de plantar?",
        "Rounds de ataque com lado identificado",
        context_only=True,
    ),
}

OBSERVATION_COLUMNS = [
    "observation_id",
    "pattern_id",
    "pattern",
    "description",
    "review_question",
    "team_id",
    "player_id",
    "player_name",
    "related_player_id",
    "round",
    "event_index",
    "time_ms",
    "side",
    "won_round",
    "positive",
    "context_only",
    "allies_before",
    "enemies_before",
]
OPPORTUNITY_COLUMNS = [
    "opportunity_id",
    "pattern_id",
    "team_id",
    "player_id",
    "round",
    "event_index",
]
ROUND_COLUMNS = [
    "round",
    "team_id",
    "side",
    "won_round",
    "result",
    "participating_player_ids",
]
PLAYER_COLUMNS = ["player_id", "player_name", "team_id", "round_count"]
PATTERN_SUMMARY_COLUMNS = [
    "pattern_id",
    "pattern",
    "description",
    "occurrences",
    "opportunities",
    "rate",
    "round_count",
    "lost_round_count",
    "round_numbers",
    "positive",
    "context_only",
    "review_question",
    "opportunity_label",
]
ROUND_SUMMARY_COLUMNS = [
    "team_id",
    "round",
    "side",
    "won_round",
    "patterns",
    "occurrences",
    "event_index",
]
PLAYER_SUMMARY_COLUMNS = [
    "player_id",
    "player_name",
    "round_count",
    "occurrences",
    "rounds_with_observations",
    "lost_round_count",
    "positive_occurrences",
]


def _team_slice(table, team_id, player_id=None):
    selected = table[table["team_id"].eq(team_id)]
    if player_id is not None:
        selected = selected[selected["player_id"].eq(player_id)]
    return selected


@dataclass(frozen=True)
class MatchReview:
    observations: pd.DataFrame
    opportunities: pd.DataFrame
    rounds: pd.DataFrame
    players: pd.DataFrame

    def pattern_summary(self, team_id, player_id=None):
        """Frequência por padrão em sua própria base de oportunidades."""
        observations = _team_slice(self.observations, team_id, player_id)
        opportunities = _team_slice(self.opportunities, team_id, player_id)
        rows = []
        for pattern_id, eligible in opportunities.groupby("pattern_id", sort=False):
            pattern = PATTERNS[pattern_id]
            if player_id is None and pattern_id == "opening_kill":
                eligible = eligible.drop_duplicates("round")
            seen = observations[observations["pattern_id"].eq(pattern_id)]
            count = len(seen)
            rows.append(
                {
                    "pattern_id": pattern_id,
                    "pattern": pattern.name,
                    "description": pattern.description,
                    "occurrences": count,
                    "opportunities": len(eligible),
                    "rate": count / len(eligible),
                    "round_count": seen["round"].nunique(),
                    "lost_round_count": seen.loc[seen["won_round"].eq(False), "round"].nunique(),
                    "round_numbers": tuple(sorted(seen["round"].unique())),
                    "positive": pattern.positive,
                    "context_only": pattern.context_only,
                    "review_question": pattern.question,
                    "opportunity_label": (
                        "Rounds com primeiro abate individual identificado"
                        if player_id is None and pattern_id == "opening_kill"
                        else pattern.opportunity_label
                    ),
                }
            )
        result = pd.DataFrame(rows, columns=PATTERN_SUMMARY_COLUMNS)
        return result.sort_values(
            ["lost_round_count", "round_count", "rate", "occurrences", "pattern_id"],
            ascending=[False, False, False, False, True],
            ignore_index=True,
        )

    def round_summary(self, team_id, player_id=None, pattern_id=None):
        """Mantém todos os rounds, inclusive os que não têm observações."""
        rounds = self.rounds[self.rounds["team_id"].eq(team_id)]
        if player_id is not None:
            rounds = rounds[rounds["participating_player_ids"].map(lambda ids: player_id in ids)]
        seen = _team_slice(self.observations, team_id, player_id)
        if pattern_id is not None:
            seen = seen[seen["pattern_id"].eq(pattern_id)]
        rows = []
        for row in rounds.itertuples():
            observations = seen[seen["round"].eq(row.round)]
            priority = observations.sort_values(["positive", "context_only", "time_ms"])
            event_indices = priority["event_index"].dropna()
            rows.append(
                {
                    "team_id": team_id,
                    "round": row.round,
                    "side": row.side,
                    "won_round": row.won_round,
                    "patterns": ", ".join(dict.fromkeys(observations["pattern"])),
                    "occurrences": len(observations),
                    "event_index": int(event_indices.iloc[0]) if len(event_indices) else None,
                }
            )
        return pd.DataFrame(rows, columns=ROUND_SUMMARY_COLUMNS).sort_values(
            "round", ignore_index=True
        )

    def player_summary(self, team_id):
        """Rounds envolvidos são únicos, mesmo com vários sinais no mesmo lance."""
        rows = []
        for player in self.players[self.players["team_id"].eq(team_id)].itertuples():
            seen = _team_slice(self.observations, team_id, player.player_id)
            behaviors = seen[seen["context_only"].eq(False)]
            concerns = behaviors[behaviors["positive"].eq(False)]
            rows.append(
                {
                    "player_id": player.player_id,
                    "player_name": player.player_name,
                    "round_count": player.round_count,
                    "occurrences": len(concerns),
                    "rounds_with_observations": concerns["round"].nunique(),
                    "lost_round_count": concerns.loc[
                        concerns["won_round"].eq(False), "round"
                    ].nunique(),
                    "positive_occurrences": int(behaviors["positive"].sum()),
                }
            )
        return pd.DataFrame(rows, columns=PLAYER_SUMMARY_COLUMNS).sort_values(
            ["lost_round_count", "rounds_with_observations", "player_name"],
            ascending=[False, False, True],
            ignore_index=True,
        )


def _position_known(location):
    return all(
        isinstance(location.get(axis), (int, float)) and math.isfinite(location[axis])
        for axis in ("x", "y")
    )


def _death_details(table, match_id):
    """event_id impede juntar duas mortes da mesma pessoa no mesmo round."""
    if table is None or table.empty or "event_id" not in table:
        return {}
    selected = table[table["match_id"].eq(match_id)] if "match_id" in table else table
    return {(int(row["round"]), row["event_id"]): row for row in selected.to_dict("records")}


def _number(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def build_match_review(match, deaths, rounds=None, styles=None):
    """Constrói a revisão sem reler arquivos ou recalcular as outras partidas.

    ``deaths`` deve ser a tabela de lutas, que inclui a tabela de mortes e a
    geometria de troca. A tabela de mortes simples também funciona, mas não
    habilita o padrão que exige direção do olhar. ``rounds`` traz equipamento
    inicial, quando disponível. ``styles`` é aceito para o mesmo contrato dos
    serviços da aplicação, mas a sequência de mortes é verificada nos eventos.
    """
    roster = {
        player["puuid"]: player
        for player in match.get("players", [])
        if player.get("teamId") in PLAYING_TEAMS and not player.get("isObserver", False)
    }
    teams = {player_id: player["teamId"] for player_id, player in roster.items()}
    names = {player_id: player.get("gameName") or player_id for player_id, player in roster.items()}
    details = _death_details(deaths, match.get("matchInfo", {}).get("matchId"))
    equipment = {}
    if rounds is not None and not rounds.empty:
        selected = rounds
        if "match_id" in selected:
            selected = selected[selected["match_id"].eq(match.get("matchInfo", {}).get("matchId"))]
        equipment = {(int(row["round"]), row["time"]): row for row in selected.to_dict("records")}
    observations, opportunities, round_rows = [], [], []

    for result in match.get("roundResults", []):
        number = int(result["roundNum"]) + 1
        events = round_events(result, teams)
        tactical = [event for event in events if event["tactical_valid"]]
        opening = (
            [event for event in tactical if event["time_ms"] == tactical[0]["time_ms"]]
            if tactical
            else []
        )
        attacker = attacking_team(result)
        participants = {stats.get("puuid") for stats in result.get("playerStats", [])} & set(roster)
        participants.update(
            event[key]
            for event in events
            for key in ("actor", "victim")
            if event.get(key) in roster
        )
        participants.update(
            row["puuid"] for event in events for row in event["locations"] if row["puuid"] in roster
        )
        if not participants:
            participants = set(roster)

        def opportunity(pattern_id, team_id, player_id=None, event=None):
            event_index = event["index"] if event is not None else None
            key = f"{number}|{pattern_id}|{team_id}|{player_id or ''}|{event_index}"
            opportunities.append(
                {
                    "opportunity_id": key,
                    "pattern_id": pattern_id,
                    "team_id": team_id,
                    "player_id": player_id,
                    "round": number,
                    "event_index": event_index,
                }
            )

        def observe(pattern_id, team_id, player_id=None, event=None, related_player_id=None):
            pattern = PATTERNS[pattern_id]
            before = alive_before_puuids(event) if event else set()
            observations.append(
                {
                    "observation_id": f"{number}|{pattern_id}|{team_id}|{player_id or ''}|{event['index'] if event else None}",
                    "pattern_id": pattern_id,
                    "pattern": pattern.name,
                    "description": pattern.description,
                    "review_question": pattern.question,
                    "team_id": team_id,
                    "player_id": player_id,
                    "player_name": names.get(player_id, "Equipe"),
                    "related_player_id": related_player_id,
                    "round": number,
                    "event_index": event["index"] if event else None,
                    "time_ms": event["time_ms"] if event else None,
                    "side": (
                        "?" if attacker is None else ("ataque" if team_id == attacker else "defesa")
                    ),
                    "won_round": result.get("winningTeam") == team_id,
                    "positive": pattern.positive,
                    "context_only": pattern.context_only,
                    "allies_before": (
                        sum(teams.get(player) == team_id for player in before) if event else None
                    ),
                    "enemies_before": (
                        sum(
                            teams.get(player) in PLAYING_TEAMS and teams.get(player) != team_id
                            for player in before
                        )
                        if event
                        else None
                    ),
                }
            )

        for team in sorted(PLAYING_TEAMS):
            round_rows.append(
                {
                    "round": number,
                    "team_id": team,
                    "side": (
                        "?" if attacker is None else ("ataque" if team == attacker else "defesa")
                    ),
                    "won_round": result.get("winningTeam") == team,
                    "result": result.get("roundResult", ""),
                    "participating_player_ids": tuple(
                        sorted(player for player in participants if teams.get(player) == team)
                    ),
                }
            )
            opportunity("collapse", team)
            loadout = equipment.get((number, team), {})
            own, enemy = loadout.get("loadout"), loadout.get("loadout_adversario")
            if _number(own) and _number(enemy):
                opportunity("lower_starting_equipment", team)
                if own - enemy < -5000:
                    observe("lower_starting_equipment", team)
            if team == attacker:
                opportunity("attack_without_plant", team)
                if not any(event["kind"] == "plant" for event in events):
                    observe("attack_without_plant", team)

        if len(opening) == 1:
            first = opening[0]
            for player in sorted(participants):
                opportunity("opening_kill", teams[player], player, first)
            observe("opening_kill", teams[first["actor"]], first["actor"], first, first["victim"])

        for event in tactical:
            victim, actor = event["victim"], event["actor"]
            victim_team, actor_team = teams[victim], teams[actor]
            opportunity("trade_kill", actor_team, actor, event)
            traded_teammates = [
                candidate
                for candidate in tactical
                if candidate["actor"] == victim
                and teams.get(candidate["victim"]) == actor_team
                and 0 <= event["time_ms"] - candidate["time_ms"] <= 5000
            ]
            if traded_teammates:
                previous = max(traded_teammates, key=lambda candidate: candidate["time_ms"])
                observe("trade_kill", actor_team, actor, event, previous["victim"])
            known_alive = alive_puuids(event)
            known_allies = {
                player
                for player in known_alive
                if teams.get(player) == victim_team and player != victim
            }
            allies = [
                row
                for row in event["locations"]
                if teams.get(row["puuid"]) == victim_team
                and row["puuid"] != victim
                and row["puuid"] in known_alive
                and _position_known(row.get("location", {}))
            ]
            geometry_known = (
                event["snapshot_available"]
                and bool(allies)
                and {row["puuid"] for row in allies} == known_allies
                and _position_known(event.get("victim_location", {}))
            )
            detail = details.get((number, event["event_id"]), {})
            traded = was_traded(event, events, teams)
            actor_location = next(
                (
                    row["location"]
                    for row in event["locations"]
                    if row["puuid"] == actor and _position_known(row.get("location", {}))
                ),
                None,
            )
            if actor_location is not None:
                for ally in allies:
                    if not _number(ally.get("viewRadians")):
                        continue
                    ally_id = ally["puuid"]
                    opportunity("nearby_ally_without_trade", victim_team, ally_id, event)
                    distance_to_actor = math.hypot(
                        ally["location"]["x"] - actor_location["x"],
                        ally["location"]["y"] - actor_location["y"],
                    )
                    if (
                        not traded
                        and distance_to_actor <= TRADE_RANGE
                        and facing_angle(ally, actor_location) <= FACING_DEGREES
                    ):
                        observe("nearby_ally_without_trade", victim_team, ally_id, event, victim)
            if geometry_known:
                location = event["victim_location"]
                nearest = min(
                    math.hypot(
                        row["location"]["x"] - location["x"], row["location"]["y"] - location["y"]
                    )
                    for row in allies
                )
                isolated = nearest > SOLO_DISTANCE
                opportunity("isolated_death", victim_team, victim, event)
                if isolated:
                    observe("isolated_death", victim_team, victim, event, actor)
                if len(opening) == 1 and event["event_id"] == opening[0]["event_id"]:
                    opportunity("isolated_opening_untraded", victim_team, victim, event)
                    if isolated and not traded:
                        observe("isolated_opening_untraded", victim_team, victim, event, actor)
                region = detail.get("regiao")
                if (
                    len(allies) >= 2
                    and isinstance(region, str)
                    and region not in {"", "?"}
                    and "aliados_mesma_regiao" in detail
                ):
                    opportunity("away_from_group", victim_team, victim, event)
                    if isolated and detail["aliados_mesma_regiao"] is True:
                        observe("away_from_group", victim_team, victim, event, actor)
                possible = detail.get("troca_possivel")
                if isinstance(possible, str) and possible not in {"", "?"}:
                    opportunity("untraded_with_nearby_ally", victim_team, victim, event)
                    if possible == TRADE_POSSIBLE and not traded:
                        observe("untraded_with_nearby_ally", victim_team, victim, event, actor)

        # Só se avaliam estados observados. Um grupo simultâneo é uma mudança.
        groups = [list(group) for _, group in groupby(tactical, key=lambda event: event["time_ms"])]
        for team in sorted(PLAYING_TEAMS):
            advantage = False
            disadvantage = None
            lost = None
            previous_after = None
            for group in groups:
                event = group[0]
                if not event["snapshot_available"]:
                    continue

                def difference(alive):
                    return sum(teams.get(player) == team for player in alive) - sum(
                        teams.get(player) in PLAYING_TEAMS and teams.get(player) != team
                        for player in alive
                    )

                before, after = difference(alive_before_puuids(event)), difference(
                    alive_puuids(event)
                )
                # A perda só conta quando a equipe, depois de ter estado à frente, fica atrás. Igualar é uma troca, não uma perda.
                was_ahead = advantage or before > 0
                advantage |= before > 0 or after > 0
                if (before < 0 or after < 0) and disadvantage is None:
                    disadvantage = event
                if (
                    was_ahead
                    and previous_after is not None
                    and previous_after >= 0
                    and before < 0
                    and lost is None
                ):
                    # Uma ressurreição pode inverter a vantagem entre snapshots.
                    # Este evento permite localizar a observação, não a causa.
                    lost = event
                elif was_ahead and before >= 0 and after < 0 and lost is None:
                    lost = next(
                        (candidate for candidate in group if candidate["victim_team"] == team),
                        event,
                    )
                previous_after = after
            if advantage:
                opportunity("numerical_advantage_lost", team)
                if lost is not None:
                    observe("numerical_advantage_lost", team, event=lost)
            if disadvantage is not None:
                opportunity("won_after_disadvantage", team)
                if result.get("winningTeam") == team:
                    observe("won_after_disadvantage", team, event=disadvantage)

            team_deaths = [event for event in tactical if event["victim_team"] == team]
            for start, event in enumerate(team_deaths):
                victims = set()
                collapsed = False
                for candidate in team_deaths[start:]:
                    if candidate["time_ms"] - event["time_ms"] > 10000:
                        break
                    victims.add(candidate["victim"])
                    if len(victims) < 3:
                        continue
                    own_kill = any(
                        kill["actor_team"] == team
                        and event["time_ms"] <= kill["time_ms"] <= candidate["time_ms"]
                        for kill in tactical
                    )
                    if not own_kill:
                        observe("collapse", team, event=event)
                        collapsed = True
                    break
                if collapsed:
                    break

    observation_frame = pd.DataFrame(observations, columns=OBSERVATION_COLUMNS).drop_duplicates(
        "observation_id", ignore_index=True
    )
    opportunity_frame = pd.DataFrame(opportunities, columns=OPPORTUNITY_COLUMNS).drop_duplicates(
        "opportunity_id", ignore_index=True
    )
    round_frame = pd.DataFrame(round_rows, columns=ROUND_COLUMNS).drop_duplicates(
        ["round", "team_id"], ignore_index=True
    )
    player_rows = [
        {
            "player_id": player,
            "player_name": names[player],
            "team_id": teams[player],
            "round_count": sum(player in ids for ids in round_frame["participating_player_ids"]),
        }
        for player in roster
    ]
    return MatchReview(
        observation_frame,
        opportunity_frame,
        round_frame,
        pd.DataFrame(player_rows, columns=PLAYER_COLUMNS),
    )
