"""Painel local para explorar as partidas do hackathon.

Uso: streamlit run app.py
"""
from datetime import datetime, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from agent_roles import ROLE_ORDER, death_cost_by_role, first_death_by_agent, first_death_by_role, first_death_by_role_and_trade, role_share
from economy import after_previous_round, after_streak, build_rounds_table, close_match_ids, pistol_by_side, second_round_cycle, versus_full_buy, win_rate_by_loadout, win_rate_matrix
from explore_fields import DEFAULT_DATA_DIR, collect_field_stats, find_match_files, load_match, split_irrelevant_fields, summarize_fields
from maps import callout_name, load_maps_by_url, nearest_callout
from plants import build_plants_table, cells_for_map, situation_matrix, summary_by_plant_time, summary_by_site
from predict import forecast_accuracy, in_match_accuracy, load_matches, match_pairs, permutation_ceiling, team_features, tournament_ranking
from round_map import describe_event, draw_callout_summary, draw_points, draw_rate_markers, draw_round_map, round_events
from first_blood import first_blood_table, plant_summary, summary_by_map, who_opens_by_time, wilson_interval, win_rate_by_time
from solo_deaths import SOLO_DISTANCE, build_deaths_table, context_summary, distance_bands, first_death_summary, summary_by_distance_band, summary_by_round_outcome, territory_summary, win_rate_by_situation, with_solo_flag

st.set_page_config(page_title="VALORANT Hackathon", layout="wide")

# Paleta fixa das duas séries de resultado, validada para daltonismo com o validador do skill de dataviz
LOST_COLOR = "#ff7f0e"
WON_COLOR = "#1f77b4"
TRADE_COLOR = "#2ca02c"
ATTACK_COLOR = "#c0392b"
DEFENSE_COLOR = "#2a9d8f"
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


@st.cache_data
def first_blood_rows():
    return first_blood_table(deaths_table())


@st.cache_data
def rounds_table():
    return build_rounds_table()


@st.cache_data
def plants_table():
    return build_plants_table()


@st.cache_data
def prediction_tables():
    matches = load_matches()
    features = team_features(deaths_table(), matches)
    pairs = match_pairs(matches, features)
    chance_95, chance_median = permutation_ceiling(pairs)
    return {
        "dentro": in_match_accuracy(pairs),
        "acaso": (chance_median, chance_95),
        "outras": forecast_accuracy(matches, features, only_previous=False),
        "anteriores": forecast_accuracy(matches, features, only_previous=True),
        "rankings": tournament_ranking(matches, features),
    }


def quantile_band_chart(per_round):
    """Mediana por round com bandas p25 a p75 e p10 a p90: a distribuição é assimétrica, então quantis dizem mais que o desvio padrão."""
    base = alt.Chart(per_round.reset_index()).encode(x=alt.X("round:O", title="round"))
    tooltip = ["round", "rounds", "p10", "p25", "mediana", "p75", "p90", "media", "desvio_padrao"]
    wide_band = base.mark_area(opacity=0.15, color="#7f7f7f").encode(y=alt.Y("p10:Q", title="segundos"), y2="p90:Q", tooltip=tooltip)
    narrow_band = base.mark_area(opacity=0.3, color="#7f7f7f").encode(y="p25:Q", y2="p75:Q", tooltip=tooltip)
    median_line = base.mark_line(color="#4a4a4a", point=True).encode(y="mediana:Q", tooltip=tooltip)
    return (wide_band + narrow_band + median_line).properties(height=320)


def opening_impact_chart(by_map):
    """Barra do impacto da abertura do ataque por mapa, com o intervalo de 95% como traço."""
    data = by_map.reset_index()
    base = alt.Chart(data).encode(y=alt.Y("mapa:N", sort=None, title=None))
    tooltip = ["mapa", "rounds", "ataque_vence_se_abre", "ataque_vence_se_defesa_abre", "impacto_da_abertura", "impacto_ic95_baixo", "impacto_ic95_alto"]
    bars = base.mark_bar(color=ATTACK_COLOR).encode(x=alt.X("impacto_da_abertura:Q", title="diferença entre taxa de vitória quando ataque abre e quando defesa abre"), tooltip=tooltip)
    intervals = base.mark_rule(color="#4a4a4a", strokeWidth=2).encode(x="impacto_ic95_baixo:Q", x2="impacto_ic95_alto:Q", tooltip=tooltip)
    return (bars + intervals).properties(height=30 * len(data))


