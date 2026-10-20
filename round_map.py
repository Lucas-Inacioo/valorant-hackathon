"""Linha do tempo de um round (kills, plant e defuse) e o desenho das posições sobre o minimapa."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patheffects import withStroke
from matplotlib.lines import Line2D
from PIL import Image

from maps import game_to_image_fraction, minimap_file

ALLY_COLOR = "#1f77b4"
ENEMY_COLOR = "#d62728"


def round_events(round_result):
    """Kills, plant e defuse em ordem de tempo. Cada evento traz a posição de quem estava vivo logo depois dele."""
    events = []
    for player_stats in round_result["playerStats"]:
        for kill in player_stats["kills"]:
            events.append({
                "time_ms": kill["timeSinceRoundStartMillis"],
                "kind": "kill",
                "actor": kill["killer"],
                "victim": kill["victim"],
                "victim_location": kill["victimLocation"],
                "locations": kill["playerLocations"] or [],
                "assistants": kill["assistants"] or [],
                "finishing": kill["finishingDamage"],
            })
    if round_result["bombPlanter"]:
        events.append({"time_ms": round_result["plantRoundTime"], "kind": "plant", "actor": round_result["bombPlanter"], "locations": round_result["plantPlayerLocations"] or []})
    if round_result["bombDefuser"]:
        events.append({"time_ms": round_result["defuseRoundTime"], "kind": "defuse", "actor": round_result["bombDefuser"], "locations": round_result["defusePlayerLocations"] or []})
    return sorted(events, key=lambda event: event["time_ms"])


def describe_event(event, name_by_puuid, round_result):
    seconds = event["time_ms"] / 1000
    actor = name_by_puuid[event["actor"]]
    if event["kind"] == "kill":
        return f"{seconds:.1f} s: {actor} eliminou {name_by_puuid[event['victim']]}"
    if event["kind"] == "plant":
        return f"{seconds:.1f} s: {actor} plantou a spike no site {round_result['plantSite']}"
    return f"{seconds:.1f} s: {actor} desarmou a spike"


def draw_round_map(map_meta, events, event_index, selected_puuid, team_by_puuid, name_by_puuid):
    """Desenha o momento event_index: vivos como bolinha, mortos como X, aliados do jogador em azul e inimigos em vermelho."""
    image = Image.open(minimap_file(map_meta))
    width, height = image.size
    ally_team = team_by_puuid[selected_puuid]

    def to_pixels(location):
        fraction_x, fraction_y = game_to_image_fraction(location["x"], location["y"], map_meta)
        return fraction_x * width, fraction_y * height

    def color_of(puuid):
        return ALLY_COLOR if team_by_puuid[puuid] == ally_team else ENEMY_COLOR

    figure, axes = plt.subplots(figsize=(7, 7))
    axes.imshow(image)
    dead_locations = {event["victim"]: event["victim_location"] for event in events[:event_index + 1] if event["kind"] == "kill"}
    for puuid, location in dead_locations.items():
        draw_player(axes, to_pixels(location), color_of(puuid), "X", name_by_puuid[puuid], puuid == selected_puuid)
    for player_location in events[event_index]["locations"]:
        puuid = player_location["puuid"]
        if puuid not in dead_locations:
            draw_player(axes, to_pixels(player_location["location"]), color_of(puuid), "o", name_by_puuid[puuid], puuid == selected_puuid)
    trail = [to_pixels(player_location["location"]) for event in events[:event_index + 1] for player_location in event["locations"] if player_location["puuid"] == selected_puuid]
    if selected_puuid in dead_locations:
        trail.append(to_pixels(dead_locations[selected_puuid]))
    if len(trail) > 1:
        axes.plot([x for x, _ in trail], [y for _, y in trail], color="white", linewidth=1.5, alpha=0.8)
    axes.legend(handles=legend_handles(), loc="lower right", fontsize=8)
    axes.axis("off")
    figure.tight_layout()
    return figure


def draw_points(map_meta, series):
    """Pontos sobre o minimapa. series é uma lista de (rótulo, cor, [(x, y), ...]) em coordenadas de jogo."""
    image = Image.open(minimap_file(map_meta))
    width, height = image.size
    figure, axes = plt.subplots(figsize=(7, 7))
    axes.imshow(image)
    for label, color, points in series:
        fractions = [game_to_image_fraction(x, y, map_meta) for x, y in points]
        axes.scatter([fx * width for fx, _ in fractions], [fy * height for _, fy in fractions], s=8, c=color, alpha=0.55, linewidths=0, label=f"{label} ({len(points)})")
    axes.legend(loc="lower right", fontsize=8)
    axes.axis("off")
    figure.tight_layout()
    return figure


def draw_rate_markers(map_meta, rows, count_column, rate_column, center_rate, colorbar_label, label_min_count=10, size_per_unit=4, zoom_padding=None):
    """Um marcador por linha (x, y em coordenadas de jogo): tamanho pela contagem, cor pela taxa, centrada em center_rate.

    Com zoom_padding (em pixels) a imagem é recortada ao redor dos marcadores."""
    image = Image.open(minimap_file(map_meta))
    width, height = image.size
    figure, axes = plt.subplots(figsize=(7, 7))
    axes.imshow(image)
    fractions = [game_to_image_fraction(x, y, map_meta) for x, y in zip(rows["x"], rows["y"])]
    pixel_xs = [fx * width for fx, _ in fractions]
    pixel_ys = [fy * height for _, fy in fractions]
    norm = TwoSlopeNorm(vcenter=center_rate, vmin=max(0.0, center_rate - 0.3), vmax=min(1.0, center_rate + 0.3))
    markers = axes.scatter(pixel_xs, pixel_ys, s=20 + size_per_unit * rows[count_column], c=rows[rate_column], cmap="RdBu", norm=norm, edgecolors="white", linewidths=0.8, alpha=0.9)
    for name, count, pixel_x, pixel_y in zip(rows.index, rows[count_column], pixel_xs, pixel_ys):
        if count >= label_min_count:
            axes.annotate(f"{name} ({count})", (pixel_x, pixel_y), xytext=(0, 9), textcoords="offset points", fontsize=7, color="#111111", ha="center", path_effects=[withStroke(linewidth=2.5, foreground="white")])
    colorbar = figure.colorbar(markers, ax=axes, fraction=0.04, pad=0.02)
    colorbar.set_label(colorbar_label)
    if zoom_padding and pixel_xs:
        axes.set_xlim(max(0, min(pixel_xs) - zoom_padding), min(width, max(pixel_xs) + zoom_padding))
        axes.set_ylim(min(height, max(pixel_ys) + zoom_padding), max(0, min(pixel_ys) - zoom_padding))
    axes.axis("off")
    figure.tight_layout()
    return figure


def draw_callout_summary(map_meta, callout_rows, center_rate, label_min_count=10):
    """Um marcador por callout: tamanho pelo número de aberturas, cor pela vitória do ataque ao abrir ali."""
    return draw_rate_markers(map_meta, callout_rows, "aberturas", "ataque_venceu", center_rate, "vitória do ataque ao abrir aqui", label_min_count)


def draw_player(axes, pixels, color, marker, name, is_selected):
    pixel_x, pixel_y = pixels
    axes.scatter([pixel_x], [pixel_y], s=200 if is_selected else 80, c=color, marker=marker, edgecolors="white", linewidths=2 if is_selected else 0.5, zorder=5)
    axes.annotate(name, (pixel_x, pixel_y), xytext=(6, 6), textcoords="offset points", fontsize=8, color="#111111", weight="bold" if is_selected else "normal", path_effects=[withStroke(linewidth=2.5, foreground="white")])


def legend_handles():
    return [
        Line2D([], [], marker="o", color=ALLY_COLOR, linestyle="", label="aliado vivo"),
        Line2D([], [], marker="X", color=ALLY_COLOR, linestyle="", label="aliado morto"),
        Line2D([], [], marker="o", color=ENEMY_COLOR, linestyle="", label="inimigo vivo"),
        Line2D([], [], marker="X", color=ENEMY_COLOR, linestyle="", label="inimigo morto"),
    ]
