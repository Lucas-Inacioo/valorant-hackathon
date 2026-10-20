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
SIDE_PHRASES = {"ataque": "no ataque", "defesa": "na defesa"}
STYLE_COLORS = {"execução rápida": WON_COLOR, "default": TRADE_COLOR, "sem plant": LOST_COLOR}
ROUND_OUTCOME_LABELS = {False: "perdeu o round", True: "venceu o round"}
TRADE_POSSIBLE = "aliado em alcance olhando para o killer"
# Só a largura segue o container, senão o Streamlit encolhe a área do gráfico para caber eixos e legenda na altura
FIT_WIDTH = alt.AutoSizeParams(type="fit-x", contains="padding")


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
        base = base.encode(yOffset=alt.YOffset(f"{group_column}:N", sort=groups), color=alt.Color(f"{group_column}:N", scale=alt.Scale(domain=groups, range=list(group_colors.values())), title=None, legend=alt.Legend(orient="bottom")))
        bars = base.mark_bar().encode(x=alt.X(f"{rate_column}:Q", title=x_title))
    else:
        bars = base.mark_bar(color=color).encode(x=alt.X(f"{rate_column}:Q", title=x_title))
    rules = base.mark_rule(strokeWidth=2).encode(x="ic95_baixo:Q", x2="ic95_alto:Q", color=alt.value("#4a4a4a"))
    # O nome do grupo vai escrito ao lado da contagem, para não depender só da cor
    data["rotulo_contagem"] = data[count_column].map(lambda count: f"{count:,}") if not group_column else data[group_column].astype(str) + " · " + data[count_column].map(lambda count: f"{count:,}")
    counts = base.mark_text(align="left", dx=4, fontSize=10).encode(x="ic95_alto:Q", text="rotulo_contagem:N", color=alt.value("#6b6b6b"))
    rows = len(order) * (len(group_colors) if group_column else 1)
    return (bars + rules + counts).properties(height=height or max(120, 24 * rows + 40), autosize=FIT_WIDTH)


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
    measures = alt.Scale(domain=[left_label, right_label], range=[left_color, right_color])
    shapes = alt.Scale(domain=[left_label, right_label], range=["square", "circle"])
    points = alt.Chart(long).mark_point(size=110, opacity=1, filled=True).encode(y=category_axis("rotulo", order), x=alt.X("valor:Q", title=x_title, scale=scale), color=alt.Color("medida:N", scale=measures, title=None), shape=alt.Shape("medida:N", scale=shapes, title=None), tooltip=["rotulo", "medida", alt.Tooltip("valor:Q", format=".3f")])
    return (lines + points).properties(height=max(120, 28 * len(data) + 40), autosize=FIT_WIDTH)


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
    long = long.sort_values(["rotulo", "parte_ordem"])
    long["fim"] = long.groupby("rotulo")["fracao"].cumsum()
    long["inicio"] = long["fim"] - long["fracao"]
    long["meio"] = (long["inicio"] + long["fim"]) / 2
    long["texto"] = long.apply(lambda row: f"{row['parte']} {row['fracao']:.0%}" if row["fracao"] >= 0.12 else "", axis=1)
    y = category_axis("rotulo", list(dict.fromkeys(long["rotulo"])))
    bars = alt.Chart(long).mark_bar().encode(
        y=y,
        x=alt.X("inicio:Q", title=x_title, axis=alt.Axis(format="%")),
        x2="fim:Q",
        color=alt.Color("parte:N", scale=alt.Scale(domain=parts, range=list(part_colors.values())), sort=parts, title=None),
        tooltip=["rotulo", "parte", alt.Tooltip("fracao:Q", format=".0%")],
    )
    text = alt.Chart(long).mark_text(fontSize=10, color="white").encode(y=y, x="meio:Q", text="texto:N")
    return (bars + text).properties(height=max(120, 32 * long["rotulo"].nunique() + 40), autosize=FIT_WIDTH)


def grouped_bar_chart(wide, series_colors, x_title, value_format=".0%", height=None):
    """Barras horizontais por categoria com uma barra por série. O nome da série vai escrito ao lado do valor, para não depender da cor."""
    long = wide.rename_axis(index="categoria", columns="serie").stack().rename("valor").reset_index()
    long["categoria"] = long["categoria"].astype(str)
    series = [column for column in wide.columns]
    long["texto"] = long["serie"].astype(str) + " · " + long["valor"].map(lambda value: format(value, value_format))
    y = category_axis("categoria", list(dict.fromkeys(long["categoria"])))
    y.title = wide.index.name
    base = alt.Chart(long).encode(y=y, yOffset=alt.YOffset("serie:N", sort=series), tooltip=["categoria", "serie", alt.Tooltip("valor:Q", format=value_format)])
    bars = base.mark_bar().encode(x=alt.X("valor:Q", title=x_title), color=alt.Color("serie:N", scale=alt.Scale(domain=series, range=list(series_colors)), title=None, legend=alt.Legend(orient="bottom")))
    labels = base.mark_text(align="left", dx=4, fontSize=10, color="#6b6b6b").encode(x=alt.X("valor:Q"), text="texto:N")
    return (bars + labels).properties(height=height or max(120, 22 * len(long) + 40), autosize=FIT_WIDTH)


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
    bars = base.mark_bar(color=ATTACK_COLOR).encode(x=alt.X("impacto_da_abertura:Q", title="% de vitória do ataque com o primeiro abate menos % de vitória do ataque sem ele"), tooltip=tooltip)
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
st.sidebar.markdown("Cada aba responde uma pergunta sobre decisões da equipe. Mira e pontuação individual ficam de fora, na aba Exploração.")
st.sidebar.markdown("Como ler os gráficos: o traço escuro em cada barra é a margem de erro (intervalo de 95%) e o número ao lado é quantos rounds ou mortes entraram na conta. Se os traços de duas barras se cruzam, a diferença entre elas pode ser só acaso.")
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

- **Abertura.** Quando e onde acontece o primeiro abate do round, quanto ele pesa para cada lado, em cada mapa e conforme a função do agente que morreu.
- **Trocas e isolamento.** Quanto vale vingar um aliado logo após a morte dele (a troca), quantas vezes a troca era possível e não saiu, e o que muda quando o jogador morre longe dos aliados.
- **Colapso e estilo.** Rounds em que três jogadores morrem em 10 segundos, ritmo do ataque (plantar rápido ou devagar) e se a equipe muda o ritmo quando está perdendo.
- **Economia.** Quanto o dinheiro gasto em armas compra de rounds, o que acontece no round seguinte a uma derrota, como comprar no round 2 e quanto vale sobreviver a um round perdido.
- **Plant e defuse.** Onde a spike é plantada, quantas vezes a defesa desarma em cada posição e se o posicionamento no momento do plant muda isso.
- **Partida.** Replay de um round sobre o minimapa.
- **Previsão.** Se as medidas das conclusões explicam e preveem partidas sem usar o resultado.