def rate_by_role_chart(by_role, color, x_title):
    """Barra por função com o intervalo de 95% como traço, para um lado."""
    data = by_role.reset_index()
    base = alt.Chart(data).encode(y=alt.Y("funcao:N", sort=ROLE_ORDER, title=None, axis=alt.Axis(labelOverlap=False)))
    tooltip = ["funcao", "rounds", "trocada", "vitoria_da_vitima", "ic95_baixo", "ic95_alto", "acima_do_time"]
    bars = base.mark_bar(color=color).encode(x=alt.X("vitoria_da_vitima:Q", title=x_title), tooltip=tooltip)
    intervals = base.mark_rule(color="#4a4a4a", strokeWidth=2).encode(x="ic95_baixo:Q", x2="ic95_alto:Q", tooltip=tooltip)
    return (bars + intervals).properties(height=220)


def openings_by_callout(attack_openings, map_meta):
    """Aberturas do ataque agrupadas pela região (callout) mais próxima de onde o defensor morreu."""
    callouts = attack_openings.assign(callout=[nearest_callout(x, y, map_meta) for x, y in zip(attack_openings["vitima_x"], attack_openings["vitima_y"])])
    by_callout = callouts.groupby("callout").agg(aberturas=("round", "size"), ataque_venceu=("abriu_venceu", "mean"))
    by_callout["ic95"] = ["{:.2f} a {:.2f}".format(*wilson_interval(round(rate * count), count)) for rate, count in zip(by_callout["ataque_venceu"], by_callout["aberturas"])]
    location_by_name = {callout_name(callout): (callout["location"]["x"], callout["location"]["y"]) for callout in map_meta["callouts"]}
    by_callout["x"] = [location_by_name[name][0] for name in by_callout.index]
    by_callout["y"] = [location_by_name[name][1] for name in by_callout.index]
    return by_callout.sort_values("aberturas", ascending=False).round(3)


def first_blood_per_round_table(match_first_blood):
    columns = {"round": "round", "segundos": "primeira morte (s)", "time_abriu": "quem abriu", "lado_abriu": "lado", "trocada": "trocada", "antes_do_plant": "antes do plant", "abriu_venceu": "quem abriu venceu"}
    return match_first_blood[list(columns)].rename(columns=columns).round(1)


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

overview_tab, players_tab, deaths_tab, first_blood_tab, roles_tab, economy_tab, plants_tab, fields_tab, match_tab, prediction_tab, conclusions_tab = st.tabs(["Visão geral", "Jogadores", "Mortes isoladas", "Primeira morte", "Função do agente", "Economia", "Plant e defuse", "Campos", "Partida", "Previsão", "Conclusões"])

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
    phase = st.radio("Fase do round", ["todas", "pré-plant", "pós-plant"], horizontal=True, help="Depois do plant a lógica de rotação inverte, a defesa precisa retomar o site.")
    selected_deaths = deaths_table()[deaths_table()["match_id"].isin(selected_ids)]
    if phase != "todas":
        selected_deaths = selected_deaths[selected_deaths["fase"] == phase]
    deaths_with_allies = with_solo_flag(selected_deaths, solo_distance)
    st.caption(f"{len(selected_deaths)} mortes, {len(deaths_with_allies)} com algum aliado vivo (só essas têm distância).")

    st.subheader("Contexto da morte: onde estavam os aliados e em que território")
    context_column, territory_column = st.columns(2)
    context_column.markdown("**Pela posição dos aliados vivos.** Em grupo: algum aliado dentro do limite. Flanco: nenhum perto e todos na mesma área do mapa. Isolado: nenhum perto e aliados espalhados.")
    context_column.dataframe(context_summary(deaths_with_allies, ["lado"]), use_container_width=False)
    territory_column.markdown("**Pelo território da região.** Próprio quando 65% ou mais das posições vivas ali nos primeiros 20 s dos rounds são do lado da vítima, do adversário quando 35% ou menos, disputado no meio.")
    territory_column.dataframe(territory_summary(deaths_with_allies, ["lado"]), use_container_width=False)

    st.subheader("Controlando pelos vivos: vitória do round por situação, sem e com a condição")
    st.caption("Situação é aliados x inimigos vivos na hora da morte. Comparar dentro da mesma situação separa o efeito da condição do efeito de estar em vantagem numérica. Só situações com 60 mortes ou mais.")
    trade_column, proximity_column = st.columns(2)
    trade_column.markdown("**Morte trocada**")
    trade_column.dataframe(win_rate_by_situation(deaths_with_allies, "trocada"), hide_index=True, use_container_width=False)
    deaths_with_allies["aliado_perto"] = ~deaths_with_allies["isolada"]
    proximity_column.markdown("**Aliado perto (não isolada)**")
    proximity_column.dataframe(win_rate_by_situation(deaths_with_allies, "aliado_perto"), hide_index=True, use_container_width=False)

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
        side_column.bar_chart(regular_rounds.groupby("round").size(), color=["#7f7f7f"], y_label="mortes na base")

