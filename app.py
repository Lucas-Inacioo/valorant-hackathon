"""Painel local para explorar as partidas do hackathon, organizado pelas decisões de macro game.

Uso: streamlit run app.py
"""
from datetime import datetime, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from agent_roles import ROLE_ORDER, death_cost_by_role, first_death_by_agent, first_death_by_role, first_death_by_role_and_trade, role_share, with_interval
from economy import after_previous_round, after_streak, build_rounds_table, close_match_ids, pistol_by_side, second_round_cycle, versus_full_buy, win_rate_by_loadout, win_rate_matrix
from explore_fields import DEFAULT_DATA_DIR, collect_field_stats, find_match_files, load_match, split_irrelevant_fields, summarize_fields
from maps import callout_name, load_maps_by_url, nearest_callout
from plants import build_plants_table, cells_for_map, situation_matrix, summary_by_plant_time, summary_by_site
from predict import forecast_accuracy, in_match_accuracy, load_matches, match_pairs, permutation_ceiling, team_features, tournament_ranking
from round_style import STYLE_ORDER, build_round_styles, collapse_regions, collapse_summary, style_by_score, style_summary, team_profiles
from setups import build_setups_table, defuse_by, retake_summary, watching_bands
from round_map import describe_event, draw_callout_summary, draw_points, draw_rate_markers, draw_round_map, round_events
from fights import build_fights_table, distance_matrix, distance_summary, economic_first_death, fight_class_summary, player_range_discipline, save_effect, team_summary, trade_possibility_summary
from first_blood import TIME_LABELS, first_blood_table, plant_summary, summary_by_map, wilson_interval, win_rate_by_time
from solo_deaths import SOLO_DISTANCE, build_deaths_table, context_summary, first_death_summary, summary_by_distance_band, summary_by_round_outcome, territory_summary, win_rate_by_situation, with_solo_flag

st.set_page_config(page_title="VALORANT Hackathon", layout="wide")

# Paleta fixa, validada para daltonismo com o validador do skill de dataviz
LOST_COLOR = "#ff7f0e"
WON_COLOR = "#1f77b4"
TRADE_COLOR = "#2ca02c"
ATTACK_COLOR = "#c0392b"
DEFENSE_COLOR = "#2a9d8f"
NEUTRAL_COLOR = "#7f7f7f"
SIDE_COLORS = {"ataque": ATTACK_COLOR, "defesa": DEFENSE_COLOR}
STYLE_COLORS = {"execução rápida": WON_COLOR, "default": TRADE_COLOR, "sem plant": LOST_COLOR}
ROUND_OUTCOME_LABELS = {False: "perdeu o round", True: "venceu o round"}
TRADE_POSSIBLE = "aliado em alcance olhando para o killer"


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
def matches_table():
    return load_matches()


@st.cache_data
def fights_table():
    return build_fights_table(deaths_table())


@st.cache_data
def round_styles_table():
    return build_round_styles(deaths_table(), rounds_table(), matches_table())


@st.cache_data
def setups_table():
    return build_setups_table()


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


def with_team_names(table, team_column, name_column="nome_time"):
    """Troca a cor do time (Blue, Red) pelo nome que vem do arquivo da partida."""
    name_by_match_team = {(row.match_id, color): getattr(row, f"nome_{color.lower()}") for row in matches_table().itertuples() for color in ["Blue", "Red"]}
    return table.assign(**{name_column: [name_by_match_team.get((match_id, team), team) for match_id, team in zip(table["match_id"], table[team_column])]})


def category_axis(column, order):
    return alt.Y(f"{column}:N", sort=order, title=None, axis=alt.Axis(labelOverlap=False, labelLimit=340))


def rate_chart(table, category_column, rate_column, count_column, x_title, color=WON_COLOR, group_column=None, group_colors=None, order=None, height=None):
    """Barras horizontais de uma taxa por categoria, intervalo de 95% (Wilson) como traço e a contagem ao lado. group_column separa as barras por cor."""
    data = with_interval(table.reset_index(), rate_column, count_column)
    data[category_column] = data[category_column].astype(str)
    order = [str(value) for value in order] if order else list(dict.fromkeys(data[category_column]))
    tooltip = [category_column, count_column, alt.Tooltip(f"{rate_column}:Q", format=".3f"), alt.Tooltip("ic95_baixo:Q", format=".3f"), alt.Tooltip("ic95_alto:Q", format=".3f")]
    base = alt.Chart(data).encode(y=category_axis(category_column, order), tooltip=tooltip + ([group_column] if group_column else []))
    if group_column:
        groups = list(group_colors)
        base = base.encode(yOffset=alt.YOffset(f"{group_column}:N", sort=groups), color=alt.Color(f"{group_column}:N", scale=alt.Scale(domain=groups, range=list(group_colors.values())), title=None))
        bars = base.mark_bar().encode(x=alt.X(f"{rate_column}:Q", title=x_title))
    else:
        bars = base.mark_bar(color=color).encode(x=alt.X(f"{rate_column}:Q", title=x_title))
    rules = base.mark_rule(strokeWidth=2).encode(x="ic95_baixo:Q", x2="ic95_alto:Q", color=alt.value("#4a4a4a"))
    counts = base.mark_text(align="left", dx=4, fontSize=10).encode(x="ic95_alto:Q", text=alt.Text(f"{count_column}:Q", format=","), color=alt.value("#6b6b6b"))
    rows = len(order) * (len(group_colors) if group_column else 1)
    return (bars + rules + counts).properties(height=height or max(120, 24 * rows + 40))


