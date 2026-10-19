"""Setup do pós-plant e do retake: onde o ataque estava e para onde olhava no plant, onde a defesa estava, e onde o ataque estava quando a spike foi defusada.

Uso: python setups.py
"""
import math

import pandas as pd

from explore_fields import DEFAULT_DATA_DIR, find_match_files, load_match
from fights import facing_angle
from maps import load_maps_by_url, nearest_callout
from solo_deaths import distance

# Até 15 m da spike conta como dentro do site
SITE_RADIUS = 1500
DEFENSE_DISTANCE_BANDS = [0, 2000, 3500, 5000, float("inf")]
DEFENSE_DISTANCE_LABELS = ["até 20 m", "20 a 35 m", "35 a 50 m", "50 m+"]


def setup_rows(match, map_meta):
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    rows = []
    for round_result in match["roundResults"]:
        planter = round_result["bombPlanter"]
        if not planter:
            continue
        attacking_team = team_by_puuid[planter]
        plant = round_result["plantLocation"]
        alive = round_result["plantPlayerLocations"] or []
        attackers = [player for player in alive if team_by_puuid[player["puuid"]] == attacking_team]
        defenders = [player for player in alive if team_by_puuid[player["puuid"]] != attacking_team]
        teammates = [player for player in attackers if player["puuid"] != planter]
        defender_distances = [distance(player["location"], plant) for player in defenders]
        row = {
            "match_id": match["matchInfo"]["matchId"],
            "round": round_result["roundNum"] + 1,
            "mapa": match["matchInfo"]["mapId"].rsplit("/", 1)[-1],
            "site": round_result["plantSite"],
            "segundos_plant": round_result["plantRoundTime"] / 1000,
            "ataque_vivos": len(attackers),
            "defesa_vivos": len(defenders),
            "atacantes_no_site": sum(1 for player in attackers if distance(player["location"], plant) <= SITE_RADIUS),
            "dispersao_ataque": sum(distance(player["location"], plant) for player in teammates) / len(teammates) if teammates else math.nan,
            "olhando_para_fora": sum(1 for player in teammates if facing_angle(player, plant) > 90) / len(teammates) if teammates else math.nan,
            "defesa_dist_mediana": sorted(defender_distances)[len(defender_distances) // 2] if defender_distances else math.nan,
            "defesa_mais_proxima": min(defender_distances, default=math.nan),
            "defusada": round_result["bombDefuser"] is not None,
            "atacantes_vivos_no_defuse": math.nan,
            "atacante_mais_proximo_no_defuse": math.nan,
            "regioes_ataque_no_defuse": "",
            "posicoes_ataque_no_defuse": [],
        }
        if round_result["bombDefuser"]:
            at_defuse = [player for player in (round_result["defusePlayerLocations"] or []) if team_by_puuid[player["puuid"]] == attacking_team]
            defuse_location = round_result["defuseLocation"]
            row["atacantes_vivos_no_defuse"] = len(at_defuse)
            row["atacante_mais_proximo_no_defuse"] = min((distance(player["location"], defuse_location) for player in at_defuse), default=math.nan)
            row["regioes_ataque_no_defuse"] = ", ".join(sorted({nearest_callout(player["location"]["x"], player["location"]["y"], map_meta) for player in at_defuse})) if map_meta else ""
            row["posicoes_ataque_no_defuse"] = [(player["location"]["x"], player["location"]["y"]) for player in at_defuse]
        rows.append(row)
    return rows


def build_setups_table(data_dir=DEFAULT_DATA_DIR):
    maps_by_url = load_maps_by_url()
    rows = []
    for match_file in find_match_files(data_dir):
        match = load_match(match_file)
        rows += setup_rows(match, maps_by_url.get(match["matchInfo"]["mapId"]))
    setups = pd.DataFrame(rows)
    situation = setups["ataque_vivos"].astype(str) + "v" + setups["defesa_vivos"].astype(str)
    setups["esperado_pelos_vivos"] = situation.map(setups.groupby(situation)["defusada"].mean())
    setups["acima_do_esperado"] = setups["defusada"].astype(float) - setups["esperado_pelos_vivos"]
    setups["faixa_defesa"] = pd.cut(setups["defesa_dist_mediana"], DEFENSE_DISTANCE_BANDS, labels=DEFENSE_DISTANCE_LABELS)
    return setups


def defuse_by(setups, column):
    """Taxa de defuse por valor da coluna, com o esperado pelos vivos no plant e a diferença."""
    return setups.groupby(column, observed=True).agg(plants=("defusada", "size"), defuse=("defusada", "mean"), esperado_pelos_vivos=("esperado_pelos_vivos", "mean"), acima_do_esperado=("acima_do_esperado", "mean")).round(3)


def watching_bands(setups):
    return pd.cut(setups["olhando_para_fora"], [-0.01, 0.34, 0.67, 1.0], labels=["até um terço", "até dois terços", "quase todos"])


def retake_summary(setups):
    """Rounds defusados: quantos atacantes vivos no defuse e a que distância estava o mais próximo."""
    defused = setups[setups["defusada"]].copy()
    defused["ninguem_a_15_m"] = defused["atacante_mais_proximo_no_defuse"].isna() | (defused["atacante_mais_proximo_no_defuse"] > SITE_RADIUS)
    return defused.groupby("atacantes_vivos_no_defuse").agg(defuses=("defusada", "size"), mais_proximo_mediano=("atacante_mais_proximo_no_defuse", "median"), ninguem_a_15_m=("ninguem_a_15_m", "mean")).round(3)


def defuse_positions_for_map(setups, map_name, site):
    """Posições dos atacantes vivos no momento do defuse, para desenhar onde o ataque estava quando perdeu."""
    defused = setups[setups["defusada"] & (setups["mapa"] == map_name) & (setups["site"] == site)]
    return pd.DataFrame([{"x": x, "y": y} for positions in defused["posicoes_ataque_no_defuse"] for x, y in positions])


def main():
    setups = build_setups_table()
    print(f"Rounds plantados: {len(setups)}, defusados: {int(setups['defusada'].sum())}\n")
    print("Defuse por atacantes dentro de 15 m da spike no plant:")
    print(defuse_by(setups, "atacantes_no_site").to_string(), "\n")
    print("Defuse por fração dos aliados do planter olhando para fora do site:")
    print(defuse_by(setups, watching_bands(setups)).to_string(), "\n")
    print("Defuse pela distância mediana da defesa até a spike no plant:")
    print(defuse_by(setups, "faixa_defesa").to_string(), "\n")
    print("Retake: atacantes vivos no defuse e distância do mais próximo:")
    print(retake_summary(setups).to_string(), "\n")
    print("Regiões do ataque no defuse, Ascent:")
    print(setups[setups["defusada"] & (setups["mapa"] == "Ascent")]["regioes_ataque_no_defuse"].value_counts().head(10).to_string())


if __name__ == "__main__":
    main()