with first_blood_tab:
    st.markdown("Uma linha por round: quando aconteceu a primeira morte, qual lado abriu o placar e se o time que abriu venceu o round. O tempo conta a partir do round live, sem a fase de compra.")
    first_blood = first_blood_rows()[first_blood_rows()["match_id"].isin(selected_ids)]
    rounds_col, median_col, opener_col = st.columns(3)
    rounds_col.metric("Rounds com morte", len(first_blood))
    median_col.metric("Mediana da primeira morte", f'{first_blood["segundos"].median():.1f} s')
    opener_col.metric("Quem abre vence o round", f'{first_blood["abriu_venceu"].mean():.1%}')

    st.subheader("Quando a primeira morte acontece, por lado de quem abriu")
    opened_counts = pd.crosstab(first_blood["faixa"], first_blood["lado_abriu"])
    st.bar_chart(opened_counts, color=[ATTACK_COLOR, DEFENSE_COLOR], stack=False, y_label="rounds")

    st.subheader("Quem abre vence? Por lado e faixa de tempo")
    win_rate = win_rate_by_time(first_blood)["abriu_venceu"].unstack("lado_abriu")
    st.bar_chart(win_rate, color=[ATTACK_COLOR, DEFENSE_COLOR], stack=False, y_label="fração de rounds vencidos por quem abriu")
    st.dataframe(win_rate_by_time(first_blood), use_container_width=False)

    st.subheader("Antes ou depois do plant")
    st.dataframe(plant_summary(first_blood).rename(index={True: "antes do plant", False: "depois do plant"}, level="antes_do_plant"), use_container_width=False)

    st.subheader("Por mapa: onde a abertura do ataque mais pesa")
    st.caption("Ordenado por rounds. Impacto da abertura é a vitória do ataque quando ele abre menos a vitória do ataque quando a defesa abre. Intervalos de 95%: Wilson para a taxa de abertura, aproximação normal para a diferença.")
    map_name_by_internal = dict(zip(matches["mapa_interno"], matches["mapa"]))
    by_map = summary_by_map(first_blood).rename(index=map_name_by_internal)
    st.dataframe(by_map, use_container_width=False)
    st.altair_chart(opening_impact_chart(by_map), use_container_width=True)

    st.subheader("Onde o ataque faz a primeira kill")
    internal_by_name = {name: internal for internal, name in map_name_by_internal.items()}
    chosen_map_name = st.selectbox("Mapa", list(by_map.index))
    chosen_internal = internal_by_name[chosen_map_name]
    chosen_map_meta = maps_by_url().get(f"/Game/Maps/{chosen_internal}/{chosen_internal}")
    attack_openings = first_blood[(first_blood["mapa"] == chosen_internal) & (first_blood["lado_abriu"] == "ataque") & first_blood["antes_do_plant"]]
    if chosen_map_meta is None:
        st.info("Sem metadado de mapa para este mapId.")
    else:
        by_callout = openings_by_callout(attack_openings, chosen_map_meta)
        map_average = attack_openings["abriu_venceu"].mean()
        st.caption(f"Só aberturas antes do plant. Cada uma é atribuída à região (callout) mais próxima de onde o defensor morreu. Tamanho: número de aberturas. Cor: vitória do ataque ao abrir ali, centrada na média do mapa ({map_average:.0%}).")
        show_every_kill = st.checkbox("Mostrar cada kill em vez das regiões")
        map_column, table_column = st.columns([3, 2])
        if show_every_kill:
            won = attack_openings[attack_openings["abriu_venceu"]]
            lost = attack_openings[~attack_openings["abriu_venceu"]]
            map_column.pyplot(draw_points(chosen_map_meta, [
                ("ataque venceu o round", WON_COLOR, list(zip(won["vitima_x"], won["vitima_y"]))),
                ("ataque perdeu o round", LOST_COLOR, list(zip(lost["vitima_x"], lost["vitima_y"]))),
            ]))
        else:
            map_column.pyplot(draw_callout_summary(chosen_map_meta, by_callout, map_average))
        table_column.dataframe(by_callout[["aberturas", "ataque_venceu", "ic95"]], use_container_width=True)

    st.subheader("Ao longo da partida: tempo da primeira morte por round")
    per_round = first_blood[first_blood["round"] <= 24].groupby("round")["segundos"].agg(
        rounds="size", p10=lambda seconds: seconds.quantile(0.10), p25=lambda seconds: seconds.quantile(0.25), mediana="median",
        p75=lambda seconds: seconds.quantile(0.75), p90=lambda seconds: seconds.quantile(0.90), media="mean", desvio_padrao="std",
    ).round(1)
    st.caption("Linha: mediana. Banda escura: p25 a p75. Banda clara: p10 a p90. A distribuição é assimétrica à direita, por isso quantis em vez de média e desvio padrão, que estão na tabela.")
    band_column, count_column = st.columns([3, 2])
    band_column.altair_chart(quantile_band_chart(per_round), use_container_width=True)
    count_column.bar_chart(per_round["rounds"], color=["#7f7f7f"], y_label="rounds na base")
    with st.expander("Números por round"):
        st.dataframe(per_round, use_container_width=False)