def dumbbell_chart(table, category_column, left_column, right_column, left_label, right_label, x_title, count_column=None, left_color=NEUTRAL_COLOR, right_color=WON_COLOR, order=None, x_domain=None):
    """Dois pontos ligados por categoria, para comparar um valor de referência (esquerda) com o observado (direita)."""
    data = table.reset_index()
    labels = data[category_column].astype(str)
    if count_column:
        labels = labels + " (" + data[count_column].astype(int).astype(str) + ")"
    data = data.assign(rotulo=labels)
    label_by_category = dict(zip(data[category_column].astype(str), data["rotulo"]))
    order = [label_by_category[str(value)] for value in order if str(value) in label_by_category] if order else list(data["rotulo"])
    long = data.melt(id_vars=["rotulo"], value_vars=[left_column, right_column], var_name="medida", value_name="valor").replace({"medida": {left_column: left_label, right_column: right_label}})
    scale = alt.Scale(domain=x_domain) if x_domain else alt.Undefined
    lines = alt.Chart(data).mark_rule(color="#b0b0b0", strokeWidth=2).encode(y=category_axis("rotulo", order), x=alt.X(f"{left_column}:Q", title=x_title, scale=scale), x2=f"{right_column}:Q")
    points = alt.Chart(long).mark_circle(size=110, opacity=1).encode(y=category_axis("rotulo", order), x=alt.X("valor:Q", title=x_title, scale=scale), color=alt.Color("medida:N", scale=alt.Scale(domain=[left_label, right_label], range=[left_color, right_color]), title=None), tooltip=["rotulo", "medida", alt.Tooltip("valor:Q", format=".3f")])
    return (lines + points).properties(height=max(120, 28 * len(data) + 40))


def heatmap_chart(rates, counts, x_title, y_title, color_title):
    """Taxa por célula com a contagem escrita, para cruzamentos como vivos de cada lado."""
    rate_long = rates.rename_axis(index="linha", columns="coluna").stack().rename("taxa").reset_index()
    count_long = counts.rename_axis(index="linha", columns="coluna").stack().rename("n").reset_index()
    long = rate_long.merge(count_long, on=["linha", "coluna"])
    long["rotulo"] = long["taxa"].map(lambda rate: f"{rate:.0%}") + " · " + long["n"].astype(int).astype(str)
    x = alt.X("coluna:O", title=x_title)
    y = alt.Y("linha:O", title=y_title, sort="descending")
    cells = alt.Chart(long).mark_rect().encode(x=x, y=y, color=alt.Color("taxa:Q", scale=alt.Scale(scheme="blues", domain=[0, 1]), title=color_title), tooltip=["linha", "coluna", alt.Tooltip("taxa:Q", format=".2f"), "n"])
    text = alt.Chart(long).mark_text(fontSize=11).encode(x=x, y=y, text="rotulo:N", color=alt.condition("datum.taxa > 0.55", alt.value("white"), alt.value("#222222")))
    return (cells + text).properties(height=260)


def difference_heatmap(by_situation, side, color_title):
    """Vitória com a condição menos sem ela, por aliados x inimigos vivos, para um lado. Cor divergente centrada em zero, contagem escrita."""
    data = by_situation[by_situation["lado"] == side].copy()
    data["aliados"] = data["situacao"].str.split("v").str[0].astype(int)
    data["inimigos"] = data["situacao"].str.split("v").str[1].astype(int)
    data["rotulo"] = data["diferenca"].map(lambda difference: f"{difference:+.2f}") + " · " + data["mortes"].astype(str)
    x = alt.X("inimigos:O", title="inimigos vivos")
    y = alt.Y("aliados:O", title="aliados vivos", sort="descending")
    cells = alt.Chart(data).mark_rect().encode(x=x, y=y, color=alt.Color("diferenca:Q", scale=alt.Scale(scheme="redblue", domain=[-0.4, 0.4]), title=color_title), tooltip=["situacao", "mortes", "sem", "com", "diferenca"])
    text = alt.Chart(data).mark_text(fontSize=11).encode(x=x, y=y, text="rotulo:N", color=alt.condition("abs(datum.diferenca) > 0.25", alt.value("white"), alt.value("#222222")))
    return (cells + text).properties(height=220)


def share_chart(shares, counts, part_colors, x_title):
    """Barras empilhadas a 100% por categoria, com a contagem no rótulo."""
    long = shares.rename_axis(index="categoria", columns="parte").stack().rename("fracao").reset_index()
    long["categoria"] = long["categoria"].astype(str)
    long["rotulo"] = long["categoria"] + " (" + long["categoria"].map(lambda category: int(counts.get(category, 0))).astype(str) + ")"
    parts = list(part_colors)
    long["parte_ordem"] = long["parte"].map(parts.index)
    return alt.Chart(long).mark_bar().encode(
        y=category_axis("rotulo", list(dict.fromkeys(long["rotulo"]))),
        x=alt.X("fracao:Q", stack="normalize", title=x_title, axis=alt.Axis(format="%")),
        color=alt.Color("parte:N", scale=alt.Scale(domain=parts, range=list(part_colors.values())), sort=parts, title=None),
        order=alt.Order("parte_ordem:Q"),
        tooltip=["rotulo", "parte", alt.Tooltip("fracao:Q", format=".0%")],
    ).properties(height=max(120, 32 * long["rotulo"].nunique() + 40))


def team_scatter(profiles, x_column, y_column, size_column, x_title, y_title):
    """Um ponto por time com o nome ao lado, tamanho pelo volume."""
    data = profiles.reset_index()
    x = alt.X(f"{x_column}:Q", title=x_title, axis=alt.Axis(format="%"))
    y = alt.Y(f"{y_column}:Q", title=y_title, axis=alt.Axis(format="%"), scale=alt.Scale(zero=False))
    points = alt.Chart(data).mark_circle(color=WON_COLOR, opacity=0.7).encode(x=x, y=y, size=alt.Size(f"{size_column}:Q", title="rounds de ataque"), tooltip=["time", size_column, alt.Tooltip(f"{x_column}:Q", format=".0%"), alt.Tooltip(f"{y_column}:Q", format=".0%")])
    labelled = data[data[size_column] >= data[size_column].quantile(0.5)]
    labels = alt.Chart(labelled).mark_text(align="left", dx=8, fontSize=10, color="#333333").encode(x=x, y=y, text="time:N")
    return (points + labels).properties(height=440)


def quantile_band_chart(per_round):
    """Mediana por round com bandas p25 a p75 e p10 a p90: a distribuição é assimétrica, então quantis dizem mais que o desvio padrão."""
    base = alt.Chart(per_round.reset_index()).encode(x=alt.X("round:O", title="round"))
    tooltip = ["round", "rounds", "p10", "p25", "mediana", "p75", "p90", "media", "desvio_padrao"]
    wide_band = base.mark_area(opacity=0.15, color=NEUTRAL_COLOR).encode(y=alt.Y("p10:Q", title="segundos"), y2="p90:Q", tooltip=tooltip)
    narrow_band = base.mark_area(opacity=0.3, color=NEUTRAL_COLOR).encode(y="p25:Q", y2="p75:Q", tooltip=tooltip)
    median_line = base.mark_line(color="#4a4a4a", point=True).encode(y="mediana:Q", tooltip=tooltip)
    return (wide_band + narrow_band + median_line).properties(height=320)


