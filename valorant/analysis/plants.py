"""Plant e defuse: onde a spike é plantada, quanto cada posição é defusada e quanto disso é só gente viva.

Uso: python -m valorant.analysis.plants
"""

import math

import pandas as pd

from valorant.data.fields import DEFAULT_DATA_DIR
from valorant.data.quality import eligible_match_ids, iter_selected_matches
from valorant.analysis.events import alive_puuids, round_events

CELL_SIZE = 400
TIME_BINS = [0, 20, 40, 60, 80, 100, 200]
TIME_LABELS = ["0-20 s", "20-40 s", "40-60 s", "60-80 s", "80-100 s", "100+ s"]
PLANT_COLUMNS = [
    "match_id",
    "round",
    "mapa",
    "site",
    "x",
    "y",
    "segundos_plant",
    "ataque_vivos",
    "defesa_vivos",
    "defusada",
    "segundos_ate_defuse",
    "resultado",
    "ataque_venceu",
    "plant_valido",
    "exclusao_plant",
]


def plant_event(round_result, team_by_puuid):
    return next(
        (event for event in round_events(round_result, team_by_puuid) if event["kind"] == "plant"),
        None,
    )


def plant_exclusion(round_result, team_by_puuid, event=None):
    """Mesmas regras do replay/indicadores: uma única definição de plant válido."""
    if not round_result.get("bombPlanter"):
        return "sem plant registrado"
    event = plant_event(round_result, team_by_puuid) if event is None else event
    return event["plant_exclusion"] if event is not None else "evento do plant sem timestamp"


def plant_rows(match, include_invalid=False):
    """Uma linha por round plantado: posição, site, vivos de cada lado no plant e se foi defusada."""
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    rows = []
    for round_result in match["roundResults"]:
        if not round_result["bombPlanter"]:
            continue
        event = plant_event(round_result, team_by_puuid)
        exclusion = plant_exclusion(round_result, team_by_puuid, event)
        if exclusion and not include_invalid:
            continue
        attacking_team = team_by_puuid[round_result["bombPlanter"]]
        current_alive = alive_puuids(event) if event is not None else set()
        alive = [
            player
            for player in round_result["plantPlayerLocations"] or []
            if player["puuid"] in current_alive
        ]
        attackers_alive = sum(
            1 for player in alive if team_by_puuid[player["puuid"]] == attacking_team
        )
        rows.append(
            {
                "match_id": match["matchInfo"]["matchId"],
                "round": round_result["roundNum"] + 1,
                "mapa": match["matchInfo"]["mapId"].rsplit("/", 1)[-1],
                "site": round_result["plantSite"],
                "x": (round_result.get("plantLocation") or {}).get("x", math.nan),
                "y": (round_result.get("plantLocation") or {}).get("y", math.nan),
                "segundos_plant": (
                    round_result["plantRoundTime"] / 1000
                    if round_result.get("plantRoundTime") is not None
                    else math.nan
                ),
                "ataque_vivos": attackers_alive,
                "defesa_vivos": len(alive) - attackers_alive,
                "defusada": round_result["bombDefuser"] is not None,
                "segundos_ate_defuse": (
                    (round_result["defuseRoundTime"] - round_result["plantRoundTime"]) / 1000
                    if round_result["bombDefuser"]
                    else math.nan
                ),
                "resultado": round_result["roundResult"],
                "ataque_venceu": round_result["winningTeam"] == attacking_team,
                "plant_valido": not bool(exclusion),
                "exclusao_plant": exclusion,
            }
        )
    return rows


