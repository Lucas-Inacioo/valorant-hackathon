"""Plant e defuse: onde a spike é plantada, quanto cada posição é defusada e quanto disso é só gente viva.

Uso: python plants.py
"""
import math

import pandas as pd

from explore_fields import DEFAULT_DATA_DIR, find_match_files, load_match

CELL_SIZE = 400
TIME_BINS = [0, 20, 40, 60, 80, 100, 200]
TIME_LABELS = ["0-20 s", "20-40 s", "40-60 s", "60-80 s", "80-100 s", "100+ s"]


def plant_rows(match):
    """Uma linha por round plantado: posição, site, vivos de cada lado no plant e se foi defusada."""
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    rows = []
    for round_result in match["roundResults"]:
        if not round_result["bombPlanter"]:
            continue
        attacking_team = team_by_puuid[round_result["bombPlanter"]]
        alive = round_result["plantPlayerLocations"] or []
        attackers_alive = sum(1 for player in alive if team_by_puuid[player["puuid"]] == attacking_team)
        rows.append({
            "match_id": match["matchInfo"]["matchId"],
            "round": round_result["roundNum"] + 1,
            "mapa": match["matchInfo"]["mapId"].rsplit("/", 1)[-1],
            "site": round_result["plantSite"],
            "x": round_result["plantLocation"]["x"],
            "y": round_result["plantLocation"]["y"],
            "segundos_plant": round_result["plantRoundTime"] / 1000,
            "ataque_vivos": attackers_alive,
            "defesa_vivos": len(alive) - attackers_alive,
            "defusada": round_result["bombDefuser"] is not None,
            "segundos_ate_defuse": (round_result["defuseRoundTime"] - round_result["plantRoundTime"]) / 1000 if round_result["bombDefuser"] else math.nan,
            "resultado": round_result["roundResult"],
            "ataque_venceu": round_result["winningTeam"] == attacking_team,
        })
    return rows


def build_plants_table(data_dir=DEFAULT_DATA_DIR):
    rows = []
    for match_file in find_match_files(data_dir):
        rows += plant_rows(load_match(match_file))
    plants = pd.DataFrame(rows)
    plants["situacao"] = plants["ataque_vivos"].astype(str) + "v" + plants["defesa_vivos"].astype(str)
    expected = plants.groupby("situacao")["defusada"].mean()
    plants["esperado_pelos_vivos"] = plants["situacao"].map(expected)
    plants["acima_do_esperado"] = plants["defusada"].astype(float) - plants["esperado_pelos_vivos"]
    plants["faixa_tempo"] = pd.cut(plants["segundos_plant"], TIME_BINS, labels=TIME_LABELS)
    plants["celula_x"] = (plants["x"] / CELL_SIZE).round().astype(int) * CELL_SIZE
    plants["celula_y"] = (plants["y"] / CELL_SIZE).round().astype(int) * CELL_SIZE
    return plants


def summary_by_site(plants):
    return plants.groupby(["mapa", "site"]).agg(plants=("site", "size"), defuse=("defusada", "mean"), esperado_pelos_vivos=("esperado_pelos_vivos", "mean"), acima_do_esperado=("acima_do_esperado", "mean"), segundos_plant=("segundos_plant", "median")).round(3)


def situation_matrix(plants):
    """Defuse por vivos do ataque (linhas) e da defesa (colunas) no momento do plant, e o n de cada célula."""
    rates = pd.crosstab(plants["ataque_vivos"], plants["defesa_vivos"], values=plants["defusada"], aggfunc="mean").round(2)
    counts = pd.crosstab(plants["ataque_vivos"], plants["defesa_vivos"])
    return rates, counts


def summary_by_plant_time(plants):
    return plants.groupby("faixa_tempo", observed=True).agg(plants=("site", "size"), defuse=("defusada", "mean"), esperado_pelos_vivos=("esperado_pelos_vivos", "mean"), acima_do_esperado=("acima_do_esperado", "mean")).round(3)


def cells_for_map(plants, map_name, min_plants=5):
    """Células de 400 unidades dentro do mapa: plants, defuse, esperado pelos vivos e a diferença, com o centro para desenhar."""
    map_plants = plants[plants["mapa"] == map_name]
    cells = map_plants.groupby(["site", "celula_x", "celula_y"]).agg(plants=("site", "size"), defuse=("defusada", "mean"), esperado_pelos_vivos=("esperado_pelos_vivos", "mean"), acima_do_esperado=("acima_do_esperado", "mean")).reset_index()
    cells = cells[cells["plants"] >= min_plants].sort_values("plants", ascending=False)
    cells.index = [f"{site} {number}" for number, site in enumerate(cells["site"], start=1)]
    return cells.rename(columns={"celula_x": "x", "celula_y": "y"}).round(3)


def main():
    plants = build_plants_table()
    print(f"Rounds plantados: {len(plants)}, defusados: {plants['defusada'].mean():.1%}\n")
    print("Por mapa e site:"); print(summary_by_site(plants).to_string(), "\n")
    rates, counts = situation_matrix(plants)
    print("Defuse por vivos no plant (ataque x defesa):"); print(rates.to_string(), "\n"); print(counts.to_string(), "\n")
    print("Por tempo do plant:"); print(summary_by_plant_time(plants).to_string(), "\n")
    for map_name in ["Ascent", "Jam", "Triad"]:
        print(f"Células com 5+ plants em {map_name}:"); print(cells_for_map(plants, map_name).head(12).to_string(), "\n")


if __name__ == "__main__":
    main()
