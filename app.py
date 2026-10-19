"""Painel local para explorar as partidas do hackathon.

Uso: streamlit run app.py
"""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from explore_fields import DEFAULT_DATA_DIR, collect_field_stats, find_match_files, load_match, split_irrelevant_fields, summarize_fields
from maps import load_maps_by_url
from round_map import describe_event, draw_round_map, round_events
from solo_deaths import SOLO_DISTANCE, build_deaths_table, distance_bands, first_death_summary, summary_by_distance_band, summary_by_round_outcome, with_solo_flag

st.set_page_config(page_title="VALORANT Hackathon", layout="wide")

# Paleta fixa das duas séries de resultado, validada para daltonismo com o validador do skill de dataviz
LOST_COLOR = "#ff7f0e"
WON_COLOR = "#1f77b4"
TRADE_COLOR = "#2ca02c"
ROUND_OUTCOME_LABELS = {False: "perdeu o round", True: "venceu o round"}
MATCH_OUTCOME_LABELS = {False: "perdeu a partida", True: "venceu a partida"}


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
        "inicio": datetime.fromtimestamp(info["gameStartMillis"] / 1000, tz=timezone.utc),
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
        "jogador": f'{player["gameName"]}#{player["tagLine"]}',
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
    return matches.groupby("mapa_interno")["mapa_do_arquivo"].agg(lambda names: names.mode()[0]).to_dict()


@st.cache_data
def build_tables():
    match_rows, player_rows, round_rows = [], [], []
    for match_file in find_match_files(DEFAULT_DATA_DIR):
        match = load_match(match_file)
        match_id = match["matchInfo"]["matchId"]
        match_rows.append(match_row(match_file, match))
        player_rows += [player_row(match_id, player) for player in match["players"] if not player["isObserver"]]
        round_rows += [round_row(match_id, round_result) for round_result in match["roundResults"]]
    matches = pd.DataFrame(match_rows)
    matches["mapa"] = matches["mapa_interno"].map(map_names_from_file_names(matches))
    return matches, pd.DataFrame(player_rows), pd.DataFrame(round_rows)


@st.cache_data
def build_field_tables():
    types_by_field, values_by_field = collect_field_stats(find_match_files(DEFAULT_DATA_DIR))
    relevant_rows, irrelevant_rows = split_irrelevant_fields(summarize_fields(types_by_field, values_by_field))
    return pd.DataFrame(relevant_rows), pd.DataFrame(irrelevant_rows)


@st.cache_data
def maps_by_url():
    return load_maps_by_url()


@st.cache_data
def deaths_table():
    return build_deaths_table()


def deaths_per_round_table(match_deaths, round_results):
    """Por round da partida: vencedor e, para cada time, mortes, isoladas e trocadas."""
    per_round = match_deaths.groupby(["round", "time_vitima"]).agg(mortes=("vitima", "size"), isoladas=("isolada", "sum"), trocadas=("trocada", "sum"))
    per_round = per_round.unstack("time_vitima").fillna(0).astype(int)
    per_round.columns = [f"{team} {stat}" for stat, team in per_round.columns]
    winner_by_round = {round_result["roundNum"] + 1: round_result["winningTeam"] for round_result in round_results}
    attacker_by_round = {round_result["roundNum"] + 1: attacking_team(round_result) for round_result in round_results}
    per_round.insert(0, "vencedor", per_round.index.map(winner_by_round))
    per_round.insert(0, "atacante", per_round.index.map(attacker_by_round))
    return per_round.reset_index()


def attacking_team(round_result):
    other_team = {"Blue": "Red", "Red": "Blue"}
    winner = round_result["winningTeam"]
    return winner if round_result["winningTeamRole"] == "Attacker" else other_team[winner]


