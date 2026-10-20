"""Gráficos reutilizáveis que recebem tabelas e preservam os dados de análise."""

import altair as alt
import pandas as pd

from valorant.analysis.agent_roles import with_interval
from valorant.ui.presentation import display_value, field_label

LOST_COLOR = "#ff7f0e"
WON_COLOR = "#1f77b4"
TRADE_COLOR = "#2ca02c"
ATTACK_COLOR = "#c0392b"
DEFENSE_COLOR = "#2a9d8f"
NEUTRAL_COLOR = "#7f7f7f"
SIDE_COLORS = {"ataque": ATTACK_COLOR, "defesa": DEFENSE_COLOR}
SIDE_PHRASES = {"ataque": "no ataque", "defesa": "na defesa"}
STYLE_COLORS = {
    "execução rápida": WON_COLOR,
    "default": TRADE_COLOR,
    "sem plant": LOST_COLOR,
    "plant excluído": NEUTRAL_COLOR,
}
ROUND_OUTCOME_LABELS = {False: "perdeu o round", True: "venceu o round"}
FIT_WIDTH = alt.AutoSizeParams(type="fit-x", contains="padding")
POINTS_LABEL_EXPRESSION = "format(datum.value * 100, '.0f') + ' pp'"


def _category_label(value):
    if isinstance(value, tuple):
        return ", ".join(_category_label(part) for part in value)
    return str(display_value(value))


def _series_label(value):
    return str(field_label(display_value(value)))


def _tooltip(column, data_type="N", *, title=None, number_format=None):
    data_type = {"N": "nominal", "Q": "quantitative", "O": "ordinal"}.get(data_type, data_type)
    options = {"field": column, "type": data_type, "title": title or field_label(column)}
    if number_format is not None:
        options["format"] = number_format
    return alt.Tooltip(**options)


def _point_difference(value):
    return f"{value * 100:+.1f} pp".replace(".", ",") if pd.notna(value) else "Sem dados"


def _note(text):
    return alt.TitleParams(text="", subtitle=text, anchor="start", subtitleColor="#555555")


def empty_chart(message="Sem amostra suficiente para este gráfico"):
    return (
        alt.Chart(pd.DataFrame({"aviso": [message]}))
        .mark_text(color="#444444", fontSize=13)
        .encode(text="aviso:N")
        .properties(height=100)
    )


def category_axis(column, order):
    return alt.Y(
        field=column,
        type="nominal",
        sort=order,
        title=None,
        axis=alt.Axis(labelOverlap=False, labelLimit=340),
    )


def rate_chart(
    table,
    category_column,
    rate_column,
    count_column,
    x_title,
    color=WON_COLOR,
    group_column=None,
    group_colors=None,
    order=None,
    height=None,
):
    """Taxas por grupo com contagem e intervalo de 95% de Wilson."""
    if table.empty:
        return empty_chart()
    data = with_interval(table.reset_index(), rate_column, count_column)
    data[category_column] = data[category_column].map(_category_label).astype(str)
    order = (
        [_category_label(value) for value in order]
        if order is not None
        else list(dict.fromkeys(data[category_column]))
    )
    tooltip = [
        _tooltip(category_column),
        _tooltip(count_column, "Q", number_format=",.0f"),
        _tooltip(rate_column, "Q", title=x_title, number_format=".1%"),
        _tooltip("ic95_baixo", "Q", number_format=".1%"),
        _tooltip("ic95_alto", "Q", number_format=".1%"),
    ]
    base = alt.Chart(data).encode(y=category_axis(category_column, order))
    if group_column:
        data[group_column] = data[group_column].map(_category_label).astype(str)
        groups = (
            [_category_label(group) for group in group_colors]
            if group_colors
            else list(dict.fromkeys(data[group_column]))
        )
        scale = (
            alt.Scale(domain=groups, range=list(group_colors.values()))
            if group_colors
            else alt.Scale(domain=groups)
        )
        base = base.encode(
            yOffset=alt.YOffset(field=group_column, type="nominal", sort=groups),
            color=alt.Color(
                field=group_column,
                type="nominal",
                scale=scale,
                title=field_label(group_column),
                legend=alt.Legend(orient="top", columns=1, labelLimit=500),
            ),
        )
        tooltip.append(_tooltip(group_column))
        bars = base.mark_bar()
    else:
        groups = []
        bars = base.mark_bar(color=color)
    base = base.encode(tooltip=tooltip)
    bars = bars.encode(
        x=alt.X(field=rate_column, type="quantitative", title=x_title, axis=alt.Axis(format=".0%")),
        tooltip=tooltip,
    )
    rules = base.mark_rule(strokeWidth=2).encode(
        x=alt.X("ic95_baixo:Q", title=x_title, axis=alt.Axis(format=".0%")),
        x2="ic95_alto:Q",
        color=alt.value("#4a4a4a"),
    )
    counts = data[count_column].map(
        lambda count: f"{count:,.0f}".replace(",", ".") if pd.notna(count) else "sem amostra"
    )
    data["rotulo_contagem"] = (
        counts if not group_column else data[group_column].str.cat(counts, sep=" ")
    )
    labels = base.mark_text(align="left", dx=4, fontSize=12).encode(
        x=alt.X("ic95_alto:Q", title=x_title, axis=alt.Axis(format=".0%")),
        text="rotulo_contagem:N",
        color=alt.value("#6b6b6b"),
    )
    rows = len(order) * (len(groups) if group_column else 1)
    return (bars + rules + labels).properties(
        height=height or max(120, 24 * rows + 40),
        autosize=FIT_WIDTH,
        title=_note("Traços mostram intervalos de 95% de Wilson."),
    )


