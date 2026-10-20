"""Painel local para explorar as partidas do hackathon, organizado pelas decisões de macro game.

Uso: streamlit run app.py
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from agent_roles import ROLE_ORDER, death_cost_by_role, first_death_by_agent, first_death_by_role, first_death_by_role_and_trade, role_share, with_interval
from economy import after_previous_round, after_streak, build_rounds_table, close_match_ids, pistol_by_side, second_round_cycle, versus_full_buy, win_rate_by_loadout, win_rate_matrix
from explore_fields import DEFAULT_DATA_DIR, collect_field_stats, find_match_files, load_match, split_irrelevant_fields, summarize_fields
from maps import callout_name, load_maps_by_url, nearest_callout
from data_quality import data_signature, dataset_quality, eligible_match_ids
from match_events import alive_puuids
from plants import build_plants_table, cells_for_map, situation_matrix, summary_by_plant_time, summary_by_site
from predict import forecast_accuracy, in_match_accuracy, load_matches, match_pairs, permutation_ceiling, team_features, tournament_ranking
from round_style import STYLE_ORDER, build_round_styles, collapse_regions, collapse_summary, style_by_score, style_summary, team_profiles
from setups import build_setups_table, defuse_by, retake_summary, watching_bands
from round_map import describe_event, draw_callout_summary, draw_points, draw_rate_markers, draw_round_map, round_events
from fights import TRADE_POSSIBLE, build_fights_table, distance_matrix, distance_summary, economic_first_death, fight_class_summary, next_loadout_by_outcome, player_range_discipline, post_plant_exchange, save_effect, team_summary, trade_possibility_summary
from winprob import build_state_table, match_win_added
from predict import attacking_team_by_round
from first_blood import TIME_LABELS, first_blood_table, plant_summary, summary_by_map, wilson_interval, win_rate_by_time
from factors import build_factor_tables, factor_ranking, good_factor_ranking, match_player_summary, match_team_summary, match_timeline, player_decisions, team_round_factors
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
STYLE_COLORS = {"execução rápida": WON_COLOR, "default": TRADE_COLOR, "sem plant": LOST_COLOR, "plant excluído": NEUTRAL_COLOR}
ROUND_OUTCOME_LABELS = {False: "perdeu o round", True: "venceu o round"}
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
        "inicio": datetime.fromtimestamp(info["gameStartMillis"] / 1000, tz=ZoneInfo("America/Sao_Paulo")),
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


@st.cache_data(show_spinner=False)
def build_tables(signature):
    match_rows, player_rows, round_rows = [], [], []
    for match_file in find_match_files(DEFAULT_DATA_DIR):
        match = load_match(match_file)
        match_id = match["matchInfo"]["matchId"]
        match_rows.append(match_row(match_file, match))
        player_rows += [player_row(match_id, player) for player in match["players"] if not player["isObserver"]]
        round_rows += [round_row(match_id, rr) for rr in match["roundResults"]]
    matches = pd.DataFrame(match_rows)
    if not matches.empty:
        matches["mapa"] = matches["mapa_interno"].map(map_names_from_file_names(matches))
    return matches, pd.DataFrame(player_rows), pd.DataFrame(round_rows)


@st.cache_data(show_spinner=False)
def build_field_tables(signature, match_ids):
    paths = [path for path in find_match_files(DEFAULT_DATA_DIR)
             if load_match(path)["matchInfo"]["matchId"] in match_ids]
    types_by_field, values_by_field = collect_field_stats(paths)
    relevant, irrelevant = split_irrelevant_fields(summarize_fields(types_by_field, values_by_field))
    columns = ["campo", "tipos", "ocorrencias", "distintos", "mais_frequentes"]
    return pd.DataFrame(relevant, columns=columns), pd.DataFrame(irrelevant, columns=columns)


@st.cache_data(show_spinner=False)
def quality_cached(signature, include_anomalous):
    return dataset_quality(), eligible_match_ids(include_anomalous=include_anomalous)


@st.cache_data(show_spinner=False)
def maps_cached(signature):
    return load_maps_by_url()


def maps_by_url():
    return maps_cached(DATA_SIGNATURE)


@st.cache_data(show_spinner=False)
def analytical_tables(signature, match_ids, kind):
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
        return build_fights_table(analytical_tables(signature, match_ids, "deaths"), match_ids=ids)
    if kind == "styles":
        return build_round_styles(analytical_tables(signature, match_ids, "deaths"),
                                  analytical_tables(signature, match_ids, "rounds"),
                                  analytical_tables(signature, match_ids, "matches"), match_ids=ids)
    if kind == "setups":
        return build_setups_table(match_ids=ids)
    raise ValueError(f"Tabela desconhecida: {kind}")


def scoped_table(kind):
    return analytical_tables(DATA_SIGNATURE, SELECTED_IDS, kind)


def deaths_table(): return scoped_table("deaths")
def rounds_table(): return scoped_table("rounds")
def plants_table(): return scoped_table("plants")
def matches_table(): return scoped_table("matches")
def fights_table(): return scoped_table("fights")
def round_styles_table(): return scoped_table("styles")
def setups_table(): return scoped_table("setups")


def first_blood_rows():
    return first_blood_table(deaths_table())


@st.cache_data(show_spinner=False)
def factors_cached(signature, match_ids):
    deaths, flagged = build_factor_tables(analytical_tables(signature, match_ids, "fights"),
                                         analytical_tables(signature, match_ids, "rounds"),
                                         analytical_tables(signature, match_ids, "styles"))
    return deaths, flagged


def factor_tables():
    return factors_cached(DATA_SIGNATURE, SELECTED_IDS)


@st.cache_data(show_spinner=False)
def association_tables(signature, match_ids):
    deaths, flagged = factors_cached(signature, match_ids)
    return factor_ranking(deaths, flagged), good_factor_ranking(deaths, flagged)


@st.cache_data(show_spinner=False)
def state_tables(signature, match_ids, exclude_match_id):
    return build_state_table(analytical_tables(signature, match_ids, "deaths"),
                             analytical_tables(signature, match_ids, "plants"),
                             analytical_tables(signature, match_ids, "rounds"),
                             exclude_match_id=exclude_match_id)


@st.cache_data(show_spinner=False)
def prediction_cached(signature, match_ids):
    matches = analytical_tables(signature, match_ids, "matches")
    features = team_features(analytical_tables(signature, match_ids, "deaths"), matches)
    pairs = match_pairs(matches, features)
    chance_95, chance_median = permutation_ceiling(pairs)
    return {"dentro": in_match_accuracy(pairs), "acaso": (chance_median, chance_95),
            "outras": forecast_accuracy(matches, features, only_previous=False),
            "anteriores": forecast_accuracy(matches, features, only_previous=True),
            "rankings": tournament_ranking(matches, features)}


def prediction_tables():
    return prediction_cached(DATA_SIGNATURE, SELECTED_IDS)


def with_team_names(table, team_column, name_column="nome_time"):
    """Troca a cor do time (Blue, Red) pelo nome que vem do arquivo da partida."""
    name_by_match_team = {(row.match_id, color): getattr(row, f"nome_{color.lower()}") for row in matches_table().itertuples() for color in ["Blue", "Red"]}
    return table.assign(**{name_column: [name_by_match_team.get((match_id, team), team) for match_id, team in zip(table["match_id"], table[team_column])]})


def display_number(value, spec=".1f", suffix=""):
    return format(value, spec) + suffix if pd.notna(value) else "sem amostra"


def empty_chart(message="Sem amostra suficiente para este gráfico"):
    return alt.Chart(pd.DataFrame({"aviso": [message]})).mark_text(color="#444444", fontSize=13).encode(text="aviso:N").properties(height=100)


def category_axis(column, order):
    return alt.Y(f"{column}:N", sort=order, title=None, axis=alt.Axis(labelOverlap=False, labelLimit=340))


def rate_chart(table, category_column, rate_column, count_column, x_title, color=WON_COLOR, group_column=None, group_colors=None, order=None, height=None):
    """Barras horizontais de uma taxa por categoria, intervalo de 95% (Wilson) como traço e a contagem ao lado. group_column separa as barras por cor."""
    if table.empty:
        return empty_chart()
    data = with_interval(table.reset_index(), rate_column, count_column)
    data[category_column] = data[category_column].astype(str)
    order = [str(value) for value in order] if order else list(dict.fromkeys(data[category_column]))
    tooltip = [category_column, count_column, alt.Tooltip(f"{rate_column}:Q", format=".3f"), alt.Tooltip("ic95_baixo:Q", format=".3f"), alt.Tooltip("ic95_alto:Q", format=".3f")]
    base = alt.Chart(data).encode(y=category_axis(category_column, order), tooltip=tooltip + ([group_column] if group_column else []))
    if group_column:
        groups = list(group_colors)
        base = base.encode(yOffset=alt.YOffset(f"{group_column}:N", sort=groups), color=alt.Color(f"{group_column}:N", scale=alt.Scale(domain=groups, range=list(group_colors.values())), title=None, legend=alt.Legend(orient="top", columns=1, labelLimit=500)))
        bars = base.mark_bar().encode(x=alt.X(f"{rate_column}:Q", title=x_title))
    else:
        bars = base.mark_bar(color=color).encode(x=alt.X(f"{rate_column}:Q", title=x_title))
    rules = base.mark_rule(strokeWidth=2).encode(x="ic95_baixo:Q", x2="ic95_alto:Q", color=alt.value("#4a4a4a"))
    # O nome do grupo vai escrito ao lado da contagem, para não depender só da cor
    count_labels = data[count_column].map(lambda count: f"{count:,.0f}" if pd.notna(count) else "sem amostra").astype("string")
    data["rotulo_contagem"] = count_labels if not group_column else data[group_column].astype("string").str.cat(count_labels, sep=" · ")
    counts = base.mark_text(align="left", dx=4, fontSize=12).encode(x="ic95_alto:Q", text="rotulo_contagem:N", color=alt.value("#6b6b6b"))
    rows = len(order) * (len(group_colors) if group_column else 1)
    return (bars + rules + counts).properties(height=height or max(120, 24 * rows + 40), autosize=FIT_WIDTH)


def dumbbell_chart(table, category_column, left_column, right_column, left_label, right_label, x_title, count_column=None, left_color=NEUTRAL_COLOR, right_color=WON_COLOR, order=None, x_domain=None):
    """Dois pontos ligados por categoria, para comparar um valor de referência (esquerda) com o observado (direita)."""
    if table.empty:
        return empty_chart()
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
    if rates.empty or counts.empty:
        return empty_chart()
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
    if shares.empty:
        return empty_chart()
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
    text = alt.Chart(long).mark_text(fontSize=12, color="white").encode(y=y, x="meio:Q", text="texto:N")
    return (bars + text).properties(height=max(120, 32 * long["rotulo"].nunique() + 40), autosize=FIT_WIDTH)


def grouped_bar_chart(wide, series_colors, x_title, value_format=".0%", height=None):
    """Barras horizontais por categoria com uma barra por série. O nome da série vai escrito ao lado do valor, para não depender da cor."""
    if wide.empty:
        return empty_chart()
    wide = wide.copy()
    if isinstance(wide.index, pd.MultiIndex):
        wide.index = wide.index.map(lambda values: " · ".join(map(str, values)))
    long = wide.rename_axis(index="categoria", columns="serie").stack().rename("valor").reset_index()
    long["categoria"] = long["categoria"].astype(str)
    series = [column for column in wide.columns]
    long["texto"] = long["serie"].astype(str) + " · " + long["valor"].map(lambda value: format(value, value_format))
    y = category_axis("categoria", list(dict.fromkeys(long["categoria"])))
    y.title = wide.index.name
    base = alt.Chart(long).encode(y=y, yOffset=alt.YOffset("serie:N", sort=series), tooltip=["categoria", "serie", alt.Tooltip("valor:Q", format=value_format)])
    bars = base.mark_bar().encode(x=alt.X("valor:Q", title=x_title), color=alt.Color("serie:N", scale=alt.Scale(domain=series, range=list(series_colors)), title=None, legend=alt.Legend(orient="top", columns=1, labelLimit=500)))
    labels = base.mark_text(align="left", dx=4, fontSize=12, color="#6b6b6b").encode(x=alt.X("valor:Q"), text="texto:N")
    return (bars + labels).properties(height=height or max(120, 22 * len(long) + 40), autosize=FIT_WIDTH)


def team_scatter(profiles, x_column, y_column, size_column, x_title, y_title):
    """Um ponto por time com o nome ao lado, tamanho pelo volume."""
    if profiles.empty:
        return empty_chart()
    data = profiles.reset_index()
    x = alt.X(f"{x_column}:Q", title=x_title, axis=alt.Axis(format="%"))
    y = alt.Y(f"{y_column}:Q", title=y_title, axis=alt.Axis(format="%"), scale=alt.Scale(zero=False))
    points = alt.Chart(data).mark_circle(color=WON_COLOR, opacity=0.7).encode(x=x, y=y, size=alt.Size(f"{size_column}:Q", title="rounds de ataque"), tooltip=["time", size_column, alt.Tooltip(f"{x_column}:Q", format=".0%"), alt.Tooltip(f"{y_column}:Q", format=".0%")])
    labelled = data[data[size_column] >= data[size_column].quantile(0.5)]
    labels = alt.Chart(labelled).mark_text(align="left", dx=8, fontSize=12, color="#333333").encode(x=x, y=y, text="time:N")
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
    summary["kd"] = (summary["kills"] / summary["deaths"].where(summary["deaths"] != 0)).round(2)
    summary["score_por_round"] = (summary["score"] / summary["rounds"]).round(0)
    return summary.sort_values("kills", ascending=False).reset_index(drop=True)


def event_position_table(event, names, teams):
    alive = alive_puuids(event)
    rows = [{"jogador": names.get(p["puuid"], p["puuid"]), "equipe": teams.get(p["puuid"], "?"),
             "estado": "vivo" if p["puuid"] in alive else "morto neste instante", "x": p["location"]["x"], "y": p["location"]["y"]}
            for p in event.get("locations", [])]
    if event.get("victim") and event.get("victim_location"):
        puuid = event["victim"]
        if not any(p["puuid"] == puuid for p in event.get("locations", [])):
            rows.append({"jogador": names.get(puuid, puuid), "equipe": teams.get(puuid, "?"),
                         "estado": "morto neste instante", "x": event["victim_location"].get("x"), "y": event["victim_location"].get("y")})
    return pd.DataFrame(rows, columns=["jogador", "equipe", "estado", "x", "y"])


def map_selector(label, internal_names, key):
    """Seletor de mapa pelo nome legível, devolvendo o nome interno e o metadado."""
    names = list(dict.fromkeys(map_name_by_internal.get(internal, internal) for internal in internal_names))
    if not names:
        return None, None
    chosen_name = st.selectbox(label, names, key=key)
    internal = internal_by_name.get(chosen_name, chosen_name)
    return internal, maps_by_url().get(f"/Game/Maps/{internal}/{internal}")


DATA_SIGNATURE = data_signature()
matches, players, rounds = build_tables(DATA_SIGNATURE)
if matches.empty:
    st.info("Nenhuma partida disponível. Baixe os JSONs seguindo o README.")
    st.stop()

st.sidebar.title("Macro game")
include_anomalous = st.sidebar.checkbox("Incluir partidas sinalizadas na qualidade", value=False)
quality, eligible_ids = quality_cached(DATA_SIGNATURE, include_anomalous)
all_tournaments = sorted(matches["torneio"].unique())
chosen_tournaments = st.sidebar.multiselect("Torneios", all_tournaments, default=all_tournaments)
all_versions = sorted(matches["versao"].unique())
chosen_versions = st.sidebar.multiselect("Versões do jogo", all_versions, default=all_versions)
st.sidebar.caption("Torneios, versões e qualidade definem a amostra de todas as análises e referências. Os JSONs brutos são preservados.")
st.sidebar.caption("Os intervalos exibidos são exploratórios; os traços dos gráficos com dois pontos apenas os conectam. Sobreposição não prova igualdade; associação não mede efeito de uma decisão.")
selected_matches = matches[matches["torneio"].isin(chosen_tournaments)
                           & matches["versao"].isin(chosen_versions)
                           & matches["match_id"].isin(eligible_ids)]
selected_ids = set(selected_matches["match_id"])
SELECTED_IDS = tuple(sorted(selected_ids))
selected_players = players[players["match_id"].isin(selected_ids)]
selected_rounds = rounds[rounds["match_id"].isin(selected_ids)]
map_name_by_internal = dict(zip(matches["mapa_interno"], matches["mapa"]))
internal_by_name = {name: internal for internal, name in map_name_by_internal.items()}

sections = ["Ferramenta proposta", "Visão geral", "Abertura", "Trocas e isolamento", "Colapso e estilo", "Economia", "Plant e defuse", "Partida", "Previsão", "Conclusões", "Exploração", "Qualidade dos dados"]
active_section = st.selectbox("Seção", sections, index=1, key="section")
st.caption(f"Amostra selecionada: {len(selected_matches)} partidas · {len(selected_rounds):,} rounds · {selected_players['puuid'].nunique()} participantes. Horários em São Paulo.")
if not selected_ids:
    st.info("Selecione ao menos um torneio e uma versão com partidas elegíveis.")
    st.stop()


if active_section == "Visão geral":
    matches_col, rounds_col, players_col = st.columns(3)
    matches_col.metric("Partidas", len(selected_matches))
    rounds_col.metric("Rounds", len(selected_rounds))
    players_col.metric("Jogadores distintos", selected_players["puuid"].nunique())
    st.markdown("""