**Palavras usadas no painel**

- **Round.** Uma rodada da partida. A equipe que vence 13 rounds vence a partida.
- **Lado.** Ataque (precisa plantar a spike) ou defesa (precisa impedir ou desarmar). Os lados trocam na metade da partida.
- **Abate e morte.** O mesmo evento visto por quem matou (abate) e por quem morreu (morte).
- **Primeiro abate.** O primeiro abate do round. A equipe que o faz "abre o round".
- **Troca.** Quando o inimigo que matou alguém é morto por um aliado da vítima em até 5 segundos.
  - Troca possível: no instante da morte, algum aliado da vítima estava a menos de 20 metros do inimigo que a matou e olhando para ele.
- **Isolado.** Jogador que morre sem nenhum aliado vivo a menos de 10 metros (ajustável).
  - As posições nos arquivos vêm em unidades do jogo, não metros.
  - O estudo assume 100 unidades por metro, que é a escala padrão da engine do jogo (Unreal, em centímetros).
  - Então 10 metros são 1.000 unidades, e será apenas uma suposição para facilitar a leitura.
- **Colapso.** Três jogadores da mesma equipe morrem em até 10 segundos sem matar ninguém nesse intervalo.
- **Plant e defuse.** Plantar a spike (ataque) e desarmar a spike (defesa).
- **Loadout.** Valor total, em créditos, das armas e escudos dos cinco jogadores no início do round.
- **Esperado pelos vivos.** Uma comparação justa para o desarme da spike.
  - Quantos jogadores estão vivos de cada lado no momento do plant é o que mais decide se a defesa desarma. Com 2 atacantes contra 3 defensores, a defesa desarma 76% das vezes. Com 5 contra 5, 33%.
  - Por isso, antes de dizer que uma posição ou um horário de plant é bom, o painel responde quanto a defesa costuma desarmar com esse mesmo número de vivos. Esse é o esperado pelos vivos.
  - Se a posição desarma 40% e o esperado era 30%, a posição em si vale 10 pontos. Se desarma 40% e o esperado era 40%, a posição não muda nada, o que mudou foi quantos chegaram vivos.
- **Comparado com a equipe.** Uma comparação justa para o custo de uma morte.
  - Uma equipe forte vence muitos rounds mesmo perdendo o primeiro jogador. Uma equipe fraca perde muitos rounds mesmo sem perder ninguém. Olhar só a taxa de vitória depois da morte misturaria essas duas coisas.
  - Então o painel pega a taxa de vitória do round depois da morte e subtrai a taxa de rounds que aquela equipe venceu na partida inteira. O que sobra é quanto a morte custou além do normal daquela equipe.
  - Exemplo: a equipe venceu 50% dos rounds da partida, mas só 30% dos rounds em que o sentinela morreu primeiro. Comparado com a equipe, essa morte custou 20 pontos.