def dumbbell_chart(
    table,
    category_column,
    left_column,
    right_column,
    left_label,
    right_label,
    x_title,
    count_column=None,
    left_color=NEUTRAL_COLOR,
    right_color=WON_COLOR,
    order=None,
    x_domain=None,
):
    """Compara duas taxas por grupo com cores e formas diferentes."""
    if table.empty:
        return empty_chart()
    data = table.reset_index()
    data[category_column] = data[category_column].map(_category_label).astype(str)
    labels = data[category_column]
    if count_column:
        labels = labels + " (" + data[count_column].astype(int).astype(str) + ")"
    data = data.assign(rotulo=labels)
    labels_by_category = dict(zip(data[category_column], data["rotulo"]))
    order = (
        [
            labels_by_category[_category_label(value)]
            for value in order
            if _category_label(value) in labels_by_category
        ]
        if order is not None
        else list(data["rotulo"])
    )
    left_label, right_label = _category_label(left_label), _category_label(right_label)
    id_columns = list(
        dict.fromkeys(["rotulo", category_column] + ([count_column] if count_column else []))
    )
    long = data.melt(
        id_vars=id_columns,
        value_vars=[left_column, right_column],
        var_name="medida",
        value_name="valor",
    ).replace({"medida": {left_column: left_label, right_column: right_label}})
    scale = alt.Scale(domain=x_domain) if x_domain is not None else alt.Undefined
    x = alt.X("valor:Q", title=x_title, scale=scale, axis=alt.Axis(format=".0%"))
    tooltip = [
        _tooltip(category_column),
        _tooltip("medida", title="Taxa comparada"),
        _tooltip("valor", "Q", title=x_title, number_format=".1%"),
    ]
    if count_column:
        tooltip.append(_tooltip(count_column, "Q", number_format=",.0f"))
    lines = (
        alt.Chart(data)
        .mark_rule(color="#b0b0b0", strokeWidth=2)
        .encode(
            y=category_axis("rotulo", order),
            x=alt.X(
                field=left_column,
                type="quantitative",
                title=x_title,
                scale=scale,
                axis=alt.Axis(format=".0%"),
            ),
            x2=alt.X2(field=right_column),
            tooltip=[
                _tooltip(category_column),
                _tooltip(left_column, "Q", title=left_label, number_format=".1%"),
                _tooltip(right_column, "Q", title=right_label, number_format=".1%"),
            ],
        )
    )
    points = (
        alt.Chart(long)
        .mark_point(size=110, opacity=1, filled=True)
        .encode(
            y=category_axis("rotulo", order),
            x=x,
            color=alt.Color(
                "medida:N",
                title=None,
                legend=alt.Legend(orient="top", columns=1, labelLimit=500),
                scale=alt.Scale(domain=[left_label, right_label], range=[left_color, right_color]),
            ),
            shape=alt.Shape(
                "medida:N",
                title=None,
                legend=alt.Legend(orient="top", columns=1, labelLimit=500),
                scale=alt.Scale(domain=[left_label, right_label], range=["square", "circle"]),
            ),
            tooltip=tooltip,
        )
    )
    return (lines + points).properties(height=max(120, 28 * len(data) + 40), autosize=FIT_WIDTH)