**O que o painel descreve**

- **Abertura:** primeiro instante com abate adversário válido. Se as duas equipes abatem no mesmo timestamp, não há abridor definido.
- **Troca temporal:** o killer é abatido pela equipe adversária em até cinco segundos, inclusive simultaneidade; não comprova reação ao abate anterior.
- **Proximidade e direção compatíveis:** aliado até 2.000 unidades do killer e com olhar até 45°. Não verifica parede, smoke ou disponibilidade de disparo.
- **Isolamento:** distância ao aliado vivo mais próximo; o limite ajustável recalcula também o contexto. Sem aliado vivo, não há distância ao aliado.
- **Separado do grupo:** sem aliado perto e pelo menos dois aliados na mesma grande região; não identifica uma rota de flanco.
- **Colapso:** três vítimas distintas de abates adversários em dez segundos, sem abate da equipe na janela. Mortes ambientais e eventos após decisão não contam.
- **Estilo observado:** tempo do plant válido, até 40 s ou após 40 s. Não mede intenção tática nem identifica execuções que falharam antes do plant.
- **Loadout:** valor do equipamento no início do round. Não é gasto nem dinheiro disponível; armas coletadas durante o round não são observadas.
- **Referência pelos vivos:** média observada para a mesma situação numérica, dentro da amostra selecionada. O resíduo não é o efeito causal da posição.
- **Referência da equipe:** taxa descritiva de rounds da equipe na própria partida. Não controla independentemente sua força.