def opening_impact_chart(by_map):
    """Barra do impacto da abertura do ataque por mapa, com o intervalo de 95% como traço."""
    data = by_map.reset_index()
    data["rotulo"] = data["mapa"] + " (" + data["rounds"].astype(str) + ")"
    base = alt.Chart(data).encode(y=category_axis("rotulo", list(data["rotulo"])))
    tooltip = ["mapa", "rounds", "ataque_vence_se_abre", "ataque_vence_se_defesa_abre", "impacto_da_abertura", "impacto_ic95_baixo", "impacto_ic95_alto"]
    bars = base.mark_bar(color=ATTACK_COLOR).encode(x=alt.X("impacto_da_abertura:Q", title="diferença entre taxa de vitória quando ataque abre e quando defesa abre"), tooltip=tooltip)
    intervals = base.mark_rule(color="#4a4a4a", strokeWidth=2).encode(x="impacto_ic95_baixo:Q", x2="impacto_ic95_alto:Q", tooltip=tooltip)
    return (bars + intervals).properties(height=30 * len(data) + 40)


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


def map_selector(label, internal_names, key):
    """Seletor de mapa pelo nome legível, devolvendo o nome interno e o metadado."""
    names = list(dict.fromkeys(map_name_by_internal.get(internal, internal) for internal in internal_names))
    chosen_name = st.selectbox(label, names, key=key)
    internal = internal_by_name.get(chosen_name, chosen_name)
    return internal, maps_by_url().get(f"/Game/Maps/{internal}/{internal}")


matches, players, rounds = build_tables()

st.sidebar.title("Macro game")
all_tournaments = sorted(matches["torneio"].unique())
chosen_tournaments = st.sidebar.multiselect("Torneios", all_tournaments, default=all_tournaments)
st.sidebar.markdown("Cada aba responde uma pergunta de decisão de time. Mecânica individual (mira, score) fica fora, na aba Exploração.")
st.sidebar.markdown("Taxas vêm com intervalo de 95% (traço escuro) e o número de casos ao lado. Barras cujos traços se sobrepõem não são distinguíveis com estes dados.")
selected_matches = matches[matches["torneio"].isin(chosen_tournaments)]
selected_ids = set(selected_matches["match_id"])
selected_players = players[players["match_id"].isin(selected_ids)]
selected_rounds = rounds[rounds["match_id"].isin(selected_ids)]
map_name_by_internal = dict(zip(matches["mapa_interno"], matches["mapa"]))
internal_by_name = {name: internal for internal, name in map_name_by_internal.items()}

overview_tab, opening_tab, trades_tab, collapse_tab, economy_tab, plants_tab, match_tab, prediction_tab, conclusions_tab, explore_tab = st.tabs(["Visão geral", "Abertura", "Trocas e isolamento", "Colapso e estilo", "Economia", "Plant e defuse", "Partida", "Previsão", "Conclusões", "Exploração"])

with overview_tab:
    matches_col, rounds_col, players_col = st.columns(3)
    matches_col.metric("Partidas", len(selected_matches))
    rounds_col.metric("Rounds", len(selected_rounds))
    players_col.metric("Jogadores distintos", selected_players["puuid"].nunique())
    st.markdown("""
**O que cada aba responde**

- **Abertura.** Quando e onde a primeira morte acontece, quanto ela pesa por lado, por mapa e por função do agente que morreu.
- **Trocas e isolamento.** O que a troca vale, quando ela era possível e não saiu, e o que a distância ao aliado muda.
- **Colapso e estilo.** Rounds que acabam em 10 segundos, ritmo do ataque (execução rápida ou default) e se o time muda quando está atrás.
- **Economia.** Quanto o loadout compra de round, o round seguinte, pistol e round 2, e o que o save rende.
- **Plant e defuse.** Onde a spike é plantada, quanto cada posição é defusada e o que o setup do pós-plant muda.
- **Partida.** Replay de um round sobre o minimapa.
- **Previsão.** Se as métricas explicam e preveem partidas sem usar o resultado.
""")
    maps_column, results_column = st.columns(2)
    maps_column.markdown("**Partidas por mapa**")
    maps_column.bar_chart(selected_matches["mapa"].value_counts(), horizontal=True, color=[NEUTRAL_COLOR], x_label="partidas", y_label="")
    results_column.markdown("**Como os rounds terminam**")
    results_column.bar_chart(selected_rounds["resultado"].value_counts(), horizontal=True, color=[NEUTRAL_COLOR], x_label="rounds", y_label="")
    with st.expander("Lista de partidas"):
        st.dataframe(selected_matches.drop(columns=["match_id", "caminho", "mapa_interno", "mapa_do_arquivo"]), hide_index=True)

