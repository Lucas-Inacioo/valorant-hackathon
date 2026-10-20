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
from valorant.analysis.events import alive_puuids, round_events

ALLY_COLOR = "#1f77b4"
ENEMY_COLOR = "#d62728"


def describe_event(event, name_by_puuid, round_result):
    seconds = f"{event['time_ms'] / 1000:.1f}".replace(".", ",")
    actor = name_by_puuid.get(event["actor"], "autor desconhecido")
    suffix = ", quando o round já estava decidido" if event.get("after_decision") else ""
    if event["kind"] == "kill":
        victim = name_by_puuid.get(event["victim"], "jogador desconhecido")
        action = "morreu" if event["actor"] == event["victim"] else f"eliminou {victim}"
        return f"Aos {seconds} s, {actor} {action}{suffix}"
    if event["kind"] == "plant":
        return (
            f"Aos {seconds} s, {actor} plantou a spike no ponto {round_result['plantSite']}{suffix}"
        )
    return f"Aos {seconds} s, {actor} desarmou a spike{suffix}"


def draw_round_map(map_meta, events, event_index, selected_puuid, team_by_puuid, name_by_puuid):
    """Desenha o momento event_index: aliados como círculo, inimigos como triângulo, vivos cheios e mortos vazados."""
    with Image.open(minimap_file(map_meta)) as source:
        image = source.copy()
    width, height = image.size
    ally_team = team_by_puuid[selected_puuid]

    def to_pixels(location):
        fraction_x, fraction_y = game_to_image_fraction(location["x"], location["y"], map_meta)
        return fraction_x * width, fraction_y * height

    def color_of(puuid):
        return ALLY_COLOR if team_by_puuid[puuid] == ally_team else ENEMY_COLOR

    def marker_of(puuid):
        return "o" if team_by_puuid[puuid] == ally_team else "^"

    figure, axes = plt.subplots(figsize=(7, 7))
    axes.imshow(image)
    current_alive = alive_puuids(events[event_index])
    dead_locations = {
        event["victim"]: event["victim_location"]
        for event in events[: event_index + 1]
        if event["kind"] == "kill" and event["victim"] not in current_alive
    }
    for puuid, location in dead_locations.items():
        draw_player(
            axes,
            to_pixels(location),
            color_of(puuid),
            marker_of(puuid),
            name_by_puuid[puuid],
            puuid == selected_puuid,
            alive=False,
        )
    for player_location in events[event_index]["locations"]:
        puuid = player_location["puuid"]
        if puuid in current_alive:
            draw_player(
                axes,
                to_pixels(player_location["location"]),
                color_of(puuid),
                marker_of(puuid),
                name_by_puuid[puuid],
                puuid == selected_puuid,
            )
    trail = [
        to_pixels(player_location["location"])
        for event in events[: event_index + 1]
        for player_location in event["locations"]
        if player_location["puuid"] == selected_puuid
    ]
    if selected_puuid in dead_locations:
        trail.append(to_pixels(dead_locations[selected_puuid]))
    if len(trail) > 1:
        axes.plot(
            [x for x, _ in trail], [y for _, y in trail], color="white", linewidth=1.5, alpha=0.8
        )
    axes.legend(handles=legend_handles(), loc="lower right", fontsize=8)
    axes.axis("off")
    figure.tight_layout()
    plt.close(figure)
    return figure


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


def draw_player(axes, pixels, color, marker, name, is_selected, alive=True):
    pixel_x, pixel_y = pixels
    if alive:
        axes.scatter(
            [pixel_x],
            [pixel_y],
            s=200 if is_selected else 80,
            c=color,
            marker=marker,
            edgecolors="white",
            linewidths=2 if is_selected else 0.5,
            zorder=5,
        )
    else:
        axes.scatter(
            [pixel_x],
            [pixel_y],
            s=200 if is_selected else 80,
            facecolors="none",
            marker=marker,
            edgecolors=color,
            linewidths=2.5 if is_selected else 1.5,
            zorder=5,
        )
    axes.annotate(
        name,
        (pixel_x, pixel_y),
        xytext=(6, 6),
        textcoords="offset points",
        fontsize=8,
        color="#111111",
        weight="bold" if is_selected else "normal",
        path_effects=[withStroke(linewidth=2.5, foreground="white")],
    )


def legend_handles():
    return [
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
    ]