with roles_tab:
    st.markdown("A função do agente (duelista, iniciador, controlador, sentinela) vem da lista pública de agentes, só para dar nome ao characterId. A pergunta: a primeira morte do round e a morte isolada pesam igual para qualquer função? Acima do time é a vitória do round menos a taxa de rounds que o time da vítima venceu na partida inteira, o que desconta a força do time e do adversário.")
    max_seconds = st.slider("Só primeiras mortes até este tempo do round (s)", 10, 150, 150, step=10, key="role_max_seconds")
    role_deaths = deaths_table()[deaths_table()["match_id"].isin(selected_ids)]
    role_first = first_death_by_role(role_deaths, max_seconds)
    st.caption(f"{int(role_first['rounds'].sum())} rounds com primeira morte até {max_seconds} s e função conhecida.")

    st.subheader("Quem morre primeiro")
    st.caption("Fração de cada função entre os jogadores escalados e entre as vítimas da primeira morte, por lado.")
    st.bar_chart(role_share(role_deaths, max_seconds), color=["#7f7f7f", ATTACK_COLOR, DEFENSE_COLOR], stack=False, y_label="fração")

    st.subheader("Quanto a primeira morte custa, por função da vítima")
    st.caption("Vitória do round do time que perdeu o primeiro jogador, com intervalo de 95%. Barras que se sobrepõem no intervalo não são distinguíveis com estes dados.")
    for side_column, side, color in zip(st.columns(2), ["ataque", "defesa"], [ATTACK_COLOR, DEFENSE_COLOR]):
        side_column.markdown(f"**Vítima no {side}**")
        side_column.altair_chart(rate_by_role_chart(role_first.loc[side], color, "vitória do time da vítima"), use_container_width=True)
    st.dataframe(role_first, use_container_width=False)

    st.subheader("Trocada ou não: a função importa quando ninguém troca?")
    st.dataframe(first_death_by_role_and_trade(role_deaths, max_seconds), use_container_width=False)

    st.subheader("Qualquer morte e isolamento, por função")
    st.caption("Toda morte com aliado vivo. Acima do esperado desconta a situação de vivos (lado, aliados x inimigos). Custo do isolamento é a diferença entre morrer isolado e acompanhado, com o mesmo desconto.")
    st.dataframe(death_cost_by_role(with_solo_flag(role_deaths, SOLO_DISTANCE)), use_container_width=False)

    st.subheader("Por agente")
    st.caption("Só agentes com 30 ou mais primeiras mortes no recorte. Diferenças entre agentes misturam o agente com quem costuma escolhê-lo.")
    st.dataframe(first_death_by_agent(role_deaths, max_seconds), use_container_width=False)