As distâncias vêm em unidades do jogo. A conversão de 100 unidades por metro é uma aproximação não validada. As partidas podem ter prorrogação; chegar a 13 rounds nem sempre encerra o jogo. As posições são snapshots de eventos, sem trajetória contínua ou informação completa de linha de tiro.
""")
    maps_column, results_column = st.columns(2)
    maps_column.markdown("**Partidas em cada mapa**")
    maps_column.bar_chart(selected_matches["mapa"].value_counts(), horizontal=True, color=[NEUTRAL_COLOR], x_label="partidas", y_label="")
    results_column.markdown("**Como os rounds terminam** (spike desarmada, spike explodiu, equipe eliminada, tempo esgotado)")
    results_column.bar_chart(selected_rounds["resultado"].value_counts(), horizontal=True, color=[NEUTRAL_COLOR], x_label="rounds", y_label="")
    with st.expander("Lista de partidas"):
        st.dataframe(selected_matches.drop(columns=["match_id", "caminho", "mapa_interno", "mapa_do_arquivo"]), hide_index=True)

if active_section == "Abertura":
    st.caption("O tempo conta a partir do início do round, depois da fase de compra.")
    first_blood = first_blood_rows()[first_blood_rows()["match_id"].isin(selected_ids)]
    rounds_col, median_col, opener_col = st.columns(3)
    rounds_col.metric("Rounds com abridor definido", len(first_blood))
    median_col.metric("Segundo típico do primeiro abate (mediana)", display_number(first_blood["segundos"].median(), suffix=" s"))
    opener_col.metric("Quem consegue o primeiro abate vence o round", display_number(first_blood["abriu_venceu"].mean(), ".1%"))
    st.caption(f"Aberturas ambíguas entre equipes: {first_blood.attrs.get('rounds_abertura_ambigua', 0)} rounds. Mortes sem abertura válida: {first_blood.attrs.get('rounds_sem_abertura_valida', 0)} rounds. Simultâneos da mesma equipe não recebem localização individual arbitrária.")

    st.subheader("1. Quem consegue o primeiro abate vence o round? Isso muda conforme o tempo em que ele acontece?")
    rate_column, count_column = st.columns([3, 2])
    rate_column.altair_chart(rate_chart(win_rate_by_time(first_blood), "faixa", "abriu_venceu", "rounds", "% de rounds vencidos pela equipe que conseguiu o primeiro abate", group_column="lado_abriu", group_colors=SIDE_COLORS, order=TIME_LABELS), width="stretch")
    count_column.markdown("**Em que segundo o primeiro abate acontece**, separado pelo lado que fez o abate")
    count_column.altair_chart(grouped_bar_chart(pd.crosstab(first_blood["faixa"], first_blood["lado_abriu"]).reindex(TIME_LABELS), [ATTACK_COLOR, DEFENSE_COLOR], "rounds", ","), width="stretch")
    with st.expander("Primeiro abate antes ou depois do plant"):
        st.dataframe(plant_summary(first_blood).rename(index={True: "antes do plant", False: "depois do plant"}, level="antes_do_plant"), width="content")

    st.subheader("2. Diferença observada conforme quem abre, por mapa")
    st.caption("Taxa de vitória do ataque quando ele abre menos a taxa quando a defesa abre. A diferença descreve grupos observados, sem isolar efeito causal ou força das equipes. Intervalos individuais sobrepostos não provam equivalência entre mapas. Mapas em ordem de amostra.")
    by_map = summary_by_map(first_blood).rename(index=map_name_by_internal)
    impact_column, table_column = st.columns([3, 2])
    impact_column.altair_chart(opening_impact_chart(by_map), width="stretch")
    table_column.dataframe(by_map[["rounds", "ataque_abriu", "ataque_vence", "ataque_vence_se_abre", "ataque_vence_se_defesa_abre"]], width="stretch")

    st.subheader("3. Em que lugar do mapa o ataque consegue o primeiro abate")
    chosen_internal, chosen_map_meta = map_selector("Mapa", by_map.index.map(internal_by_name), "opening_map")
    attack_openings = first_blood[(first_blood["mapa"] == chosen_internal) & (first_blood["lado_abriu"] == "ataque") & first_blood["antes_do_plant"]].dropna(subset=["vitima_x", "vitima_y"])
    if chosen_map_meta is None or attack_openings.empty:
        st.info("Este mapa não tem imagem disponível ou não tem primeiros abates do ataque nos torneios escolhidos.")
    else:
        by_callout = openings_by_callout(attack_openings, chosen_map_meta)
        map_average = attack_openings["abriu_venceu"].mean()
        st.caption(f"Cada círculo é uma região do mapa, com o nome que os jogadores usam para ela. Só foram considerados o primeiro abate de cada round do ataque, antes do plant, e agrupados na região mais próxima de onde o defensor morreu. O tamanho do círculo mostra quantos primeiros abates aconteceram ali, enquanto a cor e a forma quantos desses rounds o ataque venceu, em relação à média do mapa ({map_average:.0%}). Círculos e quadrados indicam taxas acima ou abaixo da referência; amostras pequenas têm grande incerteza.")
        map_column, table_column = st.columns([3, 2])
        if st.checkbox("Mostrar cada abate em vez das regiões"):
            won = attack_openings[attack_openings["abriu_venceu"]]
            lost = attack_openings[~attack_openings["abriu_venceu"]]
            map_column.pyplot(draw_points(chosen_map_meta, [
                ("ataque venceu o round", WON_COLOR, "o", list(zip(won["vitima_x"], won["vitima_y"]))),
                ("ataque perdeu o round", LOST_COLOR, "x", list(zip(lost["vitima_x"], lost["vitima_y"]))),
            ]), alt="Posições de aberturas do ataque, separadas pelo resultado posterior do round.", width="stretch")
        else:
            # Sem nomes sobre o mapa: a tabela ao lado traz as regiões
            map_column.pyplot(draw_callout_summary(chosen_map_meta, by_callout, map_average, label_min_count=10**9), alt="Aberturas por região; taxas, contagens e intervalos na tabela ao lado.", width="stretch")
        table_column.dataframe(by_callout[["aberturas", "ataque_venceu", "ic95"]], width="stretch")

    st.subheader("4. Função da primeira vítima e resultado posterior")
    st.caption("Dividindo os agentes em duelistas, iniciadores, controladores ou sentinelas, considerando a lista pública de agentes, usada só para dar nome ao código do personagem.")
    max_seconds = st.slider("Considerar só primeiros abates até este segundo do round", 10, 150, 150, step=10, key="role_max_seconds")
    role_deaths = deaths_table()[deaths_table()["match_id"].isin(selected_ids)]
    role_first = first_death_by_role(role_deaths, max_seconds)
    share_column, cost_column = st.columns(2)
    share_column.markdown("**Quem morre primeiro e frequência nas composições de times**")
    share_column.altair_chart(grouped_bar_chart(role_share(role_deaths, max_seconds), [NEUTRAL_COLOR, ATTACK_COLOR, DEFENSE_COLOR], "fração"), width="stretch")
    cost_column.markdown("**Quantos rounds a equipe ainda vence depois de perder o primeiro jogador**, separado pela função do jogador perdido")
    cost_column.altair_chart(rate_chart(role_first, "funcao", "vitoria_da_vitima", "rounds", "% de rounds vencidos pela equipe que perdeu o primeiro jogador", group_column="lado", group_colors=SIDE_COLORS, order=ROLE_ORDER), width="stretch")
    with st.expander("Tabelas por função, por troca e por agente"):
        st.dataframe(role_first, width="content")
        st.markdown("**Com ou sem troca.** A função de quem morreu importa quando ninguém vinga a morte?")
        st.dataframe(first_death_by_role_and_trade(role_deaths, max_seconds), width="content")
        st.markdown("**Por agente**, só agentes com 30 ou mais primeiras mortes. Cuidado: a diferença entre agentes mistura o agente com o perfil de quem costuma escolhê-lo.")
        st.dataframe(first_death_by_agent(role_deaths, max_seconds), width="content")

    st.subheader("5. O primeiro abate fica mais cedo ou mais tarde ao longo da partida?")
    per_round = first_blood[first_blood["round"] <= 24].groupby("round")["segundos"].agg(
        rounds="size", p10=lambda seconds: seconds.quantile(0.10), p25=lambda seconds: seconds.quantile(0.25), mediana="median",
        p75=lambda seconds: seconds.quantile(0.75), p90=lambda seconds: seconds.quantile(0.90), media="mean", desvio_padrao="std",
    ).round(1)
    st.caption("Para cada round da partida, o segundo em que o primeiro abate acontece. A linha apresenta o valor típico, com metade dos rounds abaixo e metade acima. A faixa escura onde ficam os 50% centrais e a faixa clara os 80% centrais. O gráfico ao lado mostra a frequência de partidas que chegaram até cada round.")
    band_column, count_column = st.columns([3, 2])
    band_column.altair_chart(quantile_band_chart(per_round), width="stretch")
    count_column.bar_chart(per_round["rounds"], color=[NEUTRAL_COLOR], y_label="rounds contados", x_label="round da partida")
    with st.expander("Números por round"):
        st.dataframe(per_round, width="content")

if active_section == "Trocas e isolamento":
    control_column, phase_column = st.columns(2)
    solo_distance = control_column.slider("Distância a partir da qual a morte conta como isolada (unidades do jogo, cerca de 100 por metro)", 500, 3000, SOLO_DISTANCE, step=250)
    phase = phase_column.radio("Momento do round", ["todas", "pré-plant", "pós-plant"], horizontal=True, help="Depois do plant os papéis se invertem: a defesa precisa entrar no site para desarmar.")
    selected_deaths = deaths_table()[deaths_table()["diagnostico_tatico"]].copy()
    fights = fights_table()[fights_table()["diagnostico_tatico"]].copy()
    if phase != "todas":
        selected_deaths = selected_deaths[selected_deaths["fase"] == phase]
        fights = fights[fights["fase"] == phase]
    deaths_with_allies = with_solo_flag(selected_deaths, solo_distance)
    deaths_with_allies["aliado_perto"] = ~deaths_with_allies["isolada"]
    possible = fights[fights["troca_possivel"] == TRADE_POSSIBLE]
    deaths_col, traded_col, isolated_col, missed_col = st.columns(4)
    deaths_col.metric("Mortes táticas", len(selected_deaths))
    traded_col.metric("Mortes trocadas", display_number(selected_deaths["trocada"].mean(), ".0%"))
    isolated_col.metric("Mortes isoladas (entre as que tinham aliado vivo)", display_number(deaths_with_allies["isolada"].mean(), ".0%"))
    missed_col.metric("Casos geométricos sem troca temporal", display_number(1 - possible["trocada"].mean(), ".0%"))

    st.subheader("1. Como troca temporal e proximidade se associam ao resultado?")
    st.caption("Diferenças observadas entre mortes com e sem a condição, comparando a mesma quantidade de aliados e inimigos vivos após a morte. Cada barra agrega essas situações pelo número de aliados. O mesmo round pode contribuir várias mortes; a comparação não isola efeito causal, reação ou qualidade da decisão. Células sem amostra suficiente são omitidas e identificadas.")
    for flag, label in [("trocada", "Troca temporal"), ("aliado_perto", "Aliado a menos do limite de isolamento")]:
        by_situation = win_rate_by_situation(deaths_with_allies, flag)
        if by_situation.empty:
            st.info(f"{label}: sem combinações com amostra suficiente neste recorte.")
            continue
        by_situation["aliados vivos no instante da morte"] = by_situation["situacao"].str.split("v").str[0].astype(int)
        by_allies = (by_situation["diferenca"] * by_situation["mortes"]).groupby([by_situation["aliados vivos no instante da morte"], by_situation["lado"]]).sum() / by_situation.groupby(["aliados vivos no instante da morte", "lado"])["mortes"].sum()
        st.markdown(f"**{label}**")
        st.altair_chart(grouped_bar_chart(by_allies.unstack("lado").rename_axis(index="aliados da vítima vivos no instante da morte"), [ATTACK_COLOR, DEFENSE_COLOR], "diferença na vitória", "+.0%", height=260), width="stretch")
        with st.expander(f"Números de cada situação (aliados x inimigos vivos): {label.lower()}"):
            st.dataframe(by_situation.drop(columns=["aliados vivos no instante da morte"]), hide_index=True, width="content")

    st.subheader("2. Quando distância e direção eram compatíveis, houve troca temporal?")
    trade_table = trade_possibility_summary(fights, ["lado"]).rename(index={TRADE_POSSIBLE: "proximidade e direção compatíveis", "aliado em alcance olhando para outro lado": "aliado perto, olhando para outro lado", "sem aliado em alcance": "nenhum aliado perto"}, level="troca_possivel")
    traded_column, won_column = st.columns(2)
    traded_column.markdown("**Quantas mortes foram trocadas**, considerando se algum aliado da vítima estava a menos de 20 m do inimigo que a matou e olhando para ele")
    traded_column.altair_chart(rate_chart(trade_table, "troca_possivel", "trocada", "mortes", "% de mortes trocadas", group_column="lado", group_colors=SIDE_COLORS), width="stretch")
    won_column.markdown("**Quantos rounds a equipe da vítima venceu**, nas mesmas três situações")
    won_column.altair_chart(rate_chart(trade_table, "troca_possivel", "venceu_round", "mortes", "% de rounds vencidos pela equipe da vítima", group_column="lado", group_colors=SIDE_COLORS), width="stretch")

    st.subheader("3. A que distância do aliado mais próximo o jogador morreu?")
    st.caption("Mortes agrupadas pela distância até o aliado vivo mais próximo, em unidades do jogo (100 unidades são cerca de 1 metro). Troca temporal: quantas foram trocadas. Equipe venceu o round: quantos desses rounds a equipe da vítima ainda venceu.")
    for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
        side_deaths = deaths_with_allies[deaths_with_allies["lado"] == side]
        side_column.markdown(f"**Jogador que morreu estava {SIDE_PHRASES[side]}**")
        side_column.altair_chart(grouped_bar_chart(summary_by_distance_band(side_deaths)[["fracao_trocadas", "venceu_round"]].rename(columns={"fracao_trocadas": "morte trocada", "venceu_round": "equipe venceu o round"}).rename_axis(index="distância até o aliado mais próximo (unidades do jogo)"), [TRADE_COLOR, WON_COLOR], "% das mortes"), width="stretch")
    with st.expander("Números por lado e resultado do round, e o primeiro abate separado em isolado ou trocado"):
        st.dataframe(summary_by_round_outcome(deaths_with_allies, ["lado"]).rename(index=ROUND_OUTCOME_LABELS, level="venceu_round"), width="content")
        for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
            first_deaths = first_death_summary(deaths_with_allies[deaths_with_allies["lado"] == side]).reset_index()
            first_deaths["isolada"] = first_deaths["isolada"].map({False: "acompanhada", True: "isolada"})
            first_deaths["trocada"] = first_deaths["trocada"].map({False: "não trocada", True: "trocada"})
            side_column.markdown(f"**Primeira morte do round, jogador que morreu estava {SIDE_PHRASES[side]}**")
            side_column.dataframe(first_deaths, hide_index=True, width="content")

    st.subheader("4. Onde estavam os aliados, e a morte foi em área própria ou do adversário?")
    st.markdown("""
