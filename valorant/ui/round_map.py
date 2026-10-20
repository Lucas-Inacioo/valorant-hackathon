"""Eventos do round e posições dos jogadores sobre o minimapa."""

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, TwoSlopeNorm
from matplotlib.patheffects import withStroke
from matplotlib.lines import Line2D
from PIL import Image

from valorant.data.metadata import game_to_image_fraction, minimap_file
from valorant.analysis.events import alive_puuids, is_enemy_kill

ALLY_COLOR = "#1f77b4"
ENEMY_COLOR = "#d62728"


def describe_event(event, name_by_puuid, round_result):
    seconds = f"{event['time_ms'] / 1000:.1f}".replace(".", ",")
    actor = name_by_puuid.get(event["actor"], "autor desconhecido")
    suffix = ", quando o round já estava decidido" if event.get("after_decision") else ""
    if event["kind"] == "kill":
        victim = name_by_puuid.get(event["victim"], "jogador desconhecido")
        damage_type = event.get("finishing", {}).get("damageType")
        if damage_type in {"Bomb", "Fall", "Crush"} or not event.get("actor"):
            action = {
                "Bomb": "morreu com a explosão da spike",
                "Fall": "morreu após uma queda",
                "Crush": "morreu por esmagamento",
            }.get(damage_type, "morreu sem autor registrado")
            return f"Aos {seconds} s, {victim} {action}{suffix}"
        action = "morreu" if event["actor"] == event["victim"] else f"eliminou {victim}"
        return f"Aos {seconds} s, {actor} {action}{suffix}"
    if event["kind"] == "plant":
        return (
            f"Aos {seconds} s, {actor} plantou a spike no ponto {round_result['plantSite']}{suffix}"
        )
    return f"Aos {seconds} s, {actor} desarmou a spike{suffix}"


def draw_round_map(
    map_meta,
    events,
    event_index,
    selected_puuid,
    team_by_puuid,
    name_by_puuid,
    *,
    highlight_selected=True,
):
    """Mostra posições sem nomes, com destaque para os abates do mesmo instante.

    Os eventos simultâneos compartilham o mesmo estado posterior. Por isso todas
    as vítimas desse instante são desenhadas mesmo ao abrir o primeiro evento do
    grupo. Uma posição ausente continua ausente, inclusive a de quem abateu.
    """
    with Image.open(minimap_file(map_meta)) as source:
        image = source.copy()
    width, height = image.size
    ally_team = team_by_puuid.get(selected_puuid)

    def to_pixels(location):
        fraction_x, fraction_y = game_to_image_fraction(location["x"], location["y"], map_meta)
        return fraction_x * width, fraction_y * height

    def color_of(puuid):
        team = team_by_puuid.get(puuid)
        if team is None:
            return "#777777"
        return ALLY_COLOR if team == ally_team else ENEMY_COLOR

    def marker_of(puuid):
        return "o" if team_by_puuid.get(puuid) == ally_team else "^"

    figure, axes = plt.subplots(figsize=(7, 7.8))
    axes.imshow(image)
    if not events or not 0 <= event_index < len(events):
        axes.axis("off")
        figure.tight_layout()
        plt.close(figure)
        return figure
    current_event = events[event_index]
    current_alive = alive_puuids(current_event)
    current_time = current_event.get("time_ms")
    # Chamadores antigos podem omitir o tempo. Nesse caso apenas o evento
    # escolhido é considerado simultâneo.
    known_events = (
        [event for event in events if event.get("time_ms", float("inf")) <= current_time]
        if current_time is not None
        else events[: event_index + 1]
    )
    simultaneous = (
        [event for event in known_events if event.get("time_ms") == current_time]
        if current_time is not None
        else [current_event]
    )
    victims_now = {event.get("victim") for event in simultaneous if event["kind"] == "kill"}
    killers_now = {
        event.get("actor") for event in simultaneous if is_enemy_kill(event, team_by_puuid)
    }
    dead_locations = {
        event["victim"]: event["victim_location"]
        for event in known_events
        if event["kind"] == "kill"
        and event["victim"] not in current_alive
        and _has_coordinates(event.get("victim_location"))
    }
    for puuid, location in dead_locations.items():
        draw_player(
            axes,
            to_pixels(location),
            color_of(puuid),
            marker_of(puuid),
            name_by_puuid.get(puuid, puuid),
            highlight_selected and puuid == selected_puuid,
            alive=False,
            is_killer=puuid in killers_now,
            is_victim=puuid in victims_now,
        )
    drawn = set(dead_locations)
    moment_locations = [
        location
        for event in [
            current_event,
            *[entry for entry in simultaneous if entry is not current_event],
        ]
        for location in event.get("locations", [])
    ]
    for player_location in moment_locations:
        puuid = player_location["puuid"]
        if (
            puuid in current_alive
            and puuid not in drawn
            and _has_coordinates(player_location.get("location"))
        ):
            draw_player(
                axes,
                to_pixels(player_location["location"]),
                color_of(puuid),
                marker_of(puuid),
                name_by_puuid.get(puuid, puuid),
                highlight_selected and puuid == selected_puuid,
                is_killer=puuid in killers_now,
                is_victim=puuid in victims_now,
            )
            drawn.add(puuid)
    figure.legend(
        handles=legend_handles(highlight_selected=highlight_selected),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=3,
        fontsize=8,
        frameon=False,
        columnspacing=1.4,
    )
    axes.axis("off")
    figure.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.16)
    plt.close(figure)
    return figure


