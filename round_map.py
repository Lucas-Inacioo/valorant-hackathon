"""Linha do tempo de um round (kills, plant e defuse) e o desenho das posições sobre o minimapa."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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


def draw_player(axes, pixels, color, marker, name, is_selected):
    pixel_x, pixel_y = pixels
    axes.scatter([pixel_x], [pixel_y], s=200 if is_selected else 80, c=color, marker=marker, edgecolors="white", linewidths=2 if is_selected else 0.5, zorder=5)
    axes.annotate(name, (pixel_x, pixel_y), xytext=(6, 6), textcoords="offset points", fontsize=8, color="white", weight="bold" if is_selected else "normal")


def legend_handles():
    return [
        Line2D([], [], marker="o", color=ALLY_COLOR, linestyle="", label="aliado vivo"),
        Line2D([], [], marker="X", color=ALLY_COLOR, linestyle="", label="aliado morto"),
        Line2D([], [], marker="o", color=ENEMY_COLOR, linestyle="", label="inimigo vivo"),
        Line2D([], [], marker="X", color=ENEMY_COLOR, linestyle="", label="inimigo morto"),
    ]