def heatmap_chart(rates, counts, x_title, y_title, color_title):
    """Taxa e número de casos em cada combinação de duas categorias."""
    if rates.empty or counts.empty:
        return empty_chart()
    rate_long = (
        rates.rename_axis(index="linha", columns="coluna").stack().rename("taxa").reset_index()
    )
    count_long = (
        counts.rename_axis(index="linha", columns="coluna").stack().rename("n").reset_index()
    )
    long = rate_long.merge(count_long, on=["linha", "coluna"])
    for column in ("linha", "coluna"):
        long[column] = long[column].map(display_value)
    long["rotulo"] = (
        long["taxa"].map(lambda rate: f"{rate:.0%}")
        + " ("
        + long["n"].astype(int).astype(str)
        + ")"
    )
    x = alt.X("coluna:O", title=x_title)
    y = alt.Y("linha:O", title=y_title, sort="descending")
    cells = (
        alt.Chart(long)
        .mark_rect()
        .encode(
            x=x,
            y=y,
            color=alt.Color(
                "taxa:Q",
                scale=alt.Scale(scheme="blues", domain=[0, 1]),
                title=color_title,
                legend=alt.Legend(format=".0%"),
            ),
            tooltip=[
                _tooltip("linha", title=y_title),
                _tooltip("coluna", title=x_title),
                _tooltip("taxa", "Q", title=color_title, number_format=".1%"),
                _tooltip("n", "Q", title="Casos nesta combinação", number_format=",.0f"),
            ],
        )
    )
    text = (
        alt.Chart(long)
        .mark_text(fontSize=11)
        .encode(
            x=x,
            y=y,
            text="rotulo:N",
            color=alt.condition("datum.taxa > 0.55", alt.value("white"), alt.value("#222222")),
        )
    )
    return (cells + text).properties(height=260, title=_note("Taxas e casos entre parênteses."))


def difference_heatmap(by_situation, side, color_title):
    """Diferença entre taxas por número de aliados e adversários vivos."""
    data = by_situation[by_situation["lado"] == side].copy()
    if data.empty:
        return empty_chart()
    data["aliados"] = data["situacao"].str.split("v").str[0].astype(int)
    data["inimigos"] = data["situacao"].str.split("v").str[1].astype(int)
    data["diferenca_rotulo"] = data["diferenca"].map(_point_difference)
    data["rotulo"] = data["diferenca_rotulo"] + " (" + data["mortes"].astype(str) + ")"
    x = alt.X("inimigos:O", title="Adversários vivos")
    y = alt.Y("aliados:O", title="Aliados vivos", sort="descending")
    cells = (
        alt.Chart(data)
        .mark_rect()
        .encode(
            x=x,
            y=y,
            color=alt.Color(
                "diferenca:Q",
                scale=alt.Scale(scheme="redblue", domain=[-0.4, 0.4]),
                title=color_title,
                legend=alt.Legend(labelExpr=POINTS_LABEL_EXPRESSION),
            ),
            tooltip=[
                _tooltip("aliados", "Q", title="Aliados vivos"),
                _tooltip("inimigos", "Q", title="Adversários vivos"),
                _tooltip("mortes", "Q", number_format=",.0f"),
                _tooltip("sem", "Q", number_format=".1%"),
                _tooltip("com", "Q", number_format=".1%"),
                _tooltip("diferenca_rotulo", title="Diferença em pontos percentuais"),
            ],
        )
    )
    text = (
        alt.Chart(data)
        .mark_text(fontSize=11)
        .encode(
            x=x,
            y=y,
            text="rotulo:N",
            color=alt.condition(
                "abs(datum.diferenca) > 0.25", alt.value("white"), alt.value("#222222")
            ),
        )
    )
    return (cells + text).properties(
        height=220,
        title=_note(["Diferença em pontos percentuais.", "Mortes contadas entre parênteses."]),
    )