def _has_coordinates(location):
    return bool(location) and location.get("x") is not None and location.get("y") is not None


def draw_points(map_meta, series):
    """Pontos sobre o minimapa. series é uma lista de (rótulo, cor, marcador, [(x, y), ...]) em coordenadas de jogo."""
    with Image.open(minimap_file(map_meta)) as source:
        image = source.copy()
    width, height = image.size
    figure, axes = plt.subplots(figsize=(7, 7))
    axes.imshow(image)
    for label, color, marker, points in series:
        fractions = [game_to_image_fraction(x, y, map_meta) for x, y in points]
        axes.scatter(
            [fx * width for fx, _ in fractions],
            [fy * height for _, fy in fractions],
            s=12,
            c=color,
            marker=marker,
            alpha=0.6,
            linewidths=0.8,
            label=f"{label} ({len(points)})",
        )
    if series:
        axes.legend(loc="lower right", fontsize=9)
    axes.axis("off")
    figure.tight_layout()
    plt.close(figure)
    return figure


def draw_rate_markers(
    map_meta,
    rows,
    count_column,
    rate_column,
    center_rate,
    colorbar_label,
    label_min_count=10,
    size_per_unit=4,
    zoom_padding=None,
):
    """Um marcador por linha (x, y em coordenadas de jogo): tamanho pela contagem, cor pela taxa, centrada em center_rate. Círculo acima do centro, quadrado abaixo.

    Com zoom_padding (em pixels) a imagem é recortada ao redor dos marcadores."""
    with Image.open(minimap_file(map_meta)) as source:
        image = source.copy()
    width, height = image.size
    figure, axes = plt.subplots(figsize=(7, 7))
    axes.imshow(image)
    fractions = [game_to_image_fraction(x, y, map_meta) for x, y in zip(rows["x"], rows["y"])]
    pixel_xs = [fx * width for fx, _ in fractions]
    pixel_ys = [fy * height for _, fy in fractions]
    center_rate = float(center_rate) if np.isfinite(center_rate) else 0.5
    norm = (
        TwoSlopeNorm(
            vcenter=center_rate, vmin=max(0.0, center_rate - 0.3), vmax=min(1.0, center_rate + 0.3)
        )
        if 0 < center_rate < 1
        else Normalize(vmin=0, vmax=1)
    )
    sizes = 20 + size_per_unit * rows[count_column].to_numpy()
    rates = rows[rate_column].to_numpy()
    xs, ys = np.array(pixel_xs), np.array(pixel_ys)
    for marker, mask in [("o", rates >= center_rate), ("s", rates < center_rate)]:
        axes.scatter(
            xs[mask],
            ys[mask],
            s=sizes[mask],
            c=rates[mask],
            marker=marker,
            cmap="RdBu",
            norm=norm,
            edgecolors="white",
            linewidths=0.8,
            alpha=0.9,
        )
    markers = plt.cm.ScalarMappable(norm=norm, cmap="RdBu")
    axes.legend(
        handles=[
            Line2D([], [], marker="o", color="#777777", linestyle="", label="na média ou acima"),
            Line2D([], [], marker="s", color="#777777", linestyle="", label="abaixo da média"),
        ],
        loc="lower right",
        fontsize=8,
    )
    for name, count, pixel_x, pixel_y in zip(rows.index, rows[count_column], pixel_xs, pixel_ys):
        if count >= label_min_count:
            axes.annotate(
                f"{name} ({count})",
                (pixel_x, pixel_y),
                xytext=(0, 9),
                textcoords="offset points",
                fontsize=7,
                color="#111111",
                ha="center",
                path_effects=[withStroke(linewidth=2.5, foreground="white")],
            )
    colorbar = figure.colorbar(markers, ax=axes, fraction=0.04, pad=0.02)
    colorbar.set_label(colorbar_label)
    if zoom_padding and pixel_xs:
        axes.set_xlim(
            max(0, min(pixel_xs) - zoom_padding), min(width, max(pixel_xs) + zoom_padding)
        )
        axes.set_ylim(
            min(height, max(pixel_ys) + zoom_padding), max(0, min(pixel_ys) - zoom_padding)
        )
    axes.axis("off")
    figure.tight_layout()
    plt.close(figure)
    return figure