""")
    maps_column, results_column = st.columns(2)
    maps_column.markdown("**Partidas em cada mapa**")
    maps_column.bar_chart(selected_matches["mapa"].value_counts(), horizontal=True, color=[NEUTRAL_COLOR], x_label="partidas", y_label="")
    results_column.markdown("**Como os rounds terminam** (spike desarmada, spike explodiu, equipe eliminada, tempo esgotado)")
    results_column.bar_chart(selected_rounds["resultado"].value_counts(), horizontal=True, color=[NEUTRAL_COLOR], x_label="rounds", y_label="")
    with st.expander("Lista de partidas"):
        st.dataframe(selected_matches.drop(columns=["match_id", "caminho", "mapa_interno", "mapa_do_arquivo"]), hide_index=True)

with opening_tab:
    st.caption("O tempo conta a partir do início do round, depois da fase de compra.")
    first_blood = first_blood_rows()[first_blood_rows()["match_id"].isin(selected_ids)]
    rounds_col, median_col, opener_col = st.columns(3)
    rounds_col.metric("Rounds com pelo menos um abate", len(first_blood))
    median_col.metric("Segundo típico do primeiro abate (mediana)", f'{first_blood["segundos"].median():.1f} s')
    opener_col.metric("Quem consegue o primeiro abate vence o round", f'{first_blood["abriu_venceu"].mean():.1%}')

    st.subheader("1. Quem consegue o primeiro abate vence o round? Isso muda conforme o tempo em que ele acontece?")
    rate_column, count_column = st.columns([3, 2])
    rate_column.altair_chart(rate_chart(win_rate_by_time(first_blood), "faixa", "abriu_venceu", "rounds", "% de rounds vencidos pela equipe que conseguiu o primeiro abate", group_column="lado_abriu", group_colors=SIDE_COLORS, order=TIME_LABELS), use_container_width=True)
    count_column.markdown("**Em que segundo o primeiro abate acontece**, separado pelo lado que fez o abate")
    count_column.altair_chart(grouped_bar_chart(pd.crosstab(first_blood["faixa"], first_blood["lado_abriu"]).reindex(TIME_LABELS), [ATTACK_COLOR, DEFENSE_COLOR], "rounds", ","), use_container_width=True)
    with st.expander("Primeiro abate antes ou depois do plant"):
        st.dataframe(plant_summary(first_blood).rename(index={True: "antes do plant", False: "depois do plant"}, level="antes_do_plant"), use_container_width=False)

    st.subheader("2. Em que mapa o primeiro abate do ataque pesa mais?")
    st.caption("Diferença entre quantos rounds o ataque vence quando a equipe atacante consegue o primeiro abate e quantos vence quando a equipe defensora consegue o primeiro abate. Barra maior significa que, naquele mapa, conseguir o primeiro abate muda mais o round. Mapas em ordem de quantidade de rounds, entre parênteses.")
    by_map = summary_by_map(first_blood).rename(index=map_name_by_internal)
    impact_column, table_column = st.columns([3, 2])
    impact_column.altair_chart(opening_impact_chart(by_map), use_container_width=True)
    table_column.dataframe(by_map[["rounds", "ataque_abriu", "ataque_vence", "ataque_vence_se_abre", "ataque_vence_se_defesa_abre"]], use_container_width=True)

    st.subheader("3. Em que lugar do mapa o ataque consegue o primeiro abate")
    chosen_internal, chosen_map_meta = map_selector("Mapa", by_map.index.map(internal_by_name), "opening_map")
    attack_openings = first_blood[(first_blood["mapa"] == chosen_internal) & (first_blood["lado_abriu"] == "ataque") & first_blood["antes_do_plant"]]
    if chosen_map_meta is None or attack_openings.empty:
        st.info("Este mapa não tem imagem disponível ou não tem primeiros abates do ataque nos torneios escolhidos.")
    else:
        by_callout = openings_by_callout(attack_openings, chosen_map_meta)
        map_average = attack_openings["abriu_venceu"].mean()
        st.caption(f"Cada círculo é uma região do mapa, com o nome que os jogadores usam para ela. Só foram considerados o primeiro abate de cada round do ataque, antes do plant, e agrupados na região mais próxima de onde o defensor morreu. O tamanho do círculo mostra quantos primeiros abates aconteceram ali, enquanto a cor e a forma quantos desses rounds o ataque venceu, em relação à média do mapa ({map_average:.0%}). Círculo: matar um defensor ali quase garante o round. Quadrado: mesmo matando ali, o round continua em aberto.")
        map_column, table_column = st.columns([3, 2])
        if st.checkbox("Mostrar cada abate em vez das regiões"):
            won = attack_openings[attack_openings["abriu_venceu"]]
            lost = attack_openings[~attack_openings["abriu_venceu"]]
            map_column.pyplot(draw_points(chosen_map_meta, [
                ("ataque venceu o round", WON_COLOR, "o", list(zip(won["vitima_x"], won["vitima_y"]))),
                ("ataque perdeu o round", LOST_COLOR, "x", list(zip(lost["vitima_x"], lost["vitima_y"]))),
            ]))
        else:
            # Sem nomes sobre o mapa: a tabela ao lado traz as regiões
            map_column.pyplot(draw_callout_summary(chosen_map_meta, by_callout, map_average, label_min_count=10**9))
        table_column.dataframe(by_callout[["aberturas", "ataque_venceu", "ic95"]], use_container_width=True)

    st.subheader("4. Qual função de agente morre primeiro, e isso muda o custo do primeiro abate?")
    st.caption("Dividindo os agentes em duelistas, iniciadores, controladores ou sentinelas, considerando a lista pública de agentes, usada só para dar nome ao código do personagem.")
    max_seconds = st.slider("Considerar só primeiros abates até este segundo do round", 10, 150, 150, step=10, key="role_max_seconds")
    role_deaths = deaths_table()[deaths_table()["match_id"].isin(selected_ids)]
    role_first = first_death_by_role(role_deaths, max_seconds)
    share_column, cost_column = st.columns(2)
    share_column.markdown("**Quem morre primeiro e frequência nas composições de times**")
    share_column.altair_chart(grouped_bar_chart(role_share(role_deaths, max_seconds), [NEUTRAL_COLOR, ATTACK_COLOR, DEFENSE_COLOR], "fração"), use_container_width=True)
    cost_column.markdown("**Quantos rounds a equipe ainda vence depois de perder o primeiro jogador**, separado pela função do jogador perdido")
    cost_column.altair_chart(rate_chart(role_first, "funcao", "vitoria_da_vitima", "rounds", "% de rounds vencidos pela equipe que perdeu o primeiro jogador", group_column="lado", group_colors=SIDE_COLORS, order=ROLE_ORDER), use_container_width=True)
    with st.expander("Tabelas por função, por troca e por agente"):
        st.dataframe(role_first, use_container_width=False)
        st.markdown("**Com ou sem troca.** A função de quem morreu importa quando ninguém vinga a morte?")
        st.dataframe(first_death_by_role_and_trade(role_deaths, max_seconds), use_container_width=False)
        st.markdown("**Por agente**, só agentes com 30 ou mais primeiras mortes. Cuidado: a diferença entre agentes mistura o agente com o perfil de quem costuma escolhê-lo.")
        st.dataframe(first_death_by_agent(role_deaths, max_seconds), use_container_width=False)

    st.subheader("5. O primeiro abate fica mais cedo ou mais tarde ao longo da partida?")
    per_round = first_blood[first_blood["round"] <= 24].groupby("round")["segundos"].agg(
        rounds="size", p10=lambda seconds: seconds.quantile(0.10), p25=lambda seconds: seconds.quantile(0.25), mediana="median",
        p75=lambda seconds: seconds.quantile(0.75), p90=lambda seconds: seconds.quantile(0.90), media="mean", desvio_padrao="std",
    ).round(1)
    st.caption("Para cada round da partida, o segundo em que o primeiro abate acontece. A linha apresenta o valor típico, com metade dos rounds abaixo e metade acima. A faixa escura onde ficam os 50% centrais e a faixa clara os 80% centrais. O gráfico ao lado mostra a frequência de partidas que chegaram até cada round.")
    band_column, count_column = st.columns([3, 2])
    band_column.altair_chart(quantile_band_chart(per_round), use_container_width=True)
    count_column.bar_chart(per_round["rounds"], color=[NEUTRAL_COLOR], y_label="rounds contados", x_label="round da partida")
    with st.expander("Números por round"):
        st.dataframe(per_round, use_container_width=False)

with trades_tab:
    control_column, phase_column = st.columns(2)
    solo_distance = control_column.slider("Distância a partir da qual a morte conta como isolada (unidades do jogo, cerca de 100 por metro)", 500, 3000, SOLO_DISTANCE, step=250)
    phase = phase_column.radio("Momento do round", ["todas", "pré-plant", "pós-plant"], horizontal=True, help="Depois do plant os papéis se invertem: a defesa precisa entrar no site para desarmar.")
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
    traded_col.metric("Mortes trocadas", f"{selected_deaths['trocada'].mean():.0%}")
    isolated_col.metric("Mortes isoladas (entre as que tinham aliado vivo)", f"{deaths_with_allies['isolada'].mean():.0%}")
    missed_col.metric("Trocas possíveis que não aconteceram", f"{1 - possible['trocada'].mean():.0%}")

    st.subheader("1. Quanto vale trocar abates, e quanto vale ter um aliado perto?")
    st.caption("O eixo mostra quantos aliados da vítima continuaram vivos no instante em que ela morreu. Por exemplo, a barra 1 reúne mortes em que a equipe tinha 2 vivos e ficou com 1. Cada barra compara a taxa de vitória do round entre mortes trocadas e não trocadas ou entre mortes com aliado perto e sem. A comparação só junta mortes com o mesmo número de aliados e de inimigos vivos nesse instante, para não refletir o fato de a equipe já estar em vantagem numérica. Valores acima de zero ajudam a vencer o round. Exemplo de leitura da barra 1 em morte trocada: a situação era 2x2, um jogador morreu e virou 1x2. Se o aliado que sobrou trocou o abate, virou 1x1. A barra diz que, com a troca, a equipe vence cerca de 16 pontos a mais do que ficando no 1x2 sem trocar. A barra é a média de todas as quantidades de inimigos (1x1, 1x2, 1x3 e assim por diante), por isso o exemplo é uma ilustração.")
    for flag, label in [("trocada", "Morte trocada"), ("aliado_perto", "Aliado a menos do limite de isolamento")]:
        by_situation = win_rate_by_situation(deaths_with_allies, flag)
        by_situation["aliados vivos no instante da morte"] = by_situation["situacao"].str.split("v").str[0].astype(int)
        by_allies = (by_situation["diferenca"] * by_situation["mortes"]).groupby([by_situation["aliados vivos no instante da morte"], by_situation["lado"]]).sum() / by_situation.groupby(["aliados vivos no instante da morte", "lado"])["mortes"].sum()
        st.markdown(f"**{label}**")
        st.altair_chart(grouped_bar_chart(by_allies.unstack("lado").rename_axis(index="aliados da vítima vivos no instante da morte"), [ATTACK_COLOR, DEFENSE_COLOR], "diferença na vitória", "+.0%", height=260), use_container_width=True)
        with st.expander(f"Números de cada situação (aliados x inimigos vivos): {label.lower()}"):
            st.dataframe(by_situation.drop(columns=["aliados vivos no instante da morte"]), hide_index=True, use_container_width=False)

    st.subheader("2. Quando a troca era possível, ela aconteceu?")
    trade_table = trade_possibility_summary(fights, ["lado"]).rename(index={TRADE_POSSIBLE: "aliado perto, olhando para o inimigo", "aliado em alcance olhando para outro lado": "aliado perto, olhando para outro lado", "sem aliado em alcance": "nenhum aliado perto"}, level="troca_possivel")
    traded_column, won_column = st.columns(2)
    traded_column.markdown("**Quantas mortes foram trocadas**, considerando se algum aliado da vítima estava a menos de 20 m do inimigo que a matou e olhando para ele")
    traded_column.altair_chart(rate_chart(trade_table, "troca_possivel", "trocada", "mortes", "% de mortes trocadas", group_column="lado", group_colors=SIDE_COLORS), use_container_width=True)
    won_column.markdown("**Quantos rounds a equipe da vítima venceu**, nas mesmas três situações")
    won_column.altair_chart(rate_chart(trade_table, "troca_possivel", "venceu_round", "mortes", "% de rounds vencidos pela equipe da vítima", group_column="lado", group_colors=SIDE_COLORS), use_container_width=True)

    st.subheader("3. A que distância do aliado mais próximo o jogador morreu?")
    st.caption("Mortes agrupadas pela distância até o aliado vivo mais próximo, em unidades do jogo (100 unidades são cerca de 1 metro). Morte trocada: quantas foram trocadas. Equipe venceu o round: quantos desses rounds a equipe da vítima ainda venceu.")
    for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
        side_deaths = deaths_with_allies[deaths_with_allies["lado"] == side]
        side_column.markdown(f"**Jogador que morreu estava {SIDE_PHRASES[side]}**")
        side_column.altair_chart(grouped_bar_chart(summary_by_distance_band(side_deaths)[["fracao_trocadas", "venceu_round"]].rename(columns={"fracao_trocadas": "morte trocada", "venceu_round": "equipe venceu o round"}).rename_axis(index="distância até o aliado mais próximo (unidades do jogo)"), [TRADE_COLOR, WON_COLOR], "% das mortes"), use_container_width=True)
    with st.expander("Números por lado e resultado do round, e o primeiro abate separado em isolado ou trocado"):
        st.dataframe(summary_by_round_outcome(deaths_with_allies, ["lado"]).rename(index=ROUND_OUTCOME_LABELS, level="venceu_round"), use_container_width=False)
        for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
            first_deaths = first_death_summary(deaths_with_allies[deaths_with_allies["lado"] == side]).reset_index()
            first_deaths["isolada"] = first_deaths["isolada"].map({False: "acompanhada", True: "isolada"})
            first_deaths["trocada"] = first_deaths["trocada"].map({False: "não trocada", True: "trocada"})
            side_column.markdown(f"**Primeira morte do round, jogador que morreu estava {SIDE_PHRASES[side]}**")
            side_column.dataframe(first_deaths, hide_index=True, use_container_width=False)

    st.subheader("4. Onde estavam os aliados, e a morte foi em área própria ou do adversário?")
    st.markdown("""