def share_chart(shares, counts, part_colors, x_title):
    """Barras que somam 100%, com nomes e taxas escritos em cada parte."""
    if shares.empty:
        return empty_chart()
    category_title = field_label(shares.index.name) if shares.index.name else "Situação no placar"
    part_title = field_label(shares.columns.name) if shares.columns.name else "Tempo do plant"
    long = (
        shares.rename_axis(index="categoria", columns="parte")
        .stack()
        .rename("fracao")
        .reset_index()
    )
    long["casos"] = long["categoria"].map(lambda category: int(counts.get(category, 0)))
    parts = [_category_label(part) for part in part_colors]
    for column in ("categoria", "parte"):
        long[column] = long[column].map(_category_label).astype(str)
    long["rotulo"] = long["categoria"] + " (" + long["casos"].astype(str) + ")"
    long["parte_ordem"] = long["parte"].map(parts.index)
    long = long.sort_values(["rotulo", "parte_ordem"])
    long["fim"] = long.groupby("rotulo")["fracao"].cumsum()
    long["inicio"] = long["fim"] - long["fracao"]
    long["meio"] = (long["inicio"] + long["fim"]) / 2
    long["texto"] = long.apply(
        lambda row: f"{row['parte']} {row['fracao']:.0%}" if row["fracao"] >= 0.12 else "",
        axis=1,
    )
    y = category_axis("rotulo", list(dict.fromkeys(long["rotulo"])))
    bars = (
        alt.Chart(long)
        .mark_bar()
        .encode(
            y=y,
            x=alt.X("inicio:Q", title=x_title, axis=alt.Axis(format=".0%")),
            x2="fim:Q",
            color=alt.Color(
                "parte:N",
                scale=alt.Scale(domain=parts, range=list(part_colors.values())),
                sort=parts,
                title=part_title,
            ),
            tooltip=[
                _tooltip("categoria", title=category_title),
                _tooltip("parte", title=part_title),
                _tooltip("fracao", "Q", title="Parte dos rounds deste grupo", number_format=".1%"),
                _tooltip("casos", "Q", title="Rounds neste grupo", number_format=",.0f"),
            ],
        )
    )
    text = (
        alt.Chart(long)
        .mark_text(fontSize=12, color="white")
        .encode(y=y, x=alt.X("meio:Q", title=x_title, axis=alt.Axis(format=".0%")), text="texto:N")
    )
    return (bars + text).properties(
        height=max(120, 32 * long["rotulo"].nunique() + 40), autosize=FIT_WIDTH
    )


def grouped_bar_chart(wide, series_colors, x_title, value_format=".0%", height=None):
    """Compara séries com barras separadas e nomes junto dos valores."""
    if wide.empty:
        return empty_chart()
    wide = wide.copy()
    category_title = field_label(wide.index.name) if wide.index.name else "Grupo comparado"
    if isinstance(wide.index, pd.MultiIndex):
        category_title = (
            " e ".join(str(field_label(name)) for name in wide.index.names if name)
            or "Grupo comparado"
        )
        wide.index = wide.index.map(_category_label).astype(str)
    long = (
        wide.rename_axis(index="categoria", columns="serie").stack().rename("valor").reset_index()
    )
    long["categoria"] = long["categoria"].map(_category_label).astype(str)
    series = [_series_label(column) for column in wide.columns]
    long["serie"] = long["serie"].map(_series_label).astype(str)
    difference = value_format.startswith("+") and "%" in value_format
    if difference:
        long["valor_rotulo"] = long["valor"].map(_point_difference)
        axis = alt.Axis(labelExpr=POINTS_LABEL_EXPRESSION)
        value_tooltip = _tooltip("valor_rotulo", title="Diferença em pontos percentuais")
        x_title = f"{x_title} em pontos percentuais"
    else:
        long["valor_rotulo"] = long["valor"].map(lambda value: format(value, value_format))
        axis = alt.Axis(format=value_format)
        value_tooltip = _tooltip("valor", "Q", title=x_title, number_format=value_format)
    long["texto"] = long["serie"] + " " + long["valor_rotulo"]
    y = category_axis("categoria", list(dict.fromkeys(long["categoria"])))
    y.title = category_title
    base = alt.Chart(long).encode(
        y=y,
        yOffset=alt.YOffset("serie:N", sort=series),
        tooltip=[
            _tooltip("categoria", title=category_title),
            _tooltip("serie", title="Medida comparada"),
            value_tooltip,
        ],
    )
    bars = base.mark_bar().encode(
        x=alt.X("valor:Q", title=x_title, axis=axis),
        color=alt.Color(
            "serie:N",
            scale=alt.Scale(domain=series, range=list(series_colors)),
            title="Medida comparada",
            legend=alt.Legend(orient="top", columns=1, labelLimit=500),
        ),
    )
    labels = base.mark_text(align="left", dx=4, fontSize=12, color="#6b6b6b").encode(
        x=alt.X("valor:Q", title=x_title, axis=axis), text="texto:N"
    )
    return (bars + labels).properties(
        height=height or max(120, 22 * len(long) + 40), autosize=FIT_WIDTH
    )