def draw_callout_summary(map_meta, callout_rows, center_rate, label_min_count=10):
    """Um marcador por callout: tamanho pelo número de aberturas, cor pela vitória do ataque ao abrir ali."""
    return draw_rate_markers(
        map_meta,
        callout_rows,
        "aberturas",
        "ataque_venceu",
        center_rate,
        "vitórias do ataque após o primeiro abate nesta região",
        label_min_count,
    )


def draw_player(
    axes, pixels, color, marker, name, is_selected, alive=True, *, is_killer=False, is_victim=False
):
    """Desenha um jogador sem escrever seu nome sobre o mapa.

    ``name`` permanece na assinatura para os chamadores existentes. A identidade
    fica na tabela ao lado e nos detalhes do evento.
    """
    pixel_x, pixel_y = pixels
    if is_selected:
        # O anel permanece diferente dos símbolos de autor e vítima.
        axes.scatter(
            [pixel_x],
            [pixel_y],
            s=230,
            facecolors="none",
            edgecolors="white",
            linewidths=3,
            marker="o",
            zorder=4,
        )
        axes.scatter(
            [pixel_x],
            [pixel_y],
            s=230,
            facecolors="none",
            edgecolors="#222222",
            linewidths=1,
            marker="o",
            zorder=4,
        )
    if alive:
        axes.scatter(
            [pixel_x],
            [pixel_y],
            s=48,
            c=color,
            marker=marker,
            edgecolors="white",
            linewidths=0.7,
            zorder=5,
        )
    else:
        axes.scatter(
            [pixel_x],
            [pixel_y],
            s=48,
            facecolors="none",
            marker=marker,
            edgecolors=color,
            linewidths=1.3,
            zorder=5,
        )
    if is_killer:
        axes.scatter(
            [pixel_x],
            [pixel_y],
            s=165,
            c=color,
            marker="*",
            edgecolors="white",
            linewidths=0.8,
            zorder=6,
        )
    if is_victim:
        axes.scatter(
            [pixel_x],
            [pixel_y],
            s=40 if is_killer else 90,
            c="#222222" if is_killer else color,
            marker="X",
            edgecolors="white",
            linewidths=0.8,
            zorder=7,
        )


def legend_handles(*, highlight_selected=True):
    handles = [
        Line2D([], [], marker="o", color=ALLY_COLOR, linestyle="", label="aliado vivo"),
        Line2D(
            [],
            [],
            marker="o",
            markerfacecolor="none",
            color=ALLY_COLOR,
            linestyle="",
            label="aliado morto",
        ),
        Line2D([], [], marker="^", color=ENEMY_COLOR, linestyle="", label="inimigo vivo"),
        Line2D(
            [],
            [],
            marker="^",
            markerfacecolor="none",
            color=ENEMY_COLOR,
            linestyle="",
            label="inimigo morto",
        ),
        Line2D(
            [], [], marker="*", markersize=11, color="#555555", linestyle="", label="fez o abate"
        ),
        Line2D(
            [],
            [],
            marker="X",
            markersize=8,
            color="#555555",
            linestyle="",
            label="morreu no instante",
        ),
    ]
    if highlight_selected:
        handles.append(
            Line2D(
                [],
                [],
                marker="o",
                markersize=11,
                markerfacecolor="none",
                color="#222222",
                linestyle="",
                label="jogador escolhido",
            )
        )
    return handles