with opening_tab:
    st.markdown("Uma linha por round: quando aconteceu a primeira morte, qual lado abriu o placar e se o time que abriu venceu o round. O tempo conta a partir do round live, sem a fase de compra.")
    first_blood = first_blood_rows()[first_blood_rows()["match_id"].isin(selected_ids)]
    rounds_col, median_col, opener_col = st.columns(3)
    rounds_col.metric("Rounds com morte", len(first_blood))
    median_col.metric("Mediana da primeira morte", f'{first_blood["segundos"].median():.1f} s')
    opener_col.metric("Quem abre vence o round", f'{first_blood["abriu_venceu"].mean():.1%}')

    st.subheader("1. Quem abre vence, e isso muda com o momento?")
    rate_column, count_column = st.columns([3, 2])
    rate_column.altair_chart(rate_chart(win_rate_by_time(first_blood), "faixa", "abriu_venceu", "rounds", "vitória do round de quem abriu", group_column="lado_abriu", group_colors=SIDE_COLORS, order=TIME_LABELS), use_container_width=True)
    count_column.markdown("**Quando a primeira morte acontece, por lado de quem abriu**")
    count_column.bar_chart(pd.crosstab(first_blood["faixa"], first_blood["lado_abriu"]), color=[ATTACK_COLOR, DEFENSE_COLOR], stack=False, y_label="rounds", x_label="")
    with st.expander("Antes ou depois do plant"):
        st.dataframe(plant_summary(first_blood).rename(index={True: "antes do plant", False: "depois do plant"}, level="antes_do_plant"), use_container_width=False)

    st.subheader("2. Por mapa: onde a abertura do ataque mais pesa")
    st.caption("Impacto da abertura é a vitória do ataque quando ele abre menos a vitória do ataque quando a defesa abre. Ordenado por rounds, com o número no rótulo.")
    by_map = summary_by_map(first_blood).rename(index=map_name_by_internal)
    impact_column, table_column = st.columns([3, 2])
    impact_column.altair_chart(opening_impact_chart(by_map), use_container_width=True)
    table_column.dataframe(by_map[["rounds", "ataque_abriu", "ataque_vence", "ataque_vence_se_abre", "ataque_vence_se_defesa_abre"]], use_container_width=True)

    st.subheader("3. Onde o ataque abre o placar")
    chosen_internal, chosen_map_meta = map_selector("Mapa", by_map.index.map(internal_by_name), "opening_map")
    attack_openings = first_blood[(first_blood["mapa"] == chosen_internal) & (first_blood["lado_abriu"] == "ataque") & first_blood["antes_do_plant"]]
    if chosen_map_meta is None or attack_openings.empty:
        st.info("Sem metadado de mapa ou sem aberturas neste recorte.")
    else:
        by_callout = openings_by_callout(attack_openings, chosen_map_meta)
        map_average = attack_openings["abriu_venceu"].mean()
        st.caption(f"Só aberturas antes do plant, atribuídas à região (callout) mais próxima de onde o defensor morreu. Tamanho: aberturas. Cor: vitória do ataque ao abrir ali, centrada na média do mapa ({map_average:.0%}). Azul: abrir ali quase decide. Laranja: mesmo abrindo ali o round fica em aberto.")
        map_column, table_column = st.columns([3, 2])
        if st.checkbox("Mostrar cada kill em vez das regiões"):
            won = attack_openings[attack_openings["abriu_venceu"]]
            lost = attack_openings[~attack_openings["abriu_venceu"]]
            map_column.pyplot(draw_points(chosen_map_meta, [
                ("ataque venceu o round", WON_COLOR, list(zip(won["vitima_x"], won["vitima_y"]))),
                ("ataque perdeu o round", LOST_COLOR, list(zip(lost["vitima_x"], lost["vitima_y"]))),
            ]))
        else:
            map_column.pyplot(draw_callout_summary(chosen_map_meta, by_callout, map_average))
        table_column.dataframe(by_callout[["aberturas", "ataque_venceu", "ic95"]], use_container_width=True)

    st.subheader("4. Quem morre primeiro e quanto custa, por função do agente")
    st.caption("Função vem da lista pública de agentes, só para dar nome ao characterId. Acima do time é a vitória do round menos a taxa de rounds que o time da vítima venceu na partida, o que desconta a força dos dois times.")
    max_seconds = st.slider("Só primeiras mortes até este tempo do round (s)", 10, 150, 150, step=10, key="role_max_seconds")
    role_deaths = deaths_table()[deaths_table()["match_id"].isin(selected_ids)]
    role_first = first_death_by_role(role_deaths, max_seconds)
    share_column, cost_column = st.columns(2)
    share_column.markdown("**Quem morre primeiro.** Fração de cada função entre os escalados e entre as vítimas da primeira morte.")
    share_column.bar_chart(role_share(role_deaths, max_seconds), color=[NEUTRAL_COLOR, ATTACK_COLOR, DEFENSE_COLOR], stack=False, y_label="fração", x_label="")
    cost_column.markdown("**Quanto custa.** Vitória do time que perdeu o primeiro jogador, pela função dele.")
    cost_column.altair_chart(rate_chart(role_first, "funcao", "vitoria_da_vitima", "rounds", "vitória do time da vítima", group_column="lado", group_colors=SIDE_COLORS, order=ROLE_ORDER), use_container_width=True)
    with st.expander("Tabelas por função, por troca e por agente"):
        st.dataframe(role_first, use_container_width=False)
        st.markdown("**Trocada ou não.** A função importa quando ninguém troca?")
        st.dataframe(first_death_by_role_and_trade(role_deaths, max_seconds), use_container_width=False)
        st.markdown("**Por agente**, 30 ou mais primeiras mortes. Diferenças entre agentes misturam o agente com quem costuma escolhê-lo.")
        st.dataframe(first_death_by_agent(role_deaths, max_seconds), use_container_width=False)

    st.subheader("5. Ao longo da partida: o tempo da primeira morte por round")
    per_round = first_blood[first_blood["round"] <= 24].groupby("round")["segundos"].agg(
        rounds="size", p10=lambda seconds: seconds.quantile(0.10), p25=lambda seconds: seconds.quantile(0.25), mediana="median",
        p75=lambda seconds: seconds.quantile(0.75), p90=lambda seconds: seconds.quantile(0.90), media="mean", desvio_padrao="std",
    ).round(1)
    st.caption("Linha: mediana. Banda escura: p25 a p75. Banda clara: p10 a p90. A distribuição é assimétrica à direita, por isso quantis em vez de média e desvio padrão.")
    band_column, count_column = st.columns([3, 2])
    band_column.altair_chart(quantile_band_chart(per_round), use_container_width=True)
    count_column.bar_chart(per_round["rounds"], color=[NEUTRAL_COLOR], y_label="rounds na base", x_label="round")
    with st.expander("Números por round"):
        st.dataframe(per_round, use_container_width=False)