def players_summary(players):
    summary = players.groupby("puuid").agg(
        jogador=("jogador", "last"), partidas=("match_id", "nunique"), kills=("kills", "sum"),
        deaths=("deaths", "sum"), assists=("assists", "sum"), rounds=("rounds", "sum"), score=("score", "sum"),
    )
    summary["kd"] = (summary["kills"] / summary["deaths"].replace(0, 1)).round(2)
    summary["score_por_round"] = (summary["score"] / summary["rounds"]).round(0)
    return summary.sort_values("kills", ascending=False).reset_index(drop=True)


matches, players, rounds = build_tables()

all_tournaments = sorted(matches["torneio"].unique())
chosen_tournaments = st.sidebar.multiselect("Torneios", all_tournaments, default=all_tournaments)
selected_matches = matches[matches["torneio"].isin(chosen_tournaments)]
selected_ids = set(selected_matches["match_id"])
selected_players = players[players["match_id"].isin(selected_ids)]
selected_rounds = rounds[rounds["match_id"].isin(selected_ids)]

overview_tab, players_tab, deaths_tab, fields_tab, match_tab = st.tabs(["Visão geral", "Jogadores", "Mortes isoladas", "Campos", "Partida"])

with overview_tab:
    matches_col, players_col, rounds_col = st.columns(3)
    matches_col.metric("Partidas", len(selected_matches))
    players_col.metric("Jogadores distintos", selected_players["puuid"].nunique())
    rounds_col.metric("Rounds", len(selected_rounds))
    st.subheader("Partidas por mapa")
    st.bar_chart(selected_matches["mapa"].value_counts(), horizontal=True)
    st.subheader("Como os rounds terminam")
    st.bar_chart(selected_rounds["resultado"].value_counts(), horizontal=True)
    st.subheader("Partidas")
    st.dataframe(selected_matches.drop(columns=["match_id", "caminho", "mapa_interno", "mapa_do_arquivo"]), hide_index=True)

with players_tab:
    st.dataframe(players_summary(selected_players), hide_index=True)

with deaths_tab:
    st.markdown("Para cada morte, a distância da vítima ao aliado vivo mais próximo naquele instante. Isolada quando passa do limite. Trocada quando o killer morre em até 5 s. Tudo dividido pelo lado da vítima no round.")
    solo_distance = st.slider("Limite de isolamento (unidades de jogo, ~100 por metro)", 500, 3000, SOLO_DISTANCE, step=250)
    selected_deaths = deaths_table()[deaths_table()["match_id"].isin(selected_ids)]
    deaths_with_allies = with_solo_flag(selected_deaths, solo_distance)
    st.caption(f"{len(selected_deaths)} mortes, {len(deaths_with_allies)} com algum aliado vivo (só essas têm distância).")

    st.subheader("Por lado e resultado do round da vítima")
    st.dataframe(summary_by_round_outcome(deaths_with_allies, ["lado"]).rename(index=ROUND_OUTCOME_LABELS, level="venceu_round"), use_container_width=False)

    for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
        side_deaths = deaths_with_allies[deaths_with_allies["lado"] == side]
        side_column.header(side.capitalize())
        side_column.markdown("**Onde as mortes acontecem: distância ao aliado mais próximo**")
        distribution = pd.crosstab(distance_bands(side_deaths), side_deaths["venceu_round"], normalize="columns").rename(columns=ROUND_OUTCOME_LABELS)
        side_column.bar_chart(distribution, color=[LOST_COLOR, WON_COLOR], stack=False, y_label="fração das mortes")
        side_column.markdown("**Por faixa de distância: chance de trade e de vencer o round**")
        side_column.bar_chart(summary_by_distance_band(side_deaths)[["fracao_trocadas", "venceu_round"]], color=[TRADE_COLOR, WON_COLOR], stack=False, y_label="fração")
        side_column.markdown("**Primeira morte do round: o que decide é o trade**")
        first_deaths = first_death_summary(side_deaths).reset_index()
        first_deaths["isolada"] = first_deaths["isolada"].map({False: "acompanhada", True: "isolada"})
        first_deaths["trocada"] = first_deaths["trocada"].map({False: "não trocada", True: "trocada"})
        side_column.dataframe(first_deaths, hide_index=True, use_container_width=False)
        side_column.markdown("**Ao longo da partida: fração de mortes isoladas por round**")
        regular_rounds = side_deaths[side_deaths["round"] <= 24]
        trend = regular_rounds.groupby(["round", "venceu_partida"])["isolada"].mean().unstack().rename(columns=MATCH_OUTCOME_LABELS)
        side_column.line_chart(trend, color=[LOST_COLOR, WON_COLOR], y_label="fração isolada")