def team_scatter(profiles, x_column, y_column, size_column, x_title, y_title):
    """Um ponto por equipe, com tamanho pelo número de rounds."""
    if profiles.empty:
        return empty_chart()
    data = profiles.reset_index()
    x = alt.X(field=x_column, type="quantitative", title=x_title, axis=alt.Axis(format=".0%"))
    y = alt.Y(
        field=y_column,
        type="quantitative",
        title=y_title,
        axis=alt.Axis(format=".0%"),
        scale=alt.Scale(zero=False),
    )
    points = (
        alt.Chart(data)
        .mark_circle(color=WON_COLOR, opacity=0.7)
        .encode(
            x=x,
            y=y,
            size=alt.Size(field=size_column, type="quantitative", title=field_label(size_column)),
            tooltip=[
                _tooltip("time"),
                _tooltip(size_column, "Q", number_format=",.0f"),
                _tooltip(x_column, "Q", title=x_title, number_format=".1%"),
                _tooltip(y_column, "Q", title=y_title, number_format=".1%"),
            ],
        )
    )
    labelled = data[data[size_column] >= data[size_column].quantile(0.5)]
    labels = (
        alt.Chart(labelled)
        .mark_text(align="left", dx=8, fontSize=12, color="#333333")
        .encode(x=x, y=y, text="time:N")
    )
    return (points + labels).properties(height=440)


def quantile_band_chart(per_round):
    """Mediana e faixas que contêm os 50% e 80% centrais dos tempos."""
    if per_round.empty:
        return empty_chart()
    base = alt.Chart(per_round.reset_index()).encode(x=alt.X("round:O", title=field_label("round")))
    tooltip = [_tooltip("round", "O"), _tooltip("rounds", "Q", number_format=",.0f")]
    tooltip += [
        _tooltip(column, "Q", title=f"{field_label(column)} em segundos", number_format=".1f")
        for column in ("p10", "p25", "mediana", "p75", "p90", "media", "desvio_padrao")
    ]
    wide_band = base.mark_area(opacity=0.15, color=NEUTRAL_COLOR).encode(
        y=alt.Y("p10:Q", title="Segundos até o primeiro abate"),
        y2="p90:Q",
        tooltip=tooltip,
    )
    narrow_band = base.mark_area(opacity=0.3, color=NEUTRAL_COLOR).encode(
        y=alt.Y("p25:Q", title="Segundos até o primeiro abate"),
        y2="p75:Q",
        tooltip=tooltip,
    )
    median_line = base.mark_line(color="#4a4a4a", point=True).encode(
        y=alt.Y("mediana:Q", title="Segundos até o primeiro abate"),
        tooltip=tooltip,
    )
    return (wide_band + narrow_band + median_line).properties(
        height=320,
        title=_note("Linha mediana e faixas centrais de 50% e 80%."),
    )


def opening_impact_chart(by_map):
    """Diferença na taxa de vitória conforme quem fez o primeiro abate."""
    if by_map.empty:
        return empty_chart()
    data = by_map.reset_index()
    data["rotulo"] = data["mapa"] + " (" + data["rounds"].astype(str) + ")"
    for column in ("impacto_da_abertura", "impacto_ic95_baixo", "impacto_ic95_alto"):
        data[f"{column}_rotulo"] = data[column].map(_point_difference)
    tooltip = [
        _tooltip("mapa"),
        _tooltip("rounds", "Q", number_format=",.0f"),
        _tooltip("ataque_vence_se_abre", "Q", number_format=".1%"),
        _tooltip("ataque_vence_se_defesa_abre", "Q", number_format=".1%"),
        _tooltip("impacto_da_abertura_rotulo", title="Diferença em pontos percentuais"),
        _tooltip("impacto_ic95_baixo_rotulo", title=field_label("impacto_ic95_baixo")),
        _tooltip("impacto_ic95_alto_rotulo", title=field_label("impacto_ic95_alto")),
    ]
    base = alt.Chart(data).encode(y=category_axis("rotulo", list(data["rotulo"])), tooltip=tooltip)
    x_title = "Diferença na vitória do ataque em pontos percentuais"
    bars = base.mark_bar(color=ATTACK_COLOR).encode(
        x=alt.X(
            "impacto_da_abertura:Q",
            title=x_title,
            axis=alt.Axis(labelExpr=POINTS_LABEL_EXPRESSION),
        ),
    )
    intervals = base.mark_rule(color="#4a4a4a", strokeWidth=2).encode(
        x=alt.X(
            "impacto_ic95_baixo:Q",
            title=x_title,
            axis=alt.Axis(labelExpr=POINTS_LABEL_EXPRESSION),
        ),
        x2="impacto_ic95_alto:Q",
    )
    return (bars + intervals).properties(
        height=30 * len(data) + 40,
        title=_note(
            [
                "Vitórias quando o ataque abre menos quando a defesa abre.",
                "Traços mostram intervalos de 95%.",
            ]
        ),
    )
