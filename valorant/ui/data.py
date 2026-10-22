"""Leitura e cache das análises. A seleção de partidas faz parte da chave do cache."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from valorant.analysis.economy import build_rounds_table
from valorant.data.fields import (
    DEFAULT_DATA_DIR,
    collect_field_stats,
    find_match_files,
    load_match,
    split_irrelevant_fields,
    summarize_fields,
)
from valorant.data.metadata import load_maps_by_url
from valorant.data.quality import dataset_quality, eligible_match_ids
from valorant.analysis.plants import build_plants_table
from valorant.analysis.prediction import (
    forecast_accuracy,
    in_match_accuracy,
    load_matches,
    match_pairs,
    permutation_ceiling,
    team_features,
    tournament_ranking,
)
from valorant.analysis.round_style import build_round_styles
from valorant.analysis.setups import build_setups_table
from valorant.analysis.fights import build_fights_table
from valorant.analysis.state_reference import build_state_table
from valorant.analysis.deaths import build_deaths_table


def match_row(match_file, match):
    info = match["matchInfo"]
    rounds_won_by_team = {team["teamId"]: team["roundsWon"] for team in match["teams"]}
    return {
        "match_id": info["matchId"],
        "torneio": "/".join(match_file.parent.relative_to(DEFAULT_DATA_DIR).parts[1:]),
        "arquivo": match_file.name,
        "caminho": str(match_file),
        "mapa_interno": info["mapId"].rsplit("/", 1)[-1],
        "mapa_do_arquivo": match_file.stem.rsplit("_", 1)[-1],
        "inicio": datetime.fromtimestamp(
            info["gameStartMillis"] / 1000, tz=ZoneInfo("America/Sao_Paulo")
        ),
        "duracao_min": round(info["gameLengthMillis"] / 60000, 1),
        "versao": info["gameVersion"],
        "rounds_blue": rounds_won_by_team.get("Blue"),
        "rounds_red": rounds_won_by_team.get("Red"),
    }


def player_row(match_id, player):
    stats = player["stats"]
    return {
        "match_id": match_id,
        "puuid": player["puuid"],
        "jogador": f"{player['gameName']}#{player['tagLine']}",
        "time": player["teamId"],
        "agente": player["characterId"],
        "kills": stats["kills"],
        "deaths": stats["deaths"],
        "assists": stats["assists"],
        "score": stats["score"],
        "rounds": stats["roundsPlayed"],
    }


def round_row(match_id, round_result):
    return {
        "match_id": match_id,
        "round": round_result["roundNum"] + 1,
        "resultado": round_result["roundResult"],
        "time_vencedor": round_result["winningTeam"],
        "lado_vencedor": round_result["winningTeamRole"],
        "cerimonia": round_result["roundCeremony"],
        "spike_plantada": round_result["bombPlanter"] is not None,
        "site": round_result.get("plantSite"),
    }


def map_names_from_file_names(matches):
    """O nome do mapa vem do fim do nome do arquivo; vota o mais comum por nome interno do mapId."""
    return (
        matches.groupby("mapa_interno")["mapa_do_arquivo"]
        .agg(lambda names: names.mode()[0])
        .to_dict()
    )


@st.cache_data(show_spinner=False)
def load_inventory(signature):
    match_rows, player_rows, round_rows = ([], [], [])
    for match_file in find_match_files(DEFAULT_DATA_DIR):
        match = load_match(match_file)
        match_id = match["matchInfo"]["matchId"]
        match_rows.append(match_row(match_file, match))
        player_rows += [
            player_row(match_id, player) for player in match["players"] if not player["isObserver"]
        ]
        round_rows += [round_row(match_id, rr) for rr in match["roundResults"]]
    matches = pd.DataFrame(match_rows)
    if not matches.empty:
        matches["mapa"] = matches["mapa_interno"].map(map_names_from_file_names(matches))
    return (matches, pd.DataFrame(player_rows), pd.DataFrame(round_rows))


@st.cache_data(show_spinner=False)
def load_field_tables(signature, match_ids):
    paths = [
        path
        for path in find_match_files(DEFAULT_DATA_DIR)
        if load_match(path)["matchInfo"]["matchId"] in match_ids
    ]
    types_by_field, values_by_field = collect_field_stats(paths)
    relevant, irrelevant = split_irrelevant_fields(
        summarize_fields(types_by_field, values_by_field)
    )
    columns = ["campo", "tipos", "ocorrencias", "distintos", "mais_frequentes"]
    return (pd.DataFrame(relevant, columns=columns), pd.DataFrame(irrelevant, columns=columns))


@st.cache_data(show_spinner=False)
def load_quality(signature, include_anomalous):
    return (dataset_quality(), eligible_match_ids(include_anomalous=include_anomalous))


@st.cache_data(show_spinner=False)
def load_map_metadata(signature):
    return load_maps_by_url()


@st.cache_data(show_spinner=False)
def load_analysis_table(signature, match_ids, kind):
    ids = set(match_ids)
    if kind == "deaths":
        return build_deaths_table(match_ids=ids)
    if kind == "rounds":
        return build_rounds_table(match_ids=ids)
    if kind == "plants":
        return build_plants_table(match_ids=ids)
    if kind == "matches":
        return load_matches(match_ids=ids)
    if kind == "fights":
        return build_fights_table(
            load_analysis_table(signature, match_ids, "deaths"), match_ids=ids
        )
    if kind == "styles":
        return build_round_styles(
            load_analysis_table(signature, match_ids, "deaths"),
            load_analysis_table(signature, match_ids, "rounds"),
            load_analysis_table(signature, match_ids, "matches"),
            match_ids=ids,
        )
    if kind == "setups":
        return build_setups_table(match_ids=ids)
    raise ValueError(f"Tabela desconhecida: {kind}")


@st.cache_data(show_spinner=False)
def load_state_references(signature, match_ids, exclude_match_id):
    return build_state_table(
        load_analysis_table(signature, match_ids, "deaths"),
        load_analysis_table(signature, match_ids, "plants"),
        load_analysis_table(signature, match_ids, "rounds"),
        exclude_match_id=exclude_match_id,
    )


@st.cache_data(show_spinner=False)
def load_predictions(signature, match_ids):
    matches = load_analysis_table(signature, match_ids, "matches")
    features = team_features(load_analysis_table(signature, match_ids, "deaths"), matches)
    pairs = match_pairs(matches, features)
    chance_95, chance_median = permutation_ceiling(pairs)
    return {
        "dentro": in_match_accuracy(pairs),
        "acaso": (chance_median, chance_95),
        "outras": forecast_accuracy(matches, features, only_previous=False),
        "anteriores": forecast_accuracy(matches, features, only_previous=True),
        "rankings": tournament_ranking(matches, features),
    }


@st.cache_data(show_spinner=False)
def load_match_review(signature, match_ids, match):
    from valorant.analysis.post_match import build_match_review

    match_id = match["matchInfo"]["matchId"]
    if match_id not in match_ids:
        raise ValueError("A partida está fora da seleção atual")
    scoped_ids = (match_id,)
    return build_match_review(
        match,
        load_analysis_table(signature, scoped_ids, "fights"),
        load_analysis_table(signature, scoped_ids, "rounds"),
    )


@st.cache_data(show_spinner=False)
def load_research(signature, match_ids):
    from valorant.analysis.research import build_research_data

    inventory = load_inventory(signature)[0]
    selected = inventory[inventory["match_id"].isin(match_ids)]
    records = [(info, load_match(Path(info["caminho"]))) for info in selected.to_dict("records")]
    return build_research_data(
        records,
        load_analysis_table(signature, match_ids, "fights"),
        load_analysis_table(signature, match_ids, "rounds"),
    )


@st.cache_data(show_spinner=False)
def load_rank_comparison(signature, match_ids, tournament, minimum_matches, performance):
    from valorant.analysis.research import team_ranking
    from valorant.analysis.rank_comparison import bootstrap_comparison

    matches = load_research(signature, match_ids).team_matches
    if tournament is not None:
        matches = matches[matches["torneio"].eq(tournament)]
    ranking = team_ranking(matches, minimum_matches)
    return bootstrap_comparison(matches, ranking, performance)


class AnalysisData:
    """Fornece as tabelas de uma seleção sem depender de variáveis globais."""

    def __init__(self, data_version: str, match_ids: tuple[str, ...]):
        self.data_version = data_version
        self.match_ids = match_ids

    def match_table(self, match_id, name):
        if match_id not in self.match_ids:
            raise ValueError("A partida está fora da seleção atual")
        return load_analysis_table(self.data_version, (match_id,), name)

    def match_review(self, match):
        return load_match_review(self.data_version, self.match_ids, match)

    def research(self):
        return load_research(self.data_version, self.match_ids)

    def rank_comparison(self, tournament, minimum_matches, performance):
        return load_rank_comparison(self.data_version, self.match_ids, tournament, minimum_matches, performance)

    def table(self, name):
        return load_analysis_table(self.data_version, self.match_ids, name)

    def deaths(self):
        return self.table("deaths")

    def rounds(self):
        return self.table("rounds")

    def plants(self):
        return self.table("plants")

    def matches(self):
        return self.table("matches")

    def fights(self):
        return self.table("fights")

    def styles(self):
        return self.table("styles")

    def setups(self):
        return self.table("setups")

    def first_blood(self):
        from valorant.analysis.first_blood import first_blood_table

        return first_blood_table(self.deaths())

    def maps(self):
        return load_map_metadata(self.data_version)

    def states(self, exclude_match_id):
        return load_state_references(self.data_version, self.match_ids, exclude_match_id)

    def predictions(self):
        return load_predictions(self.data_version, self.match_ids)

    def fields(self):
        return load_field_tables(self.data_version, self.match_ids)

    def with_team_names(self, table, team_column, name_column="nome_time"):
        """Usa o nome da equipe, mantendo a cor quando o arquivo não trouxer nome."""
        names = {
            (row.match_id, color): getattr(row, f"nome_{color.lower()}")
            for row in self.matches().itertuples()
            for color in ["Blue", "Red"]
        }
        return table.assign(
            **{
                name_column: [
                    names.get((match_id, team), team)
                    for match_id, team in zip(table["match_id"], table[team_column])
                ]
            }
        )