with economy_tab:
    st.markdown("Por round e por time: soma do loadout dos cinco jogadores, resultado e cerimônia. Rounds normais excluem pistol (1 e 13) e o segundo round (2 e 14). Vitória esperada pelo dinheiro é a taxa de vitória da faixa de diferença de loadout; o que sobra acima dela é o que não é dinheiro.")
    all_rounds = rounds_table()
    selected_rounds = all_rounds[all_rounds["match_id"].isin(selected_ids)]
    close_rounds = selected_rounds[selected_rounds["match_id"].isin(close_match_ids(selected_rounds))]

    st.subheader("1. Quanto o loadout compra de vitória")
    own_table, difference_table = win_rate_by_loadout(selected_rounds)
    st.bar_chart(difference_table["vitoria"], color=[WON_COLOR], y_label="vitória do round", x_label="loadout do time menos o do adversário")
    full_buy_column, own_column = st.columns(2)
    full_buy_column.markdown("**Contra compra cheia (20k+), rounds normais.** Ganho por 1k a mais é a diferença de vitória para a faixa anterior dividida pela diferença de loadout médio.")
    full_buy_column.dataframe(versus_full_buy(selected_rounds), use_container_width=False)
    own_column.markdown("**Por faixa de loadout do time, todos os rounds.** Lê-se com cuidado: 8-12k é quase sempre force contra compra cheia.")
    own_column.dataframe(own_table, use_container_width=False)
    rates, counts = win_rate_matrix(selected_rounds)
    rates_column, counts_column = st.columns(2)
    rates_column.markdown("**Vitória por loadout do time (linhas) e do adversário (colunas)**")
    rates_column.dataframe(rates, use_container_width=False)
    counts_column.markdown("**Rounds em cada célula**")
    counts_column.dataframe(counts, use_container_width=False)

    st.subheader("2. O round seguinte: perder abala?")
    st.caption("Round fácil perdido é derrota num round em que o adversário fez clutch ou thrifty. Acima do esperado é a vitória real menos a esperada pelo dinheiro do round seguinte.")
    all_column, close_column = st.columns(2)
    all_column.markdown("**Todas as partidas**")
    all_column.dataframe(after_previous_round(selected_rounds), use_container_width=False)
    close_column.markdown(f"**Só partidas equilibradas (até 4 rounds de diferença no placar final, {close_rounds['match_id'].nunique()} partidas)**")
    close_column.dataframe(after_previous_round(close_rounds), use_container_width=False)

    st.subheader("3. Pistol e round 2: eco ou force?")
    pistol_column, cycle_column = st.columns([1, 3])
    pistol_column.markdown("**Pistol por lado**")
    pistol_column.dataframe(pistol_by_side(selected_rounds), use_container_width=False)
    overall_cycle, cycle_by_side = second_round_cycle(selected_rounds)
    cycle_column.markdown("**Perdedor do pistol: compra no round 2 e o que vem depois.** Força do time é a vitória de rounds do round 5 em diante, para ver quem escolhe cada compra.")
    cycle_column.dataframe(overall_cycle, use_container_width=True)
    cycle_column.dataframe(cycle_by_side, use_container_width=True)

    st.subheader("4. Derrotas seguidas")
    all_column, close_column = st.columns(2)
    all_column.markdown("**Todas as partidas**")
    all_column.dataframe(after_streak(selected_rounds), use_container_width=False)
    close_column.markdown("**Só partidas equilibradas**")
    close_column.dataframe(after_streak(close_rounds), use_container_width=False)