def build_plants_table(data_dir=DEFAULT_DATA_DIR, include_invalid=False, match_ids=None):
    match_ids = eligible_match_ids(data_dir) if match_ids is None else set(match_ids)
    rows = []
    for _, match in iter_selected_matches(data_dir, match_ids):
        rows += plant_rows(match, include_invalid=include_invalid)
    plants = pd.DataFrame(rows, columns=PLANT_COLUMNS)
    plants["situacao"] = (
        plants["ataque_vivos"].astype(str) + "v" + plants["defesa_vivos"].astype(str)
    )
    valid = plants[plants["plant_valido"].astype(bool)]
    expected = valid.groupby("situacao")["defusada"].mean()
    plants["esperado_pelos_vivos"] = plants["situacao"].map(expected)
    plants["acima_do_esperado"] = plants["defusada"].astype(float) - plants["esperado_pelos_vivos"]
    plants["esperado_vitoria_vivos"] = plants["situacao"].map(
        valid.groupby("situacao")["ataque_venceu"].mean()
    )
    plants["vitoria_acima_esperado"] = (
        plants["ataque_venceu"].astype(float) - plants["esperado_vitoria_vivos"]
    )
    plants.loc[
        ~plants["plant_valido"].astype(bool),
        [
            "esperado_pelos_vivos",
            "acima_do_esperado",
            "esperado_vitoria_vivos",
            "vitoria_acima_esperado",
        ],
    ] = math.nan
    plants["faixa_tempo"] = pd.cut(
        plants["segundos_plant"], TIME_BINS, labels=TIME_LABELS, include_lowest=True
    )
    plants["celula_x"] = (plants["x"] / CELL_SIZE).round().astype("Int64") * CELL_SIZE
    plants["celula_y"] = (plants["y"] / CELL_SIZE).round().astype("Int64") * CELL_SIZE
    return plants


def _summary(plants, columns):
    if "plant_valido" in plants:
        plants = plants[plants["plant_valido"].astype(bool)]
    table = plants.groupby(columns, observed=True).agg(
        plants=("site", "size"),
        partidas=("match_id", "nunique"),
        defuse=("defusada", "mean"),
        esperado_pelos_vivos=("esperado_pelos_vivos", "mean"),
        acima_do_esperado=("acima_do_esperado", "mean"),
        segundos_plant=("segundos_plant", "median"),
    )
    # Wilson é descritivo e supõe independência; rounds de uma partida dependem.
    n, p, z = table["plants"], table["defuse"], 1.96
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    radius = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    table["defuse_ic95_min"] = center - radius
    table["defuse_ic95_max"] = center + radius
    return table


def summary_by_site(plants):
    return _summary(plants, ["mapa", "site"]).round(3)


def situation_matrix(plants):
    """Defuse por vivos do ataque (linhas) e da defesa (colunas) no momento do plant, e o n de cada célula."""
    if "plant_valido" in plants:
        plants = plants[plants["plant_valido"].astype(bool)]
    rates = pd.crosstab(
        plants["ataque_vivos"], plants["defesa_vivos"], values=plants["defusada"], aggfunc="mean"
    ).round(2)
    counts = pd.crosstab(plants["ataque_vivos"], plants["defesa_vivos"])
    return rates, counts


def summary_by_plant_time(plants):
    return _summary(plants, "faixa_tempo").round(3)


def cells_for_map(plants, map_name, min_plants=5):
    """Células de 400 unidades dentro do mapa: plants, defuse, esperado pelos vivos e a diferença, com o centro para desenhar."""
    map_plants = plants[plants["mapa"] == map_name]
    cells = _summary(map_plants, ["site", "celula_x", "celula_y"]).reset_index()
    cells = cells[cells["plants"] >= min_plants].sort_values("plants", ascending=False)
    cells.index = [f"{site} {number}" for number, site in enumerate(cells["site"], start=1)]
    return cells.rename(columns={"celula_x": "x", "celula_y": "y"}).round(3)


def main():
    plants = build_plants_table()
    print(f"Plants táticos válidos: {len(plants)}, defusados: {plants['defusada'].mean():.1%}\n")
    print("Por mapa e site:")
    print(summary_by_site(plants).to_string(), "\n")
    rates, counts = situation_matrix(plants)
    print("Defuse por vivos no plant (ataque x defesa):")
    print(rates.to_string(), "\n")
    print(counts.to_string(), "\n")
    print("Por tempo do plant:")
    print(summary_by_plant_time(plants).to_string(), "\n")
    for map_name in ["Ascent", "Jam", "Triad"]:
        print(f"Células com 5+ plants em {map_name}:")
        print(cells_for_map(plants, map_name).head(12).to_string(), "\n")


if __name__ == "__main__":
    main()