with fields_tab:
    relevant_fields, irrelevant_fields = build_field_tables()
    field_filter = st.text_input("Filtrar campo")
    st.dataframe(relevant_fields[relevant_fields["campo"].str.contains(field_filter, regex=False)], hide_index=True)
    with st.container(border=True):
        st.subheader("Dados irrelevantes")
        st.caption("Campos com um único valor em toda a base e sem subcampos. Não diferenciam partida, jogador nem round.")
        st.dataframe(irrelevant_fields.drop(columns=["distintos"]).rename(columns={"mais_frequentes": "valor"}), hide_index=True)

with match_tab:
    chosen_file = st.selectbox("Partida", selected_matches["arquivo"].tolist())
    chosen_match = selected_matches[selected_matches["arquivo"] == chosen_file].iloc[0]
    match = load_match(Path(chosen_match["caminho"]))
    st.write(f'{chosen_match["torneio"]} · {chosen_match["mapa"]} · Blue {chosen_match["rounds_blue"]} x {chosen_match["rounds_red"]} Red')

    st.subheader("Mapa do round")
    name_by_puuid = {player["puuid"]: f'{player["gameName"]}#{player["tagLine"]}' for player in match["players"]}
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    player_column, round_column = st.columns(2)
    playing_puuids = [player["puuid"] for player in match["players"] if not player["isObserver"]]
    selected_puuid = player_column.selectbox("Jogador", playing_puuids, format_func=lambda puuid: f"{name_by_puuid[puuid]} ({team_by_puuid[puuid]})")
    round_index = round_column.selectbox("Round", range(len(match["roundResults"])), format_func=lambda index: f"Round {index + 1}")
    round_result = match["roundResults"][round_index]
    events = round_events(round_result)
    map_meta = maps_by_url().get(match["matchInfo"]["mapId"])
    if map_meta is None:
        st.info("Sem metadado de mapa para este mapId.")
    elif not events:
        st.info("Este round não tem kill, plant nem defuse, então não há posição registrada.")
    else:
        event_index = st.slider("Momento", 0, len(events) - 1, 0, format="evento %d") if len(events) > 1 else 0
        st.caption(describe_event(events[event_index], name_by_puuid, round_result))
        map_column, _ = st.columns([4, 1])
        map_column.pyplot(draw_round_map(map_meta, events, event_index, selected_puuid, team_by_puuid, name_by_puuid))

    st.subheader("Mortes isoladas e trades por round")
    match_deaths = with_solo_flag(deaths_table()[deaths_table()["match_id"] == chosen_match["match_id"]], SOLO_DISTANCE)
    st.dataframe(deaths_per_round_table(match_deaths, match["roundResults"]), hide_index=True)

    st.subheader("Jogadores")
    match_players = players[players["match_id"] == chosen_match["match_id"]].drop(columns=["match_id", "puuid"])
    st.dataframe(match_players.sort_values(["time", "score"], ascending=[True, False]), hide_index=True)
    st.subheader("Rounds")
    st.dataframe(rounds[rounds["match_id"] == chosen_match["match_id"]].drop(columns=["match_id"]), hide_index=True)
    with st.expander("matchInfo bruto"):
        st.json(match["matchInfo"])