À esquerda, onde estavam os aliados vivos no momento da morte.

- **Em grupo.** Pelo menos um aliado dentro do limite de isolamento.
- **Separado do grupo.** Nenhum aliado perto e pelo menos dois aliados na mesma grande região; não identifica flanqueamento nem garante proximidade entre eles.
- **Isolado.** Nenhum aliado perto, sem configuração de grupo identificada.

À direita, a ocupação observada nos primeiros confrontos até 20 segundos. A referência usa um snapshot por round e inclui as vítimas; não mede posição no início de todos os rounds nem identifica holds ou pushes.

- **Própria.** 65% ou mais dos jogadores ali são do mesmo lado da vítima.
- **Do adversário.** 35% ou menos.
- **Disputada.** Entre os dois.
""")
    context_column, territory_column = st.columns(2)
    context_column.markdown("**Quantos rounds a equipe venceu**, conforme onde estavam os aliados")
    context_column.altair_chart(rate_chart(context_summary(deaths_with_allies, ["lado"]).rename(index={"flanco": "separado do grupo"}, level="contexto"), "contexto", "venceu_round", "mortes", "% de rounds vencidos pela equipe da vítima", group_column="lado", group_colors=SIDE_COLORS, order=["em grupo", "separado do grupo", "isolado", "último vivo"]), width="stretch")
    territory_column.markdown("**Quantos rounds a equipe venceu**, conforme de quem é a região")
    territory_column.altair_chart(rate_chart(territory_summary(deaths_with_allies[deaths_with_allies["territorio"] != "?"], ["lado"]), "territorio", "venceu_round", "mortes", "% de rounds vencidos pela equipe da vítima", group_column="lado", group_colors=SIDE_COLORS, order=["próprio", "disputado", "do adversário"]), width="stretch")
    with st.expander("Números de posição dos aliados e de região, e o isolamento separado por função do agente"):
        st.dataframe(context_summary(deaths_with_allies, ["lado"]).rename(index={"flanco": "separado do grupo"}, level="contexto"), width="content")
        st.dataframe(territory_summary(deaths_with_allies, ["lado"]), width="content")
        st.markdown("**Por função do agente.** Acima do esperado: taxa de vitória do round menos o esperado para a mesma quantidade de vivos. Custo do isolamento: essa mesma conta para mortes isoladas menos para mortes acompanhadas.")
        st.dataframe(death_cost_by_role(deaths_with_allies), width="content")

    st.subheader("5. Conversão da heurística geométrica em troca temporal, por equipe")
    st.caption("Só equipes com 150 ou mais mortes táticas. A heurística combina distância e direção, sem verificar linha de tiro ou viabilidade. A conversão mede abate adversário em até 5 s. Dano no autor é o agregado do round, sem comprovar reação no confronto.")
    named_fights = fights.assign(time_killer=fights["time_vitima"].map({"Blue": "Red", "Red": "Blue"}))
    named_fights = with_team_names(with_team_names(named_fights, "time_vitima"), "time_killer", "nome_killer")
    st.dataframe(team_summary(named_fights), width="stretch")

if active_section == "Colapso e estilo":
    st.markdown("Colapso foi definido como três jogadores da equipe morrendo em até 10 segundos sem que a equipe mate ninguém nesse intervalo. Execução rápida é quando a spike é plantada em até 40 s, default quando é plantada depois disso, sem plant quando o round acabou antes de plantar. Contato cedo é quando o primeiro abate do round aconteceu em até 20 s. Por fim, placar é quem estava na frente antes do round começar.")
    styles = round_styles_table()
    styles = styles[styles["match_id"].isin(selected_ids) & (styles["lado"] != "?")]
    rounds_col, collapse_col, fast_col = st.columns(3)
    rounds_col.metric("Rounds contados (um por equipe)", len(styles))
    collapse_col.metric("Rounds com colapso", display_number(styles["colapso"].mean(), ".0%"))
    fast_col.metric("Rounds de ataque com plant até 40 s", f"{(styles.loc[styles['lado'] == 'ataque', 'estilo'] == 'execução rápida').mean():.0%}")

    st.subheader("1. Colapso: frequência e associação com o resultado")
    by_side = collapse_summary(styles, ["lado"])
    side_column, map_column = st.columns([2, 3])
    side_column.markdown("**Parte dos rounds com colapso**, em cada lado")
    side_column.altair_chart(rate_chart(by_side, "lado", "colapsos", "rounds", "% dos rounds com colapso", group_column="lado", group_colors=SIDE_COLORS, height=140), width="stretch")
    side_column.markdown("**Quantos rounds a equipe vence** quando colapsa (quadrado) e quando não colapsa (círculo)")
    side_column.altair_chart(dumbbell_chart(by_side, "lado", "venceu_com_colapso", "venceu_sem_colapso", "com colapso", "sem colapso", "% de rounds vencidos", count_column="rounds", left_color=LOST_COLOR), width="stretch")
    map_column.markdown("**Parte dos rounds com colapso em cada mapa**, por lado")
    by_map_side = collapse_summary(styles, ["mapa", "lado"]).rename(index=map_name_by_internal, level="mapa").sort_values("rounds", ascending=False)
    map_column.altair_chart(rate_chart(by_map_side, "mapa", "colapsos", "rounds", "% dos rounds com colapso", group_column="lado", group_colors=SIDE_COLORS), width="stretch")
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
        map_collapses = styles[(styles["mapa"] == collapse_internal) & styles["colapso"]]
        map_pre_plant = map_collapses["fase_colapso"].eq("pré-plant").mean()
        mixed_count = int(map_collapses["regiao_colapso"].eq("múltiplas regiões").sum())
        st.caption(f"Colapsos em múltiplas regiões não recebem marcador único: {mixed_count}. A tabela de estilo preserva esses casos.")
        st.caption(f"Cada círculo é uma região do mapa, só regiões com 5 ou mais colapsos. O tamanho mostra quantos colapsos aconteceram ali, enquanto a cor e a forma mostram quando, com círculo sendo antes do plant e quadrado depois do plant, em relação à média do mapa ({map_pre_plant:.0%} antes do plant).")
        for side_column, side in zip(st.columns(2), ["ataque", "defesa"]):
            side_regions = regions[regions["lado"] == side].set_index("regiao_colapso")
            side_column.markdown(f"**Colapsos da equipe {SIDE_PHRASES[side].replace('no ', 'de ').replace('na ', 'de ')}** ({int(side_regions['colapsos'].sum())} colapsos)")
            if side_regions.empty:
                side_column.info("Sem colapsos com volume neste lado.")
            else:
                side_column.pyplot(draw_rate_markers(collapse_map_meta, side_regions, "colapsos", "pre_plant", map_pre_plant, "parte dos colapsos antes do plant", label_min_count=10**9, size_per_unit=6), alt=f"Colapsos na {side}; contagens por região disponíveis na tabela.", width="stretch")
        with st.expander("Números por região"):
            st.dataframe(regions.drop(columns=["x", "y"]), hide_index=True, width="content")

    st.subheader("2. Ritmo do ataque: o resultado difere conforme o tempo observado do plant? E fazer contato cedo?")
    attack_styles, contact = style_summary(styles)
    style_column, contact_column = st.columns(2)
    style_column.markdown("**Quantos rounds o ataque vence** conforme o ritmo")
    style_column.altair_chart(rate_chart(attack_styles, "estilo", "venceu", "rounds", "% de rounds vencidos pelo ataque", order=STYLE_ORDER, height=140), width="stretch")
    contact_column.markdown("**Quantos rounds cada lado vence** quando o primeiro abate sai até 20 s (contato cedo) ou depois (contato tarde)")
    contact_column.altair_chart(rate_chart(contact, "contato", "venceu", "rounds", "% de rounds vencidos", group_column="lado", group_colors=SIDE_COLORS, height=140), width="stretch")

    st.subheader("3. A equipe muda o ritmo quando está perdendo?")
    shares, wins, counts = style_by_score(styles)
    shares_column, wins_column = st.columns(2)
    shares_column.markdown("**Como os rounds de ataque se dividem entre os ritmos**, conforme o placar antes do round")
    shares_column.altair_chart(share_chart(shares, counts, STYLE_COLORS, "% dos rounds de ataque"), width="stretch")
    wins_column.markdown("**Parte dos rounds vencidos** em cada combinação de placar e ritmo")
    wins_column.dataframe(wins, width="content")

    st.subheader("4. Perfil de cada equipe (equipes com 40 ou mais rounds de ataque)")
    profiles = team_profiles(styles)
    st.altair_chart(team_scatter(profiles, "execução rápida", "vitoria_ataque", "rounds_ataque", "% dos rounds de ataque com plant até 40 s", "% de rounds de ataque vencidos"), width="stretch")
    with st.expander("Todos os números por equipe"):
        st.dataframe(profiles, width="stretch")

if active_section == "Economia":
    st.markdown("Loadout é o valor das armas e escudos dos cinco jogadores. Rounds normais são todos menos o pistol (rounds 1 e 13) e o segundo round de cada metade (2 e 14). Vitória esperada pelo dinheiro é a taxa de vitória normal para a diferença de loadout vista entre as equipes.")
    economy_rounds = rounds_table()[rounds_table()["match_id"].isin(selected_ids)]
    close_rounds = economy_rounds[economy_rounds["match_id"].isin(close_match_ids(economy_rounds))]
    fights = fights_table()[fights_table()["match_id"].isin(selected_ids)]

    st.subheader("1. Como o valor do equipamento se associa à vitória?")
    own_table, difference_table = win_rate_by_loadout(economy_rounds)
    difference_column, full_buy_column = st.columns(2)
    difference_column.markdown("**Diferença de loadout entre a equipe e o adversário.** Acima de zero, o equipamento inicial valia mais. (todos os rounds)")
    difference_column.altair_chart(rate_chart(difference_table, "faixa_diferenca", "vitoria", "rounds", "% de rounds vencidos"), width="stretch")
    full_buy_column.markdown("**Pelo loadout da equipe quando o adversário comprou tudo** (20 mil ou mais, rounds normais)")
    full_buy_column.altair_chart(rate_chart(versus_full_buy(economy_rounds), "faixa_loadout", "vitoria", "rounds", "% de rounds vencidos"), width="stretch")
    with st.expander("Números: ganho de vitória por 1.000 créditos a mais, loadout da equipe sem olhar o adversário, e o cruzamento loadout da equipe x loadout do adversário"):
        st.dataframe(versus_full_buy(economy_rounds), width="content")
        st.dataframe(own_table, width="content")
        rates, counts = win_rate_matrix(economy_rounds)
        st.altair_chart(heatmap_chart(rates, counts, "loadout do adversário", "loadout da equipe", "% de rounds vencidos"), width="stretch")

    st.subheader("2. Perder um round abala a equipe no round seguinte?")
    st.caption("Clutch/thrifty é uma cerimônia registrada, sem comprovar que o round era fácil. A referência econômica usa rounds normais da amostra selecionada. Resíduos pequenos não provam ausência de abalo. O recorte por placar final é descritivo e selecionado pelo resultado, sem controlar força de forma independente.")
    all_column, close_column = st.columns(2)
    all_column.markdown("**Todas as partidas**")
    previous_labels = {"perdeu round fácil (clutch ou thrifty do adversário)": "perdeu round fácil"}
    all_column.altair_chart(dumbbell_chart(after_previous_round(economy_rounds).rename(index=previous_labels), "anterior", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "venceu de fato", "% de rounds seguintes vencidos", count_column="rounds", x_domain=[0.2, 0.7]), width="stretch")
    close_column.markdown(f"**Só partidas equilibradas** (até 4 rounds de diferença no placar final, {close_rounds['match_id'].nunique()} partidas)")
    close_column.altair_chart(dumbbell_chart(after_previous_round(close_rounds).rename(index=previous_labels), "anterior", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "venceu de fato", "% de rounds seguintes vencidos", count_column="rounds", x_domain=[0.2, 0.7]), width="stretch")
    streak_all_column, streak_close_column = st.columns(2)
    streak_all_column.markdown("**Quantos rounds seguidos a equipe tinha perdido antes deste**, todas as partidas")
    streak_all_column.altair_chart(dumbbell_chart(after_streak(economy_rounds), "derrotas", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "venceu de fato", "% de rounds vencidos", count_column="rounds", x_domain=[0.2, 0.7]), width="stretch")
    streak_close_column.markdown("**Quantos rounds seguidos a equipe tinha perdido antes deste**, só partidas equilibradas")
    streak_close_column.altair_chart(dumbbell_chart(after_streak(close_rounds), "derrotas", "esperado_pelo_dinheiro", "vitoria", "esperado pelo dinheiro", "venceu de fato", "% de rounds vencidos", count_column="rounds", x_domain=[0.2, 0.7]), width="stretch")

    st.subheader("3. Ciclos após o pistol: equipamento e resultados observados")
    pistol_column, cycle_column = st.columns([1, 3])
    pistol_column.markdown("**Round pistol**, quantos cada lado vence")
    pistol_column.dataframe(pistol_by_side(economy_rounds), width="content")
    overall_cycle, cycle_by_side = second_round_cycle(economy_rounds)
    cycle_column.markdown("**Perdedor do pistol, por metade e equipamento no round seguinte.** As taxas e a soma usam somente ciclos completos com os três rounds observados. A tabela mostra disponibilidade e censura; não é uma recomendação de compra. Taxa prévia usa apenas rounds anteriores ao pistol, quando existentes.")
    cycle_column.altair_chart(grouped_bar_chart(overall_cycle[["vitoria_round_2", "vitoria_round_3", "vitoria_round_4"]].rename(columns={"vitoria_round_2": "round seguinte ao pistol", "vitoria_round_3": "segundo do ciclo", "vitoria_round_4": "terceiro do ciclo"}), [WON_COLOR, TRADE_COLOR, NEUTRAL_COLOR], "% de rounds vencidos na coorte completa"), width="stretch")
    with st.expander("Números dos rounds 2 a 4, no total e por lado"):
        st.dataframe(overall_cycle, width="stretch")
        st.dataframe(cycle_by_side, width="stretch")

    st.subheader("4. Equipamento da primeira vítima e sobreviventes de rounds perdidos")
    expensive_column, operator_column = st.columns(2)
    expensive_column.markdown("**Comparação quando o primeiro a morrer é o jogador com maior loadout da equipe**, em relação à taxa descritiva da equipe na partida.")
    expensive_column.dataframe(economic_first_death(fights, "mais_caro_do_time"), width="content")
    operator_column.markdown("**Quando o primeiro a morrer tinha um Operator**")
    operator_column.dataframe(economic_first_death(fights.assign(operator=fights["arma_vitima"] == "Operator"), "operator"), width="content")
    saves = save_effect(economy_rounds, fights).loc[0:4]
    saves = saves[saves["rounds"] >= 20]
    save_loadout_column, save_win_column = st.columns(2)
    save_loadout_column.markdown("**Valor do equipamento no round seguinte**, por sobreviventes; exclui fins de metade e transições de prorrogação. A associação não é preço causal de salvar um jogador.")
    save_loadout_column.bar_chart(saves["loadout_seguinte"], color=[WON_COLOR], y_label="loadout do round seguinte", x_label="sobreviventes")
    save_win_column.markdown("**Chance de vencer o round seguinte**, conforme quantos sobreviveram")
    save_win_column.altair_chart(rate_chart(saves, "sobreviventes", "venceu_seguinte", "rounds", "% de rounds seguintes vencidos", height=170), width="stretch")

    st.subheader("5. Sobreviventes e mortes pós-plant: descrição econômica")
    st.caption("Os arquivos não dizem quem caçou quem. As médias não estimam retorno de caçar; o gráfico de trocas observa apenas vitórias do ataque e não representa tentativas malsucedidas. Equipamento seguinte difere de dinheiro disponível e gasto.")
    ledger_column, exchange_column = st.columns(2)
    next_loadouts, next_counts = next_loadout_by_outcome(economy_rounds, fights)
    ledger_column.markdown("**Valor do equipamento no round seguinte**, conforme quantos sobreviveram, para quem venceu e para quem perdeu o round")
    ledger_column.altair_chart(grouped_bar_chart(next_loadouts.rename_axis(index="sobreviventes"), [WON_COLOR, LOST_COLOR], "loadout do round seguinte", ",.0f"), width="stretch")
    exchange = post_plant_exchange(plants_table()[plants_table()["match_id"].isin(selected_ids)], fights)
    exchange_column.markdown("**Parte das mortes depois do plant que são de atacantes**, por situação no plant (atacantes x defensores vivos), em rounds que o ataque venceu")
    exchange_column.altair_chart(rate_chart(exchange, "situacao", "parte_do_ataque", "mortes_pos_plant", "% das mortes depois do plant que são de atacantes", color=ATTACK_COLOR), width="stretch")
    with st.expander("Números por sobreviventes e por situação no plant"):
        st.dataframe(next_counts.rename(columns=lambda column: f"rounds, {column}"), width="content")
        st.dataframe(exchange, width="content")

if active_section == "Plant e defuse":
    st.markdown("A referência pelos vivos é a taxa observada na mesma situação numérica, dentro dos torneios e versões selecionados. O resíduo não é efeito causal da posição. Plants após eliminação ou em rounds encerrados pelo tempo ficam fora das taxas táticas.")
    selected_plants = plants_table()[plants_table()["match_id"].isin(selected_ids)]
    plants_col, defuse_col, time_col = st.columns(3)
    plants_col.metric("Rounds com spike plantada", len(selected_plants))
    defuse_col.metric("Desarmados pela defesa", display_number(selected_plants["defusada"].mean(), ".1%"))
    time_col.metric("Segundo típico do plant (mediana)", display_number(selected_plants["segundos_plant"].median(), ".0f", " s"))

    st.subheader("1. Quantos estão vivos no momento do plant é o que mais decide")
    rates, counts = situation_matrix(selected_plants)
    st.altair_chart(heatmap_chart(rates, counts, "defensores vivos no momento do plant", "atacantes vivos no momento do plant", "% de spikes desarmadas"), width="stretch")

    st.subheader("2. Taxa de desarme por tempo de plant e site")
    time_column, site_column = st.columns(2)
    time_column.markdown("**Pelo segundo em que a spike foi plantada**")
    by_time = summary_by_plant_time(selected_plants)
    time_column.altair_chart(dumbbell_chart(by_time[by_time["plants"] >= 20], "faixa_tempo", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "desarmado de fato", "% de spikes desarmadas", count_column="plants", x_domain=[0, 0.6]), width="stretch")
    by_site = summary_by_site(selected_plants).rename(index=map_name_by_internal, level="mapa")
    by_site_named = by_site[by_site["plants"] >= 100].reset_index()
    by_site_named["mapa_site"] = by_site_named["mapa"] + " " + by_site_named["site"]
    site_column.markdown("**Por mapa e site**, sites com 100 ou mais plants")
    site_column.altair_chart(dumbbell_chart(by_site_named.set_index("mapa_site"), "mapa_site", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "desarmado de fato", "% de spikes desarmadas", count_column="plants", x_domain=[0, 0.6]), width="stretch")
    with st.expander("Números por mapa e site"):
        st.dataframe(by_site, width="content")

    st.subheader("3. Onde a spike é plantada, e quais posições a defesa desarma mais")
    plant_map_internal, plant_map_meta = map_selector("Mapa", selected_plants["mapa"].value_counts().index, "plant_map")
    if plant_map_meta is None:
        st.info("Este mapa não tem imagem disponível.")
    else:
        cells = cells_for_map(selected_plants, plant_map_internal)
        map_defuse = selected_plants[selected_plants["mapa"] == plant_map_internal]["defusada"].mean()
        st.caption("Cada marca junta os plants feitos num quadrado de cerca de 4 metros, só quadrados com 5 ou mais plants, com uma imagem por site. Tamanho da bola é maior de acordo com a quantidade de plants. Cor e forma mostram quantos foram desarmados, em relação à média do mapa")
        sites = sorted(cells["site"].unique())
        if not sites:
            st.info("Há plants neste mapa, mas nenhuma célula tem cinco ou mais observações no recorte.")
        for site_column, site in zip(st.columns(len(sites)) if sites else [], sites):
            site_cells = cells[cells["site"] == site]
            site_column.markdown(f"**Site {site}** ({int(site_cells['plants'].sum())} plants nos quadrados mostrados)")
            site_column.pyplot(draw_rate_markers(plant_map_meta, site_cells, "plants", "defuse", map_defuse, "taxa bruta de defuse", label_min_count=10**9, size_per_unit=3, zoom_padding=90), alt=f"Plants no site {site}; coordenadas, taxas brutas e referência pelos vivos na tabela.", width="stretch")
        with st.expander("Números de cada quadrado"):
            st.dataframe(cells[["site", "plants", "defuse", "esperado_pelos_vivos", "acima_do_esperado"]], width="content")

    st.subheader("4. Como as medidas de posição se associam ao desarme? E como a defesa retoma o site?")
    st.caption("No instante do plant válido, comparado com a referência pelos vivos. Atacantes até 15 m é uma distância radial, sem comprovar presença no site. Olhar oposto à spike não comprova vigiar entradas ou ter linha de tiro. A distância da defesa usa a mediana correta, incluindo a média dos dois valores centrais nos casos pares.")
    selected_setups = setups_table()[setups_table()["match_id"].isin(selected_ids)]
    on_site_column, watching_column, defense_column = st.columns(3)
    on_site_column.markdown("**Atacantes a menos de 15 m da spike**")
    on_site_column.altair_chart(dumbbell_chart(defuse_by(selected_setups, "atacantes_no_site"), "atacantes_no_site", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "desarmado de fato", "% de spikes desarmadas", count_column="plants", x_domain=[0, 0.6]), width="stretch")
    watching_column.markdown("**Parte dos aliados com olhar oposto à spike**")
    watching_column.altair_chart(dumbbell_chart(defuse_by(selected_setups, watching_bands(selected_setups)), "fracao_olhar_oposto_spike", "esperado_pelos_vivos", "defuse", "referência pelos vivos", "desarmado de fato", "% de spikes desarmadas", count_column="plants", x_domain=[0, 0.6]), width="stretch")
    defense_column.markdown("**Distância da defesa até a spike no momento do plant**")
    defense_column.altair_chart(dumbbell_chart(defuse_by(selected_setups, "faixa_defesa"), "faixa_defesa", "esperado_pelos_vivos", "defuse", "esperado pelos vivos", "desarmado de fato", "% de spikes desarmadas", count_column="plants", x_domain=[0, 0.6]), width="stretch")
    st.markdown("**Quando a defesa desarmou, quantos atacantes ainda estavam vivos e a que distância da spike estava o mais próximo**")
    st.dataframe(retake_summary(selected_setups), width="content")

if active_section == "Partida":
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
    events = round_events(round_result, team_by_puuid)
    map_meta = maps_by_url().get(match["matchInfo"]["mapId"])
    if map_meta is None:
        st.info("Este mapa não tem imagem disponível.")
    elif not events:
        st.info("Este round não tem abate, plant nem desarme, então não há posição registrada.")
    else:
        event_index = st.slider("Momento", 0, len(events) - 1, 0, format="evento %d") if len(events) > 1 else 0
        st.caption(describe_event(events[event_index], name_by_puuid, round_result))
        map_column, _ = st.columns([4, 1])
        map_column.pyplot(draw_round_map(map_meta, events, event_index, selected_puuid, team_by_puuid, name_by_puuid), alt=describe_event(events[event_index], name_by_puuid, round_result), width="stretch")
        st.dataframe(event_position_table(events[event_index], name_by_puuid, team_by_puuid), hide_index=True, width="stretch")
        st.caption("Snapshots dos eventos; linhas ligam posições registradas e não indicam o caminho efetivamente percorrido. Eventos após decisão são identificados no texto.")

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

if active_section == "Ferramenta proposta":
    st.title("Indicadores e estados da partida")
    st.markdown("Explore ocorrências por equipe e jogador e consulte referências empíricas para os estados do round. As associações não são somadas como pontos nem atribuídas como contribuição causal.")
    if st.button("Sortear partida, round e jogador"):
        random_match = selected_matches.sample(1).iloc[0]
        random_loaded = load_match(Path(random_match["caminho"]))
        st.session_state["pos_match"] = random_match["arquivo"]
        st.session_state["pos_round"] = int(pd.Series(range(len(random_loaded["roundResults"]))).sample(1).iloc[0])
        st.session_state["pos_player"] = pd.Series([p["puuid"] for p in random_loaded["players"] if not p["isObserver"]]).sample(1).iloc[0]
    match_files = selected_matches["arquivo"].tolist()
    if st.session_state.get("pos_match") not in match_files:
        st.session_state.pop("pos_match", None)
    selector_columns = st.columns(3)
    post_file = selector_columns[0].selectbox("Partida", match_files, key="pos_match")
    post_match_row = selected_matches[selected_matches["arquivo"] == post_file].iloc[0]
    post_match = load_match(Path(post_match_row["caminho"]))
    post_names = {p["puuid"]: f'{p["gameName"]}#{p["tagLine"]}' for p in post_match["players"]}
    post_teams = {p["puuid"]: p["teamId"] for p in post_match["players"]}
    post_puuids = [p["puuid"] for p in post_match["players"] if not p["isObserver"]]
    if st.session_state.get("pos_round") not in range(len(post_match["roundResults"])):
        st.session_state.pop("pos_round", None)
    if st.session_state.get("pos_player") not in post_puuids:
        st.session_state.pop("pos_player", None)
    post_round_index = selector_columns[1].selectbox("Round", range(len(post_match["roundResults"])), format_func=lambda i: f"Round {i + 1}", key="pos_round")
    post_puuid = selector_columns[2].selectbox("Jogador", post_puuids, format_func=lambda puuid: f"{post_names[puuid]} ({post_teams[puuid]})", key="pos_player")
    post_round = post_match["roundResults"][post_round_index]
    post_team = post_teams[post_puuid]
    post_events = round_events(post_round, post_teams)
    post_map_meta = maps_by_url().get(post_match["matchInfo"]["mapId"])
    st.caption(f'{post_match_row["torneio"]} · {post_match_row["mapa"]} · Blue {post_match_row["rounds_blue"]} × {post_match_row["rounds_red"]} Red')
    view = st.radio("Visualização", ["Ocorrências e associações", "Referência por estado"], horizontal=True)

    if view == "Ocorrências e associações":
        flagged_deaths, flagged_rounds = factor_tables()
        associations = {}
        st.subheader("Ocorrências na partida")
        st.caption("Contagens podem se sobrepor. Não há saldo ou soma de probabilidade por jogador.")
        st.dataframe(match_team_summary(flagged_rounds, post_match_row["match_id"], associations).T, width="stretch")
        st.dataframe(match_player_summary(post_match, flagged_deaths, associations), width="stretch")
        with st.expander("Indicadores por round"):
            st.dataframe(match_timeline(flagged_rounds, post_match_row["match_id"], associations), width="stretch")
        st.subheader("Ocorrências do jogador no round selecionado")
        post_round_deaths = flagged_deaths[(flagged_deaths["match_id"] == post_match_row["match_id"]) & (flagged_deaths["round"] == post_round_index + 1)]
        decisions = player_decisions(post_events, post_teams, post_puuid, post_round_deaths, associations, name_of=post_names.get)
        if not decisions:
            st.info("Nenhum dos indicadores desta lista foi observado para o jogador neste round.")
        for decision in decisions:
            event = post_events[decision["evento"]]
            st.markdown(f'**{decision["fator"]}**. {decision["detalhe"]}.')
            st.caption(describe_event(event, post_names, post_round))
            if post_map_meta is not None:
                st.pyplot(draw_round_map(post_map_meta, post_events, decision["evento"], post_puuid, post_teams, post_names), alt=f"Posições registradas: {describe_event(event, post_names, post_round)}", width="stretch")
            st.dataframe(event_position_table(event, post_names, post_teams), hide_index=True, width="stretch")

        association_panel = st.expander("Associações históricas da amostra selecionada", on_change="rerun", key="association_panel")
        if association_panel.open:
            with association_panel:
                ranking, good_ranking = association_tables(DATA_SIGNATURE, SELECTED_IDS)
                st.caption("Comparação exploratória da taxa com e sem cada indicador, com reamostragem por partida. Não é efeito causal. Indicadores de round e de morte são apresentados separadamente; mortes ponderam os rounds pelo número de eventos.")
                combined = pd.concat([ranking, good_ranking], ignore_index=True).drop_duplicates("fator")
                for unit, table in combined.groupby("unidade", sort=False):
                    st.markdown(f"**{unit}**")
                    st.dataframe(table.sort_values("diferenca"), hide_index=True, width="stretch", column_config={
                        "diferenca": st.column_config.NumberColumn("Diferença observada", format="%+.3f"),
                        "ic_baixo": st.column_config.NumberColumn("IC inferior", format="%+.3f"),
                        "ic_alto": st.column_config.NumberColumn("IC superior", format="%+.3f")})

    else:
        st.subheader("Referência empírica fora da partida selecionada")
        st.caption("Taxas observadas em outras partidas da amostra selecionada, no mesmo contexto de vivos, fase, equipamento e faixa de tempo. Não são probabilidades calibradas nem crédito de quem agiu. Sem suporte suficiente, o valor fica indisponível; não se troca de população para preencher lacunas.")
        state_table, _ = state_tables(DATA_SIGNATURE, SELECTED_IDS, post_match_row["match_id"])
        attacking_by_round = {r["roundNum"] + 1: attacking_team(r) for r in post_match["roundResults"]}
        attack_rows = rounds_table()[(rounds_table()["match_id"] == post_match_row["match_id"]) & (rounds_table()["lado"] == "ataque")]
        start_by_round = {row.round: {"faixa_diferenca": str(row.faixa_diferenca)} for row in attack_rows.itertuples()}
        selected_round_match = dict(post_match, roundResults=[post_round])
        round_added = match_win_added(selected_round_match, attacking_by_round, state_table, start_by_round)
        if round_added.empty:
            st.info("O round não tem estados observáveis para a referência.")
        else:
            round_added = round_added.copy()
            round_added["descricao"] = [describe_event(post_events[int(row.evento)], post_names, post_round) if 0 <= row.evento < len(post_events) else "resultado final observado" for row in round_added.itertuples()]
            round_added["passo"] = range(1, len(round_added) + 1)
            supported = round_added["depois_ataque"].notna()
            st.metric("Eventos com referência disponível", f"{int(supported.sum())} / {len(round_added)}")
            if supported.any():
                base = alt.Chart(round_added).encode(x=alt.X("passo:O", title="evento"))
                points = base.mark_point(size=100, filled=True, color=ATTACK_COLOR).encode(
                    y=alt.Y("depois_ataque:Q", title="taxa observada de vitória do ataque", axis=alt.Axis(format=".0%"), scale=alt.Scale(domain=[0, 1])),
                    tooltip=["descricao", "estado", "n_depois", "partidas_depois", "faixa_diferenca", "faixa_tempo", alt.Tooltip("depois_ataque:Q", format=".1%")])
                intervals = base.mark_rule(color="#444444").encode(y="ic_baixo:Q", y2="ic_alto:Q")
                st.altair_chart((intervals + points).properties(height=300), width="stretch")
            else:
                st.info("Nenhum estado deste round tem suporte suficiente nas outras partidas do recorte. Amplie torneios/versões para consultar uma referência mais abrangente.")
            listing = round_added[[c for c in ["descricao", "tipo", "estado", "fase", "faixa_diferenca", "faixa_tempo", "antes_ataque", "depois_ataque", "n_depois", "partidas_depois", "ic_baixo", "ic_alto", "observacao"] if c in round_added]]
            st.dataframe(listing, hide_index=True, width="stretch")
            st.caption(f'Resultado factual: {post_round["winningTeam"]} venceu por {post_round["roundResult"]}. Esse resultado não é apresentado como uma taxa empírica nem pontuado para o autor do último evento.')

if active_section == "Previsão":
    st.markdown("Associações dentro da partida, avaliação retrospectiva em outras partidas e previsão temporal são análises diferentes. Todos os números seguem a amostra selecionada. A comparação com histórico usa os mesmos jogos e regra de desempate explícita; resultados descritivos não validam contribuição causal.")
    prediction = prediction_tables()
    chance_median, chance_95 = prediction["acaso"]
    st.subheader("1. Associação dentro da partida já observada")
    st.caption(f"A equipe com a medida melhor na própria partida foi a vencedora? Para comparar, embaralhando quem venceu ao acaso o acerto típico é {chance_median:.1%} e chega a {chance_95:.1%} em 5% das vezes.")
    st.dataframe(prediction["dentro"], hide_index=True, width="content")
    st.subheader("2. Avaliação retrospectiva usando outras partidas do campeonato")
    st.caption("Inclui jogos posteriores: esta seção não simula uma previsão antes do jogo. Só equipes com histórico suficiente; consulte o número de jogos e intervalos em cada linha.")
    st.dataframe(prediction["outras"], hide_index=True, width="content")
    st.subheader("3. Previsão usando só partidas anteriores no calendário")
    st.dataframe(prediction["anteriores"], hide_index=True, width="content")
    st.subheader("4. Ranking de cada campeonato: perfil combinado contra taxa de vitória")
    st.caption("Associação descritiva no próprio campeonato, sem validação prospectiva. Equipes com 3 ou mais partidas. Perfil: soma das medidas, cada uma padronizada e com o sinal de bom ou ruim. Spearman: quanto a ordem das equipes pelo perfil coincide com a ordem pela taxa de vitória (1 é igual, 0 é sem relação).")
    for tournament_column, (tournament, table) in zip(st.columns(2) + st.columns(2), prediction["rankings"].items()):
        tournament_column.markdown(f"**{tournament}** (Spearman {table['spearman'].iloc[0]})")
        tournament_column.dataframe(table.drop(columns=["spearman"]), width="stretch")

if active_section == "Conclusões":
    st.caption("Documento recalculado para a amostra padrão descrita no próprio texto. Os filtros da interface não alteram este retrato; consulte as outras seções para os números do recorte atual.")
    st.markdown((Path(__file__).parent / "CONCLUSOES.md").read_text(encoding="utf-8"))

if active_section == "Exploração":
    st.markdown("Fora do escopo de decisões de equipe, guardado como exploração: a arma e a distância de cada morte, se a vítima reagiu, números individuais de combate e o dicionário de campos dos arquivos.")
    fights = fights_table()[fights_table()["match_id"].isin(selected_ids)]
    st.subheader("Arma da vítima e distância de quem matou")
    summary_column, matrix_column = st.columns(2)
    summary_column.dataframe(distance_summary(fights), width="content")
    matrix_column.dataframe(distance_matrix(fights), width="content")
    name_by_puuid = players.drop_duplicates("puuid").set_index("puuid")["jogador"]
    short_table, sniper_table = player_range_discipline(fights, name_by_puuid)
    short_column, sniper_column = st.columns(2)
    short_column.markdown("**Por jogador: mortes com SMG ou shotgun inicial a longa distância (25 m+)**, 10 ou mais mortes")
    short_column.dataframe(short_table, hide_index=True, width="content")
    sniper_column.markdown("**Por jogador: mortes com sniper inicial a curta distância (até 10 m)**, 10 ou mais mortes")
    sniper_column.dataframe(sniper_table, hide_index=True, width="content")

    st.subheader("Dano recebido e causado ao longo do round")
    st.caption("Categorias pelo dano recebido de adversários ao longo do round, independentemente de assistência. Não identificam foco simultâneo ou reação naquela luta. A arma atribuída à vítima é o equipamento inicial.")
    st.dataframe(fight_class_summary(fights, ["lado"]), width="content")

    st.subheader("Jogadores: abates, mortes e pontuação")
    st.dataframe(players_summary(selected_players), hide_index=True)

    st.subheader("Campos dos arquivos de partida")
    relevant_fields, irrelevant_fields = build_field_tables(DATA_SIGNATURE, SELECTED_IDS)
    field_filter = st.text_input("Filtrar campo")
    st.dataframe(relevant_fields[relevant_fields["campo"].str.contains(field_filter, regex=False)], hide_index=True)
    with st.container(border=True):
        st.markdown("**Campos sem informação.** Têm o mesmo valor em todas as partidas.")
        st.dataframe(irrelevant_fields.drop(columns=["distintos"]).rename(columns={"mais_frequentes": "valor"}), hide_index=True)


if active_section == "Qualidade dos dados":
    st.title("Cobertura e qualidade dos dados")
    st.caption("A inspeção preserva os arquivos brutos. Partidas atípicas ficam fora das análises por padrão e podem ser incluídas no controle lateral, sem presumir a causa da anomalia.")
    st.caption("Inventário completo dos arquivos locais, incluindo partidas sinalizadas. A cobertura do recorte aparece abaixo.")
    st.json(quality)
    from fights import fight_coverage
    st.write({"cobertura_de_lutas_no_recorte": fight_coverage(fights_table())})
    st.markdown("**Regras de análise**")
    st.markdown("Aberturas e trocas exigem abates entre adversários. Eventos após decisão observável são preservados no replay/economia e retirados dos diagnósticos táticos. Plants após eliminação ou em rounds encerrados pelo tempo não entram nas taxas táticas. Empates de abertura entre equipes não recebem um vencedor arbitrário. Snapshots ausentes e estados com suporte insuficiente permanecem indisponíveis.")
    with st.expander("Cobertura de mortes no recorte"):
        deaths = deaths_table()
        st.write({"mortes": len(deaths), "abates adversários": int(deaths.get("abate_adversario", pd.Series(dtype=bool)).sum()), "após decisão observável": int(deaths.get("apos_decisao", pd.Series(dtype=bool)).sum()), "abertura ambígua (eventos)": int(deaths.get("abertura_ambigua", pd.Series(dtype=bool)).sum())})
    st.caption(f"Assinatura dos dados e metadados: {DATA_SIGNATURE}")