with plants_tab:
    st.markdown("Uma linha por round plantado: onde a spike foi plantada, quantos de cada lado estavam vivos no plant e se foi defusada. Esperado pelos vivos é a taxa de defuse da mesma situação (ataque x defesa vivos no plant); acima do esperado é o que a posição ou o mapa acrescentam.")
    selected_plants = plants_table()[plants_table()["match_id"].isin(selected_ids)]
    plants_col, defuse_col, time_col = st.columns(3)
    plants_col.metric("Rounds plantados", len(selected_plants))
    defuse_col.metric("Defusados", f'{selected_plants["defusada"].mean():.1%}')
    time_col.metric("Tempo mediano do plant", f'{selected_plants["segundos_plant"].median():.0f} s')

    st.subheader("Por mapa e site")
    map_name_by_internal = dict(zip(matches["mapa_interno"], matches["mapa"]))
    st.dataframe(summary_by_site(selected_plants).rename(index=map_name_by_internal, level="mapa"), use_container_width=False)

    st.subheader("Defuse por vivos no momento do plant")
    rates, counts = situation_matrix(selected_plants)
    rates_column, counts_column = st.columns(2)
    rates_column.markdown("**Taxa de defuse, ataque vivos (linhas) x defesa vivos (colunas)**")
    rates_column.dataframe(rates, use_container_width=False)
    counts_column.markdown("**Rounds em cada célula**")
    counts_column.dataframe(counts, use_container_width=False)

    st.subheader("Por tempo do plant")
    st.dataframe(summary_by_plant_time(selected_plants), use_container_width=False)

    st.subheader("Onde a spike é plantada e quanto cada posição é defusada")
    internal_by_name = {name: internal for internal, name in map_name_by_internal.items()}
    plant_map_name = st.selectbox("Mapa", list(summary_by_site(selected_plants).index.get_level_values("mapa").map(map_name_by_internal).unique()), key="plant_map")
    plant_map_internal = internal_by_name[plant_map_name]
    plant_map_meta = maps_by_url().get(f"/Game/Maps/{plant_map_internal}/{plant_map_internal}")
    if plant_map_meta is None:
        st.info("Sem metadado de mapa para este mapId.")
    else:
        cells = cells_for_map(selected_plants, plant_map_internal)
        map_defuse = selected_plants[selected_plants["mapa"] == plant_map_internal]["defusada"].mean()
        st.caption(f"Plants agrupados em células de 400 unidades (cerca de 4 m) e só células com 5 ou mais, um recorte por site. Tamanho: plants. Cor: taxa de defuse, centrada na média do mapa ({map_defuse:.0%}). Azul é bom para a defesa.")
        sites = sorted(cells["site"].unique())
        for site_column, site in zip(st.columns(len(sites)), sites):
            site_cells = cells[cells["site"] == site]
            site_column.markdown(f"**Site {site}** ({int(site_cells['plants'].sum())} plants em células com 5+)")
            site_column.pyplot(draw_rate_markers(plant_map_meta, site_cells, "plants", "defuse", map_defuse, "taxa de defuse", label_min_count=10, size_per_unit=3, zoom_padding=90))
        st.dataframe(cells[["site", "plants", "defuse", "esperado_pelos_vivos", "acima_do_esperado"]], use_container_width=False)

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

    st.subheader("Primeira morte por round")
    st.dataframe(first_blood_per_round_table(first_blood_rows()[first_blood_rows()["match_id"] == chosen_match["match_id"]]), hide_index=True)

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

with prediction_tab:
    st.markdown("As métricas das conclusões, sem nenhum resultado dentro delas, explicam e preveem partidas? O lado de cada round vem de quem planta a spike na metade, não há contagem de rounds, placar nem ordem, e o rótulo é só o vencedor da partida. Times vêm do nome do arquivo. Esta aba ignora o filtro de torneios.")
    prediction = prediction_tables()
    chance_median, chance_95 = prediction["acaso"]
    st.subheader("1. Dentro da partida, rounds embaralhados")
    st.caption(f"O time com a métrica melhor na própria partida venceu? Acaso com rótulos embaralhados: mediana {chance_median:.1%}, percentil 95 {chance_95:.1%}.")
    st.dataframe(prediction["dentro"], hide_index=True, use_container_width=False)
    st.subheader("2. Previsão com o perfil do time nas outras partidas do campeonato")
    st.caption("Pelo menos duas outras partidas para cada time. A última linha é a base de comparação: a taxa de vitória do time nas outras partidas.")
    st.dataframe(prediction["outras"], hide_index=True, use_container_width=False)
    st.subheader("3. Previsão só com partidas anteriores no tempo")
    st.dataframe(prediction["anteriores"], hide_index=True, use_container_width=False)
    st.subheader("4. Ranking por campeonato: perfil combinado contra taxa de vitória")
    st.caption("Times com 3 ou mais partidas. Perfil é a soma padronizada das métricas com o sinal de cada uma. Spearman é a correlação de postos entre perfil e taxa de vitória.")
    for tournament_column, (tournament, table) in zip(st.columns(2) + st.columns(2), prediction["rankings"].items()):
        tournament_column.markdown(f"**{tournament}** (Spearman {table['spearman'].iloc[0]})")
        tournament_column.dataframe(table.drop(columns=["spearman"]), use_container_width=True)

with conclusions_tab:
    st.markdown((Path(__file__).parent / "CONCLUSOES.md").read_text(encoding="utf-8"))