with trades_tab:
    st.markdown("Para cada morte, a distância da vítima ao aliado vivo mais próximo, se a morte foi trocada (o killer morre em até 5 s) e se a troca era possível (um aliado a até 20 m do killer com o olhar a até 45 graus dele). A cadeia que a base mostra: isolamento tira a troca, e a troca é o que decide o round.")
    control_column, phase_column = st.columns(2)
    solo_distance = control_column.slider("Limite de isolamento (unidades de jogo, cerca de 100 por metro)", 500, 3000, SOLO_DISTANCE, step=250)
    phase = phase_column.radio("Fase do round", ["todas", "pré-plant", "pós-plant"], horizontal=True, help="Depois do plant a lógica de rotação inverte, a defesa precisa retomar o site.")
    selected_deaths = deaths_table()[deaths_table()["match_id"].isin(selected_ids)]
    fights = fights_table()[fights_table()["match_id"].isin(selected_ids)]
    if phase != "todas":
        selected_deaths = selected_deaths[selected_deaths["fase"] == phase]
        fights = fights[fights["fase"] == phase]
    deaths_with_allies = with_solo_flag(selected_deaths, solo_distance)
    deaths_with_allies["aliado_perto"] = ~deaths_with_allies["isolada"]
    possible = fights[fights["troca_possivel"] == TRADE_POSSIBLE]
    deaths_col, traded_col, isolated_col, missed_col = st.columns(4)
    deaths_col.metric("Mortes", len(selected_deaths))
    traded_col.metric("Trocadas", f"{selected_deaths['trocada'].mean():.0%}")
    isolated_col.metric("Isoladas (com aliado vivo)", f"{deaths_with_allies['isolada'].mean():.0%}")
    missed_col.metric("Troca possível e não feita", f"{1 - possible['trocada'].mean():.0%}")

    st.subheader("1. O que a troca e o aliado perto valem, com os vivos descontados")
    st.caption("Cada célula é uma situação (aliados x inimigos vivos na hora da morte) com 60 mortes ou mais. O número é a vitória do round com a condição menos sem ela, e ao lado o total de mortes da célula. Comparar dentro da mesma situação separa o efeito da condição do efeito de estar em vantagem numérica. Azul: a condição ajuda. Vermelho: atrapalha.")
    for flag, label in [("trocada", "Morte trocada"), ("aliado_perto", "Aliado perto (não isolada)")]:
        by_situation = win_rate_by_situation(deaths_with_allies, flag)
        weighted = (by_situation["diferenca"] * by_situation["mortes"]).groupby(by_situation["lado"]).sum() / by_situation.groupby("lado")["mortes"].sum()
        st.markdown(f"**{label}.** Efeito médio ponderado pelas mortes: ataque {weighted.get('ataque', float('nan')):+.2f}, defesa {weighted.get('defesa', float('nan')):+.2f}.")
        attack_column, defense_column = st.columns(2)
        attack_column.altair_chart(difference_heatmap(by_situation, "ataque", "com menos sem"), use_container_width=True)
        defense_column.altair_chart(difference_heatmap(by_situation, "defesa", "com menos sem"), use_container_width=True)
        with st.expander(f"Tabela por situação: {label.lower()}"):
            st.dataframe(by_situation, hide_index=True, use_container_width=False)

    st.subheader("2. A troca era possível?")
    trade_table = trade_possibility_summary(fights, ["lado"]).rename(index={TRADE_POSSIBLE: "aliado em alcance, olhando para o killer", "aliado em alcance olhando para outro lado": "aliado em alcance, olhando para outro lado"}, level="troca_possivel")
    traded_column, won_column = st.columns(2)
    traded_column.markdown("**Fração trocada em cada condição**")
    traded_column.altair_chart(rate_chart(trade_table, "troca_possivel", "trocada", "mortes", "fração trocada", group_column="lado", group_colors=SIDE_COLORS), use_container_width=True)
    won_column.markdown("**Vitória do round do time da vítima em cada condição**")
    won_column.altair_chart(rate_chart(trade_table, "troca_possivel", "venceu_round", "mortes", "vitória do round", group_column="lado", group_colors=SIDE_COLORS), use_container_width=True)

    st.subheader("3. A distância ao aliado mais próximo")
    st.caption("Por faixa de distância da vítima ao aliado vivo mais próximo: quantas mortes foram trocadas e quantas o time ainda venceu.")
    for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
        side_deaths = deaths_with_allies[deaths_with_allies["lado"] == side]
        side_column.markdown(f"**Vítima no {side}**")
        side_column.bar_chart(summary_by_distance_band(side_deaths)[["fracao_trocadas", "venceu_round"]].rename(columns={"fracao_trocadas": "trocada", "venceu_round": "venceu o round"}), color=[TRADE_COLOR, WON_COLOR], stack=False, y_label="fração", x_label="distância ao aliado mais próximo (unidades)")
    with st.expander("Resumo por lado e resultado do round, e a primeira morte isolada ou trocada"):
        st.dataframe(summary_by_round_outcome(deaths_with_allies, ["lado"]).rename(index=ROUND_OUTCOME_LABELS, level="venceu_round"), use_container_width=False)
        for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
            first_deaths = first_death_summary(deaths_with_allies[deaths_with_allies["lado"] == side]).reset_index()
            first_deaths["isolada"] = first_deaths["isolada"].map({False: "acompanhada", True: "isolada"})
            first_deaths["trocada"] = first_deaths["trocada"].map({False: "não trocada", True: "trocada"})
            side_column.markdown(f"**Primeira morte do round, vítima no {side}**")
            side_column.dataframe(first_deaths, hide_index=True, use_container_width=False)

    st.subheader("4. Onde estavam os aliados e em que território a morte aconteceu")
    st.caption("Contexto pela posição dos aliados vivos. Em grupo: algum aliado dentro do limite. Flanco: nenhum perto e todos na mesma área do mapa. Isolado: nenhum perto e aliados espalhados. Território pela fração do próprio lado entre as posições vivas da região nos primeiros 20 s dos rounds (próprio a partir de 65%, do adversário até 35%).")
    context_column, territory_column = st.columns(2)
    context_column.markdown("**Vitória do round pelo contexto da morte**")
    context_column.altair_chart(rate_chart(context_summary(deaths_with_allies, ["lado"]), "contexto", "venceu_round", "mortes", "vitória do round", group_column="lado", group_colors=SIDE_COLORS, order=["em grupo", "flanco", "isolado", "último vivo"]), use_container_width=True)
    territory_column.markdown("**Vitória do round pelo território**")
    territory_column.altair_chart(rate_chart(territory_summary(deaths_with_allies[deaths_with_allies["territorio"] != "?"], ["lado"]), "territorio", "venceu_round", "mortes", "vitória do round", group_column="lado", group_colors=SIDE_COLORS, order=["próprio", "disputado", "do adversário"]), use_container_width=True)
    with st.expander("Tabelas de contexto e território, e o isolamento por função do agente"):
        st.dataframe(context_summary(deaths_with_allies, ["lado"]), use_container_width=False)
        st.dataframe(territory_summary(deaths_with_allies, ["lado"]), use_container_width=False)
        st.markdown("**Por função do agente.** Acima do esperado desconta a situação de vivos. Custo do isolamento é a diferença entre morrer isolado e acompanhado, com o mesmo desconto.")
        st.dataframe(death_cost_by_role(deaths_with_allies), use_container_width=False)

    st.subheader("5. Por time: trocas possíveis convertidas")
    st.caption("Só times com 150 ou mais mortes com posição do killer. Troca possível é a fração das mortes do time em que um aliado estava em condição de trocar. Convertida é quanto dessas foi trocada. Sem reação é a fração das mortes em que a vítima não feriu o killer. Kills em foco é a fração das kills do time com dois ou mais atirando.")
    named_fights = fights.assign(time_killer=fights["time_vitima"].map({"Blue": "Red", "Red": "Blue"}))
    named_fights = with_team_names(with_team_names(named_fights, "time_vitima"), "time_killer", "nome_killer")
    st.dataframe(team_summary(named_fights), use_container_width=False)