À esquerda, onde estavam os aliados vivos no momento da morte.

- **Em grupo.** Pelo menos um aliado dentro do limite de isolamento.
- **Flanco.** Nenhum aliado perto, e os aliados todos juntos em outra área do mapa.
- **Isolado.** Nenhum aliado perto, e os aliados espalhados pelo mapa.

À direita, de quem costuma ser a região onde o jogador morreu, medido por quem fica ali nos primeiros 20 segundos dos rounds.

- **Própria.** 65% ou mais dos jogadores ali são do mesmo lado da vítima.
- **Do adversário.** 35% ou menos.
- **Disputada.** Entre os dois.
""")
    context_column, territory_column = st.columns(2)
    context_column.markdown("**Quantos rounds a equipe venceu**, conforme onde estavam os aliados")
    context_column.altair_chart(rate_chart(context_summary(deaths_with_allies, ["lado"]), "contexto", "venceu_round", "mortes", "% de rounds vencidos pela equipe da vítima", group_column="lado", group_colors=SIDE_COLORS, order=["em grupo", "flanco", "isolado", "último vivo"]), use_container_width=True)
    territory_column.markdown("**Quantos rounds a equipe venceu**, conforme de quem é a região")
    territory_column.altair_chart(rate_chart(territory_summary(deaths_with_allies[deaths_with_allies["territorio"] != "?"], ["lado"]), "territorio", "venceu_round", "mortes", "% de rounds vencidos pela equipe da vítima", group_column="lado", group_colors=SIDE_COLORS, order=["próprio", "disputado", "do adversário"]), use_container_width=True)
    with st.expander("Números de posição dos aliados e de região, e o isolamento separado por função do agente"):
        st.dataframe(context_summary(deaths_with_allies, ["lado"]), use_container_width=False)
        st.dataframe(territory_summary(deaths_with_allies, ["lado"]), use_container_width=False)
        st.markdown("**Por função do agente.** Acima do esperado: taxa de vitória do round menos o esperado para a mesma quantidade de vivos. Custo do isolamento: essa mesma conta para mortes isoladas menos para mortes acompanhadas.")
        st.dataframe(death_cost_by_role(deaths_with_allies), use_container_width=False)

    st.subheader("5. Quantas trocas possíveis viraram troca? Por equipe")
    st.caption("Só equipes com 150 ou mais mortes. Uma troca é possível quando um aliado estava a menos de 20 m de quem matou, olhando para ele, e é considerada uma troca convertida quando ela de fato ocorreu. Também foi considerado um caso para 'sem reação', quando o jogador morreu sem causar dano em quem o matou.")
    named_fights = fights.assign(time_killer=fights["time_vitima"].map({"Blue": "Red", "Red": "Blue"}))
    named_fights = with_team_names(with_team_names(named_fights, "time_vitima"), "time_killer", "nome_killer")
    st.dataframe(team_summary(named_fights).drop(columns=["kills_em_foco"]), use_container_width=False)

with collapse_tab:
    st.markdown("Colapso foi definido como três jogadores da equipe morrendo em até 10 segundos sem que a equipe mate ninguém nesse intervalo. Execução rápida é quando a spike é plantada em até 40 s, default quando é plantada depois disso, sem plant quando o round acabou antes de plantar. Contato cedo é quando o primeiro abate do round aconteceu em até 20 s. Por fim, placar é quem estava na frente antes do round começar.")
    styles = round_styles_table()
    styles = styles[styles["match_id"].isin(selected_ids) & (styles["lado"] != "?")]
    rounds_col, collapse_col, fast_col = st.columns(3)
    rounds_col.metric("Rounds contados (um por equipe)", len(styles))
    collapse_col.metric("Rounds com colapso", f"{styles['colapso'].mean():.0%}")
    fast_col.metric("Rounds de ataque com plant até 40 s", f"{(styles.loc[styles['lado'] == 'ataque', 'estilo'] == 'execução rápida').mean():.0%}")

    st.subheader("1. Colapso: com que frequência acontece e quanto custa?")
    by_side = collapse_summary(styles, ["lado"])
    side_column, map_column = st.columns([2, 3])
    side_column.markdown("**Parte dos rounds com colapso**, em cada lado")
    side_column.altair_chart(rate_chart(by_side, "lado", "colapsos", "rounds", "% dos rounds com colapso", group_column="lado", group_colors=SIDE_COLORS, height=140), use_container_width=True)
    side_column.markdown("**Quantos rounds a equipe vence** quando colapsa (quadrado) e quando não colapsa (círculo)")
    side_column.altair_chart(dumbbell_chart(by_side, "lado", "venceu_com_colapso", "venceu_sem_colapso", "com colapso", "sem colapso", "% de rounds vencidos", count_column="rounds", left_color=LOST_COLOR), use_container_width=True)
    map_column.markdown("**Parte dos rounds com colapso em cada mapa**, por lado")
    by_map_side = collapse_summary(styles, ["mapa", "lado"]).rename(index=map_name_by_internal, level="mapa").sort_values("rounds", ascending=False)
    map_column.altair_chart(rate_chart(by_map_side, "mapa", "colapsos", "rounds", "% dos rounds com colapso", group_column="lado", group_colors=SIDE_COLORS), use_container_width=True)
    collapse_internal, collapse_map_meta = map_selector("Em que regiões do mapa os colapsos acontecem", styles["mapa"].value_counts().index, "collapse_map")
    regions = collapse_regions(styles, collapse_internal)
    if collapse_map_meta is None or regions.empty:
        st.info("Este mapa não tem imagem disponível ou não tem colapsos suficientes.")
    else:
        location_by_name = {callout_name(callout): (callout["location"]["x"], callout["location"]["y"]) for callout in collapse_map_meta["callouts"]}
        regions = regions.reset_index()
        regions["x"] = regions["regiao_colapso"].map(lambda name: location_by_name.get(name, (None, None))[0])
        regions["y"] = regions["regiao_colapso"].map(lambda name: location_by_name.get(name, (None, None))[1])
        regions = regions.dropna(subset=["x", "y"])
        map_pre_plant = regions["pre_plant"].mean()
        st.caption(f"Cada círculo é uma região do mapa, só regiões com 5 ou mais colapsos. O tamanho mostra quantos colapsos aconteceram ali, enquanto a cor e a forma mostram quando, com círculo sendo antes do plant e quadrado depois do plant, em relação à média do mapa ({map_pre_plant:.0%} antes do plant).")
        for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
            side_regions = regions[regions["lado"] == side].set_index("regiao_colapso")
            side_column.markdown(f"**Colapsos da equipe {SIDE_PHRASES[side].replace('no ', 'de ').replace('na ', 'de ')}** ({int(side_regions['colapsos'].sum())} colapsos)")
            if side_regions.empty:
                side_column.info("Sem colapsos com volume neste lado.")
            else:
                side_column.pyplot(draw_rate_markers(collapse_map_meta, side_regions, "colapsos", "pre_plant", map_pre_plant, "parte dos colapsos antes do plant", label_min_count=10**9, size_per_unit=6))
        with st.expander("Números por região"):
            st.dataframe(regions.drop(columns=["x", "y"]), hide_index=True, use_container_width=False)

    st.subheader("2. Ritmo do ataque: plantar rápido rende mais? E fazer contato cedo?")
    attack_styles, contact = style_summary(styles)
    style_column, contact_column = st.columns(2)
    style_column.markdown("**Quantos rounds o ataque vence** conforme o ritmo")
    style_column.altair_chart(rate_chart(attack_styles, "estilo", "venceu", "rounds", "% de rounds vencidos pelo ataque", order=STYLE_ORDER, height=140), use_container_width=True)
    contact_column.markdown("**Quantos rounds cada lado vence** quando o primeiro abate sai até 20 s (contato cedo) ou depois (contato tarde)")
    contact_column.altair_chart(rate_chart(contact, "contato", "venceu", "rounds", "% de rounds vencidos", group_column="lado", group_colors=SIDE_COLORS, height=140), use_container_width=True)

    st.subheader("3. A equipe muda o ritmo quando está perdendo?")
    shares, wins, counts = style_by_score(styles)
    shares_column, wins_column = st.columns(2)
    shares_column.markdown("**Como os rounds de ataque se dividem entre os ritmos**, conforme o placar antes do round")
    shares_column.altair_chart(share_chart(shares, counts, STYLE_COLORS, "% dos rounds de ataque"), use_container_width=True)
    wins_column.markdown("**Parte dos rounds vencidos** em cada combinação de placar e ritmo")
    wins_column.dataframe(wins, use_container_width=False)

    st.subheader("4. Perfil de cada equipe (equipes com 40 ou mais rounds de ataque)")
    profiles = team_profiles(styles)
    st.altair_chart(team_scatter(profiles, "execução rápida", "vitoria_ataque", "rounds_ataque", "% dos rounds de ataque com plant até 40 s", "% de rounds de ataque vencidos"), use_container_width=True)
    with st.expander("Todos os números por equipe"):
        st.dataframe(profiles, use_container_width=True)

with economy_tab:
    st.markdown("Loadout é o valor das armas e escudos dos cinco jogadores. Rounds normais são todos menos o pistol (rounds 1 e 13) e o segundo round de cada metade (2 e 14). Vitória esperada pelo dinheiro é a taxa de vitória normal para a diferença de loadout vista entre as equipes.")
    economy_rounds = rounds_table()[rounds_table()["match_id"].isin(selected_ids)]
    close_rounds = economy_rounds[economy_rounds["match_id"].isin(close_match_ids(economy_rounds))]
    fights = fights_table()[fights_table()["match_id"].isin(selected_ids)]

    st.subheader("1. Quanto o dinheiro gasto em armas compra de rounds?")
    own_table, difference_table = win_rate_by_loadout(economy_rounds)
    difference_column, full_buy_column = st.columns(2)
    difference_column.markdown("**Diferença de loadout entre a equipe e o adversário.** Acima de zero, a equipe gastou mais. (todos os rounds)")
    difference_column.altair_chart(rate_chart(difference_table, "faixa_diferenca", "vitoria", "rounds", "% de rounds vencidos"), use_container_width=True)
    full_buy_column.markdown("**Pelo loadout da equipe quando o adversário comprou tudo** (20 mil ou mais, rounds normais)")
    full_buy_column.altair_chart(rate_chart(versus_full_buy(economy_rounds), "faixa_loadout", "vitoria", "rounds", "% de rounds vencidos"), use_container_width=True)
    with st.expander("Números: ganho de vitória por 1.000 créditos a mais, loadout da equipe sem olhar o adversário, e o cruzamento loadout da equipe x loadout do adversário"):
        st.dataframe(versus_full_buy(economy_rounds), use_container_width=False)
        st.dataframe(own_table, use_container_width=False)
        rates, counts = win_rate_matrix(economy_rounds)
        st.altair_chart(heatmap_chart(rates, counts, "loadout do adversário", "loadout da equipe", "% de rounds vencidos"), use_container_width=True)

    st.subheader("2. Perder um round abala a equipe no round seguinte?")
    st.caption("Round fácil perdido é quando a equipe perdeu um round em que o adversário venceu em desvantagem (clutch ou thrifty). Quadrado mostra quantos rounds seguintes a equipe deveria vencer só pelo dinheiro que tinha. Círculo mostra quantos venceu de fato.")
    all_column, close_column = st.columns(2)
    all_column.markdown("**Todas as partidas**")
    previous_labels = {"perdeu round fácil (clutch ou thrifty do adversário)": "perdeu round fácil"}
    all_column.altair_chart(dumbbell_chart(after_previous_round(economy_rounds).rename(index=previous_labels), "anterior", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "venceu de fato", "% de rounds seguintes vencidos", count_column="rounds", x_domain=[0.2, 0.7]), use_container_width=True)
    close_column.markdown(f"**Só partidas equilibradas** (até 4 rounds de diferença no placar final, {close_rounds['match_id'].nunique()} partidas)")
    close_column.altair_chart(dumbbell_chart(after_previous_round(close_rounds).rename(index=previous_labels), "anterior", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "venceu de fato", "% de rounds seguintes vencidos", count_column="rounds", x_domain=[0.2, 0.7]), use_container_width=True)
    streak_all_column, streak_close_column = st.columns(2)
    streak_all_column.markdown("**Quantos rounds seguidos a equipe tinha perdido antes deste**, todas as partidas")
    streak_all_column.altair_chart(dumbbell_chart(after_streak(economy_rounds), "derrotas", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "venceu de fato", "% de rounds vencidos", count_column="rounds", x_domain=[0.2, 0.7]), use_container_width=True)
    streak_close_column.markdown("**Quantos rounds seguidos a equipe tinha perdido antes deste**, só partidas equilibradas")
    streak_close_column.altair_chart(dumbbell_chart(after_streak(close_rounds), "derrotas", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "venceu de fato", "% de rounds vencidos", count_column="rounds", x_domain=[0.2, 0.7]), use_container_width=True)

    st.subheader("3. Quem perde o pistol deve economizar ou comprar no round 2?")
    pistol_column, cycle_column = st.columns([1, 3])
    pistol_column.markdown("**Round pistol**, quantos cada lado vence")
    pistol_column.dataframe(pistol_by_side(economy_rounds), use_container_width=False)
    overall_cycle, cycle_by_side = second_round_cycle(economy_rounds)
    cycle_column.markdown("**Equipe que perdeu o pistol, o que ela gastou no round 2 e quantos dos rounds 2, 3 e 4 venceu.** Nas tabelas, força da equipe é a taxa de vitória do round 5 em diante, para ver se quem força é uma equipe melhor ou pior.")
    cycle_column.altair_chart(grouped_bar_chart(overall_cycle[["vitoria_round_2", "vitoria_round_3", "vitoria_round_4"]].rename(columns={"vitoria_round_2": "round 2", "vitoria_round_3": "round 3", "vitoria_round_4": "round 4"}).rename_axis(index="quanto a equipe gastou no round 2"), [WON_COLOR, TRADE_COLOR, NEUTRAL_COLOR], "% de rounds vencidos"), use_container_width=True)
    with st.expander("Números dos rounds 2 a 4, no total e por lado"):
        st.dataframe(overall_cycle, use_container_width=True)
        st.dataframe(cycle_by_side, use_container_width=True)

    st.subheader("4. Perder o jogador mais caro custa mais? E sobreviver a um round perdido vale quanto?")
    expensive_column, operator_column = st.columns(2)
    expensive_column.markdown("**Comparação quando o primeiro a morrer é o jogador com maior loadout da equipe**, em relação a média da equipe na partida.")
    expensive_column.dataframe(economic_first_death(fights, "mais_caro_do_time"), use_container_width=False)
    operator_column.markdown("**Quando o primeiro a morrer tinha um Operator**")
    operator_column.dataframe(economic_first_death(fights.assign(operator=fights["arma_vitima"] == "Operator"), "operator"), use_container_width=False)
    saves = save_effect(economy_rounds, fights).loc[0:4]
    saves = saves[saves["rounds"] >= 20]
    save_loadout_column, save_win_column = st.columns(2)
    save_loadout_column.markdown("**Quanto a equipe tem para gastar no round seguinte**, conforme quantos jogadores sobreviveram ao round perdido (sem os rounds 12 e 24, em que o dinheiro zera)")
    save_loadout_column.bar_chart(saves["loadout_seguinte"], color=[WON_COLOR], y_label="loadout do round seguinte", x_label="sobreviventes")
    save_win_column.markdown("**Chance de vencer o round seguinte**, conforme quantos sobreviveram")
    save_win_column.altair_chart(rate_chart(saves, "sobreviventes", "venceu_seguinte", "rounds", "% de rounds seguintes vencidos", height=170), use_container_width=True)

with plants_tab:
    st.markdown("Cada round em que a spike foi plantada entra uma vez: onde foi plantada, quantos jogadores de cada lado estavam vivos nesse momento e se a defesa desarmou. Esperado pelos vivos: a taxa de desarme normal para a mesma quantidade de vivos de cada lado. Nos gráficos de dois pontos, o quadrado é o esperado e o círculo é o que aconteceu. Quando o círculo fica à direita do quadrado, a defesa desarmou mais do que o número de vivos explica.")
    selected_plants = plants_table()[plants_table()["match_id"].isin(selected_ids)]
    plants_col, defuse_col, time_col = st.columns(3)
    plants_col.metric("Rounds com spike plantada", len(selected_plants))
    defuse_col.metric("Desarmados pela defesa", f'{selected_plants["defusada"].mean():.1%}')
    time_col.metric("Segundo típico do plant (mediana)", f'{selected_plants["segundos_plant"].median():.0f} s')

    st.subheader("1. Quantos estão vivos no momento do plant é o que mais decide")
    rates, counts = situation_matrix(selected_plants)
    st.altair_chart(heatmap_chart(rates, counts, "defensores vivos no momento do plant", "atacantes vivos no momento do plant", "% de spikes desarmadas"), use_container_width=True)

    st.subheader("2. O segundo do plant e o site mudam a chance de desarme?")
    time_column, site_column = st.columns(2)
    time_column.markdown("**Pelo segundo em que a spike foi plantada**")
    by_time = summary_by_plant_time(selected_plants)
    time_column.altair_chart(dumbbell_chart(by_time[by_time["plants"] >= 20], "faixa_tempo", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "desarmado de fato", "% de spikes desarmadas", count_column="plants", x_domain=[0, 0.6]), use_container_width=True)
    by_site = summary_by_site(selected_plants).rename(index=map_name_by_internal, level="mapa")
    by_site_named = by_site[by_site["plants"] >= 100].reset_index()
    by_site_named["mapa_site"] = by_site_named["mapa"] + " " + by_site_named["site"]
    site_column.markdown("**Por mapa e site**, sites com 100 ou mais plants")
    site_column.altair_chart(dumbbell_chart(by_site_named.set_index("mapa_site"), "mapa_site", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "desarmado de fato", "% de spikes desarmadas", count_column="plants", x_domain=[0, 0.6]), use_container_width=True)
    with st.expander("Números por mapa e site"):
        st.dataframe(by_site, use_container_width=False)

    st.subheader("3. Onde a spike é plantada, e quais posições a defesa desarma mais")
    plant_map_internal, plant_map_meta = map_selector("Mapa", selected_plants["mapa"].value_counts().index, "plant_map")
    if plant_map_meta is None:
        st.info("Este mapa não tem imagem disponível.")
    else:
        cells = cells_for_map(selected_plants, plant_map_internal)
        map_defuse = selected_plants[selected_plants["mapa"] == plant_map_internal]["defusada"].mean()
        st.caption(f"Cada bola junta os plants feitos num quadrado de cerca de 4 metros, só quadrados com 5 ou mais plants, com uma imagem por site. Tamanho da bola: quantos plants. Cor e forma: quantos foram desarmados, em relação à média do mapa ({map_defuse:.0%}). Círculo: a defesa desarma mais do que a média ali. Quadrado: menos.")
        sites = sorted(cells["site"].unique())
        for site_column, site in zip(st.columns(len(sites)), sites):
            site_cells = cells[cells["site"] == site]
            site_column.markdown(f"**Site {site}** ({int(site_cells['plants'].sum())} plants nos quadrados mostrados)")
            site_column.pyplot(draw_rate_markers(plant_map_meta, site_cells, "plants", "defuse", map_defuse, "taxa de defuse", label_min_count=10**9, size_per_unit=3, zoom_padding=90))
        with st.expander("Números de cada quadrado"):
            st.dataframe(cells[["site", "plants", "defuse", "esperado_pelos_vivos", "acima_do_esperado"]], use_container_width=False)

    st.subheader("4. O posicionamento no momento do plant muda o desarme? E como a defesa retoma o site?")
    st.caption("Três medidas tiradas no instante do plant, todas comparadas com o esperado pelos vivos. Atacantes no site: quantos estavam a menos de 15 metros da spike. Olhando para fora: parte dos aliados de quem plantou que estava de costas para a spike, ou seja, vigiando as entradas. Distância da defesa: a que distância da spike estava o defensor do meio (metade mais perto, metade mais longe).")
    selected_setups = setups_table()[setups_table()["match_id"].isin(selected_ids)]
    on_site_column, watching_column, defense_column = st.columns(3)
    on_site_column.markdown("**Atacantes a menos de 15 m da spike**")
    on_site_column.altair_chart(dumbbell_chart(defuse_by(selected_setups, "atacantes_no_site"), "atacantes_no_site", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "desarmado de fato", "% de spikes desarmadas", count_column="plants", x_domain=[0, 0.6]), use_container_width=True)
    watching_column.markdown("**Parte dos aliados de quem plantou olhando para fora do site**")
    watching_column.altair_chart(dumbbell_chart(defuse_by(selected_setups, watching_bands(selected_setups)), "olhando_para_fora", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "desarmado de fato", "% de spikes desarmadas", count_column="plants", x_domain=[0, 0.6]), use_container_width=True)
    defense_column.markdown("**Distância da defesa até a spike no momento do plant**")
    defense_column.altair_chart(dumbbell_chart(defuse_by(selected_setups, "faixa_defesa"), "faixa_defesa", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "desarmado de fato", "% de spikes desarmadas", count_column="plants", x_domain=[0, 0.6]), use_container_width=True)
    st.markdown("**Retomada do site: quando a defesa desarmou, quantos atacantes ainda estavam vivos e a que distância da spike estava o mais próximo**")
    st.dataframe(retake_summary(selected_setups), use_container_width=False)

with match_tab:
    chosen_file = st.selectbox("Partida", selected_matches["arquivo"].tolist())
    chosen_match = selected_matches[selected_matches["arquivo"] == chosen_file].iloc[0]
    match = load_match(Path(chosen_match["caminho"]))
    st.write(f'{chosen_match["torneio"]} · {chosen_match["mapa"]} · Blue {chosen_match["rounds_blue"]} x {chosen_match["rounds_red"]} Red')

    st.subheader("Posições no minimapa a cada abate, plant e desarme")
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
        st.info("Este mapa não tem imagem disponível.")
    elif not events:
        st.info("Este round não tem abate, plant nem desarme, então não há posição registrada.")
    else:
        event_index = st.slider("Momento", 0, len(events) - 1, 0, format="evento %d") if len(events) > 1 else 0
        st.caption(describe_event(events[event_index], name_by_puuid, round_result))
        map_column, _ = st.columns([4, 1])
        map_column.pyplot(draw_round_map(map_meta, events, event_index, selected_puuid, team_by_puuid, name_by_puuid))

    st.subheader("Primeiro abate de cada round")
    st.dataframe(first_blood_per_round_table(first_blood_rows()[first_blood_rows()["match_id"] == chosen_match["match_id"]]), hide_index=True)

    st.subheader("Mortes isoladas e trocas em cada round")
    match_deaths = with_solo_flag(deaths_table()[deaths_table()["match_id"] == chosen_match["match_id"]], SOLO_DISTANCE)
    st.dataframe(deaths_per_round_table(match_deaths, match["roundResults"]), hide_index=True)

    with st.expander("Jogadores, rounds e dados brutos da partida"):
        match_players = players[players["match_id"] == chosen_match["match_id"]].drop(columns=["match_id", "puuid"])
        st.dataframe(match_players.sort_values(["time", "score"], ascending=[True, False]), hide_index=True)
        st.dataframe(rounds[rounds["match_id"] == chosen_match["match_id"]].drop(columns=["match_id"]), hide_index=True)
        st.json(match["matchInfo"])

with prediction_tab:
    st.markdown("As medidas das conclusões (primeiro abate, troca, isolamento) explicam e preveem quem vence a partida, sem usar nenhum resultado no caminho? O lado de cada round vem de quem planta a spike na metade, sem contagem de rounds, placar nem ordem, e o único rótulo é quem venceu a partida. Os nomes das equipes vêm do nome do arquivo. Esta aba ignora o filtro de torneios.")
    prediction = prediction_tables()
    chance_median, chance_95 = prediction["acaso"]
    st.subheader("1. Dentro da mesma partida, com os rounds embaralhados")
    st.caption(f"A equipe com a medida melhor na própria partida foi a vencedora? Para comparar, embaralhando quem venceu ao acaso o acerto típico é {chance_median:.1%} e chega a {chance_95:.1%} em 5% das vezes.")
    st.dataframe(prediction["dentro"], hide_index=True, use_container_width=False)
    st.subheader("2. Previsão usando o perfil da equipe nas outras partidas do campeonato")
    st.caption("Só equipes com pelo menos duas outras partidas. A última linha é a comparação: prever pela taxa de vitória da equipe nas outras partidas.")
    st.dataframe(prediction["outras"], hide_index=True, use_container_width=False)
    st.subheader("3. Previsão usando só partidas anteriores no calendário")
    st.dataframe(prediction["anteriores"], hide_index=True, use_container_width=False)
    st.subheader("4. Ranking de cada campeonato: perfil combinado contra taxa de vitória")
    st.caption("Equipes com 3 ou mais partidas. Perfil: soma das medidas, cada uma padronizada e com o sinal de bom ou ruim. Spearman: quanto a ordem das equipes pelo perfil coincide com a ordem pela taxa de vitória (1 é igual, 0 é sem relação).")
    for tournament_column, (tournament, table) in zip(st.columns(2) + st.columns(2), prediction["rankings"].items()):
        tournament_column.markdown(f"**{tournament}** (Spearman {table['spearman'].iloc[0]})")
        tournament_column.dataframe(table.drop(columns=["spearman"]), use_container_width=True)

with conclusions_tab:
    st.markdown((Path(__file__).parent / "CONCLUSOES.md").read_text(encoding="utf-8"))

with explore_tab:
    st.markdown("Fora do escopo de decisões de equipe, guardado como exploração: a arma e a distância de cada morte, se a vítima reagiu, números individuais de combate e o dicionário de campos dos arquivos.")
    fights = fights_table()[fights_table()["match_id"].isin(selected_ids)]
    st.subheader("Arma da vítima e distância de quem matou")
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

    st.subheader("A vítima reagiu antes de morrer?")
    st.caption("Duelo: a vítima causou dano em quem a matou. Foco: dois ou mais inimigos causaram dano na vítima. Sem reação: nenhum dos dois.")
    st.dataframe(fight_class_summary(fights, ["lado"]), use_container_width=False)

    st.subheader("Jogadores: abates, mortes e pontuação")
    st.dataframe(players_summary(selected_players), hide_index=True)

    st.subheader("Campos dos arquivos de partida")
    relevant_fields, irrelevant_fields = build_field_tables()
    field_filter = st.text_input("Filtrar campo")
    st.dataframe(relevant_fields[relevant_fields["campo"].str.contains(field_filter, regex=False)], hide_index=True)
    with st.container(border=True):
        st.markdown("**Campos sem informação.** Têm o mesmo valor em todas as partidas.")
        st.dataframe(irrelevant_fields.drop(columns=["distintos"]).rename(columns={"mais_frequentes": "valor"}), hide_index=True)