with collapse_tab:
    st.markdown("Uma linha por round e time. Colapso: três mortes do time em 10 s sem nenhuma kill do time na janela. Estilo do ataque pelo tempo do plant: execução rápida até 40 s, default depois, sem plant quando o round acabou antes (quase sempre derrota, é mais resultado que estilo). Contato cedo: primeira morte do round até 20 s. Placar é o estado antes do round.")
    styles = round_styles_table()
    styles = styles[styles["match_id"].isin(selected_ids) & (styles["lado"] != "?")]
    rounds_col, collapse_col, fast_col = st.columns(3)
    rounds_col.metric("Rounds por time", len(styles))
    collapse_col.metric("Rounds com colapso", f"{styles['colapso'].mean():.0%}")
    fast_col.metric("Ataques com execução rápida", f"{(styles.loc[styles['lado'] == 'ataque', 'estilo'] == 'execução rápida').mean():.0%}")

    st.subheader("1. Colapso: quanto acontece e o que custa")
    by_side = collapse_summary(styles, ["lado"])
    side_column, map_column = st.columns([2, 3])
    side_column.markdown("**Fração dos rounds com colapso, por lado**")
    side_column.altair_chart(rate_chart(by_side, "lado", "colapsos", "rounds", "fração dos rounds", group_column="lado", group_colors=SIDE_COLORS, height=140), use_container_width=True)
    side_column.markdown("**Vitória do round sem e com colapso**")
    side_column.altair_chart(dumbbell_chart(by_side, "lado", "venceu_com_colapso", "venceu_sem_colapso", "com colapso", "sem colapso", "vitória do round", count_column="rounds", left_color=LOST_COLOR), use_container_width=True)
    map_column.markdown("**Por mapa e lado**")
    by_map_side = collapse_summary(styles, ["mapa", "lado"]).rename(index=map_name_by_internal, level="mapa").sort_values("rounds", ascending=False)
    map_column.altair_chart(rate_chart(by_map_side, "mapa", "colapsos", "rounds", "fração dos rounds com colapso", group_column="lado", group_colors=SIDE_COLORS), use_container_width=True)
    collapse_internal, _ = map_selector("Regiões de colapso no mapa", styles["mapa"].value_counts().index, "collapse_map")
    st.dataframe(collapse_regions(styles, collapse_internal), use_container_width=False)

    st.subheader("2. Estilo do ataque e contato")
    attack_styles, contact = style_summary(styles)
    style_column, contact_column = st.columns(2)
    style_column.markdown("**Vitória do ataque por estilo**")
    style_column.altair_chart(rate_chart(attack_styles, "estilo", "venceu", "rounds", "vitória do round", order=STYLE_ORDER, height=140), use_container_width=True)
    contact_column.markdown("**Vitória por contato cedo ou tarde, por lado**")
    contact_column.altair_chart(rate_chart(contact, "contato", "venceu", "rounds", "vitória do round", group_column="lado", group_colors=SIDE_COLORS, height=140), use_container_width=True)

    st.subheader("3. O estilo muda com o placar?")
    shares, wins, counts = style_by_score(styles)
    shares_column, wins_column = st.columns(2)
    shares_column.markdown("**Fração de cada estilo conforme o placar antes do round**")
    shares_column.altair_chart(share_chart(shares, counts, STYLE_COLORS, "fração dos rounds de ataque"), use_container_width=True)
    wins_column.markdown("**Vitória de cada combinação**")
    wins_column.dataframe(wins, use_container_width=False)

    st.subheader("4. Perfil por time, 40 ou mais rounds de ataque")
    profiles = team_profiles(styles)
    st.caption("Só a metade dos times com mais rounds de ataque tem o nome escrito. Os outros aparecem no tooltip.")
    st.altair_chart(team_scatter(profiles, "execução rápida", "vitoria_ataque", "rounds_ataque", "fração de execuções rápidas no ataque", "vitória no ataque"), use_container_width=True)
    with st.expander("Tabela completa por time"):
        st.dataframe(profiles, use_container_width=True)

with economy_tab:
    st.markdown("Por round e por time: soma do loadout dos cinco jogadores, resultado e cerimônia. Rounds normais excluem pistol (1 e 13) e o segundo round (2 e 14). Vitória esperada pelo dinheiro é a taxa de vitória da faixa de diferença de loadout; o que sobra acima dela é o que não é dinheiro.")
    economy_rounds = rounds_table()[rounds_table()["match_id"].isin(selected_ids)]
    close_rounds = economy_rounds[economy_rounds["match_id"].isin(close_match_ids(economy_rounds))]
    fights = fights_table()[fights_table()["match_id"].isin(selected_ids)]

    st.subheader("1. Quanto o loadout compra de vitória")
    own_table, difference_table = win_rate_by_loadout(economy_rounds)
    difference_column, full_buy_column = st.columns(2)
    difference_column.markdown("**Pela diferença de loadout para o adversário**, todos os rounds")
    difference_column.altair_chart(rate_chart(difference_table, "faixa_diferenca", "vitoria", "rounds", "vitória do round"), use_container_width=True)
    full_buy_column.markdown("**Contra compra cheia (20k+)**, rounds normais")
    full_buy_column.altair_chart(rate_chart(versus_full_buy(economy_rounds), "faixa_loadout", "vitoria", "rounds", "vitória do round"), use_container_width=True)
    with st.expander("Tabelas: ganho por 1k, faixa própria e a matriz loadout x loadout do adversário"):
        st.dataframe(versus_full_buy(economy_rounds), use_container_width=False)
        st.dataframe(own_table, use_container_width=False)
        rates, counts = win_rate_matrix(economy_rounds)
        st.altair_chart(heatmap_chart(rates, counts, "loadout do adversário", "loadout do time", "vitória do round"), use_container_width=True)

    st.subheader("2. O round seguinte: perder abala?")
    st.caption("Round fácil perdido é derrota num round em que o adversário fez clutch ou thrifty. Ponto cinza: vitória esperada pelo dinheiro do round seguinte. Ponto azul: vitória real. Quando os dois pontos se sobrepõem, o round anterior não acrescenta nada além do dinheiro que deixou.")
    all_column, close_column = st.columns(2)
    all_column.markdown("**Todas as partidas**")
    previous_labels = {"perdeu round fácil (clutch ou thrifty do adversário)": "perdeu round fácil"}
    all_column.altair_chart(dumbbell_chart(after_previous_round(economy_rounds).rename(index=previous_labels), "anterior", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "vitória real", "vitória do round seguinte", count_column="rounds", x_domain=[0.2, 0.7]), use_container_width=True)
    close_column.markdown(f"**Só partidas equilibradas** (até 4 rounds de diferença no placar final, {close_rounds['match_id'].nunique()} partidas)")
    close_column.altair_chart(dumbbell_chart(after_previous_round(close_rounds).rename(index=previous_labels), "anterior", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "vitória real", "vitória do round seguinte", count_column="rounds", x_domain=[0.2, 0.7]), use_container_width=True)
    streak_all_column, streak_close_column = st.columns(2)
    streak_all_column.markdown("**Derrotas seguidas antes do round**, todas as partidas")
    streak_all_column.altair_chart(dumbbell_chart(after_streak(economy_rounds), "derrotas", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "vitória real", "vitória do round", count_column="rounds", x_domain=[0.2, 0.7]), use_container_width=True)
    streak_close_column.markdown("**Derrotas seguidas**, só partidas equilibradas")
    streak_close_column.altair_chart(dumbbell_chart(after_streak(close_rounds), "derrotas", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "vitória real", "vitória do round", count_column="rounds", x_domain=[0.2, 0.7]), use_container_width=True)

    st.subheader("3. Pistol e round 2: eco ou force?")
    pistol_column, cycle_column = st.columns([1, 3])
    pistol_column.markdown("**Pistol por lado**")
    pistol_column.dataframe(pistol_by_side(economy_rounds), use_container_width=False)
    overall_cycle, cycle_by_side = second_round_cycle(economy_rounds)
    cycle_column.markdown("**Perdedor do pistol: compra no round 2 e o que vem depois.** Força do time é a vitória de rounds do round 5 em diante, para ver quem escolhe cada compra.")
    cycle_column.bar_chart(overall_cycle[["vitoria_round_2", "vitoria_round_3", "vitoria_round_4"]].rename(columns={"vitoria_round_2": "round 2", "vitoria_round_3": "round 3", "vitoria_round_4": "round 4"}), color=[WON_COLOR, TRADE_COLOR, NEUTRAL_COLOR], stack=False, y_label="vitória", x_label="compra do perdedor do pistol no round 2")
    with st.expander("Tabelas do ciclo, no total e por lado"):
        st.dataframe(overall_cycle, use_container_width=True)
        st.dataframe(cycle_by_side, use_container_width=True)

    st.subheader("4. O peso econômico da morte e o save")
    expensive_column, operator_column = st.columns(2)
    expensive_column.markdown("**Primeira morte do jogador mais caro do time** (loadout maior que o de todos os colegas). Acima do time desconta a taxa de rounds do time na partida.")
    expensive_column.dataframe(economic_first_death(fights, "mais_caro_do_time"), use_container_width=False)
    operator_column.markdown("**Primeira morte de quem comprou Operator**")
    operator_column.dataframe(economic_first_death(fights.assign(operator=fights["arma_vitima"] == "Operator"), "operator"), use_container_width=False)
    saves = save_effect(economy_rounds, fights).loc[0:4]
    saves = saves[saves["rounds"] >= 20]
    save_loadout_column, save_win_column = st.columns(2)
    save_loadout_column.markdown("**Save: loadout do round seguinte por sobreviventes de um round perdido** (fora dos rounds 12 e 24)")
    save_loadout_column.bar_chart(saves["loadout_seguinte"], color=[WON_COLOR], y_label="loadout do round seguinte", x_label="sobreviventes")
    save_win_column.markdown("**Vitória do round seguinte por sobreviventes**")
    save_win_column.altair_chart(rate_chart(saves, "sobreviventes", "venceu_seguinte", "rounds", "vitória do round seguinte", height=170), use_container_width=True)

with plants_tab:
    st.markdown("Uma linha por round plantado: onde a spike foi plantada, quantos de cada lado estavam vivos no plant e se foi defusada. Esperado pelos vivos é a taxa de defuse da mesma situação (ataque x defesa vivos no plant). Ponto cinza: esperado. Ponto azul: observado. A diferença é o que a posição, o tempo ou o setup acrescentam.")
    selected_plants = plants_table()[plants_table()["match_id"].isin(selected_ids)]
    plants_col, defuse_col, time_col = st.columns(3)
    plants_col.metric("Rounds plantados", len(selected_plants))
    defuse_col.metric("Defusados", f'{selected_plants["defusada"].mean():.1%}')
    time_col.metric("Tempo mediano do plant", f'{selected_plants["segundos_plant"].median():.0f} s')

    st.subheader("1. Quem está vivo no plant decide")
    rates, counts = situation_matrix(selected_plants)
    st.altair_chart(heatmap_chart(rates, counts, "defesa vivos no plant", "ataque vivos no plant", "taxa de defuse"), use_container_width=True)

    st.subheader("2. Tempo do plant e site, contra o esperado pelos vivos")
    time_column, site_column = st.columns(2)
    time_column.markdown("**Por tempo do plant**")
    by_time = summary_by_plant_time(selected_plants)
    time_column.altair_chart(dumbbell_chart(by_time[by_time["plants"] >= 20], "faixa_tempo", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "defuse observado", "taxa de defuse", count_column="plants", x_domain=[0, 0.6]), use_container_width=True)
    by_site = summary_by_site(selected_plants).rename(index=map_name_by_internal, level="mapa")
    by_site_named = by_site[by_site["plants"] >= 100].reset_index()
    by_site_named["mapa_site"] = by_site_named["mapa"] + " " + by_site_named["site"]
    site_column.markdown("**Por mapa e site**, 100 ou mais plants")
    site_column.altair_chart(dumbbell_chart(by_site_named.set_index("mapa_site"), "mapa_site", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "defuse observado", "taxa de defuse", count_column="plants", x_domain=[0, 0.6]), use_container_width=True)
    with st.expander("Tabela por mapa e site"):
        st.dataframe(by_site, use_container_width=False)

    st.subheader("3. Onde a spike é plantada e quanto cada posição é defusada")
    plant_map_internal, plant_map_meta = map_selector("Mapa", selected_plants["mapa"].value_counts().index, "plant_map")
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
        with st.expander("Células do mapa"):
            st.dataframe(cells[["site", "plants", "defuse", "esperado_pelos_vivos", "acima_do_esperado"]], use_container_width=False)

    st.subheader("4. Setup no plant e retake")
    st.caption("Posições e olhar no momento do plant. Atacantes no site: a até 15 m da spike. Olhando para fora: fração dos aliados do planter com o olhar a mais de 90 graus da spike, ou seja, vigiando entradas. Distância da defesa: mediana dos defensores vivos até a spike. Tudo contra o esperado pelos vivos.")
    selected_setups = setups_table()[setups_table()["match_id"].isin(selected_ids)]
    on_site_column, watching_column, defense_column = st.columns(3)
    on_site_column.markdown("**Atacantes a até 15 m da spike**")
    on_site_column.altair_chart(dumbbell_chart(defuse_by(selected_setups, "atacantes_no_site"), "atacantes_no_site", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "defuse observado", "taxa de defuse", count_column="plants", x_domain=[0, 0.6]), use_container_width=True)
    watching_column.markdown("**Aliados do planter olhando para fora**")
    watching_column.altair_chart(dumbbell_chart(defuse_by(selected_setups, watching_bands(selected_setups)), "olhando_para_fora", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "defuse observado", "taxa de defuse", count_column="plants", x_domain=[0, 0.6]), use_container_width=True)
    defense_column.markdown("**Distância mediana da defesa no plant**")
    defense_column.altair_chart(dumbbell_chart(defuse_by(selected_setups, "faixa_defesa"), "faixa_defesa", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "defuse observado", "taxa de defuse", count_column="plants", x_domain=[0, 0.6]), use_container_width=True)
    st.markdown("**Retake: atacantes vivos quando a spike foi defusada e distância do mais próximo**")
    st.dataframe(retake_summary(selected_setups), use_container_width=False)

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

    with st.expander("Jogadores, rounds e matchInfo bruto"):
        match_players = players[players["match_id"] == chosen_match["match_id"]].drop(columns=["match_id", "puuid"])
        st.dataframe(match_players.sort_values(["time", "score"], ascending=[True, False]), hide_index=True)
        st.dataframe(rounds[rounds["match_id"] == chosen_match["match_id"]].drop(columns=["match_id"]), hide_index=True)
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

with explore_tab:
    st.markdown("Fora do macro game, mantido como exploração: a arma e a distância de cada morte, a reação da vítima, estatísticas individuais de combate e o dicionário de campos dos JSONs.")
    fights = fights_table()[fights_table()["match_id"].isin(selected_ids)]
    st.subheader("Disciplina de distância: a arma da vítima e a distância do killer")
    summary_column, matrix_column = st.columns(2)
    summary_column.dataframe(distance_summary(fights), use_container_width=False)
    matrix_column.dataframe(distance_matrix(fights), use_container_width=False)
    name_by_puuid = players.drop_duplicates("puuid").set_index("puuid")["jogador"]
    short_table, sniper_table = player_range_discipline(fights, name_by_puuid)
    short_column, sniper_column = st.columns(2)
    short_column.markdown("**Por jogador: mortes com SMG ou shotgun em duelo longo (25 m+)**, 10 ou mais mortes")
    short_column.dataframe(short_table, hide_index=True, use_container_width=False)
    sniper_column.markdown("**Por jogador: mortes com sniper em duelo curto (até 10 m)**, 10 ou mais mortes")
    sniper_column.dataframe(sniper_table, hide_index=True, use_container_width=False)

    st.subheader("Luta ou execução: a vítima reagiu?")
    st.caption("Duelo quando a vítima feriu o killer no round, foco quando dois ou mais inimigos feriram a vítima, sem reação no resto.")
    st.dataframe(fight_class_summary(fights, ["lado"]), use_container_width=False)

    st.subheader("Jogadores: kills, mortes e score")
    st.dataframe(players_summary(selected_players), hide_index=True)

    st.subheader("Campos dos JSONs")
    relevant_fields, irrelevant_fields = build_field_tables()
    field_filter = st.text_input("Filtrar campo")
    st.dataframe(relevant_fields[relevant_fields["campo"].str.contains(field_filter, regex=False)], hide_index=True)
    with st.container(border=True):
        st.markdown("**Dados irrelevantes.** Campos com um único valor em toda a base e sem subcampos.")
        st.dataframe(irrelevant_fields.drop(columns=["distintos"]).rename(columns={"mais_frequentes": "valor"}), hide_index=True)
