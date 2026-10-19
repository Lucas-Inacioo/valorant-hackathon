"""As métricas das conclusões explicam e preveem partidas e campeonatos sem usar o resultado?

Uso: python predict.py
Três testes. Dentro da partida com rounds embaralhados (só taxas, sem ordem, sem placar, sem número de rounds).
Previsão de verdade, com o perfil de cada time calculado só nas outras partidas dele. E o ranking por campeonato.
"""
import math
import random
import re
from pathlib import Path

import pandas as pd

from explore_fields import DEFAULT_DATA_DIR, find_match_files, load_match
from solo_deaths import build_deaths_table, with_solo_flag

MATCH_NAME = re.compile(r"^(?P<prefix>[A-Z0-9_]+?)_(?P<number>\d+[a-z]?)_(?P<date>\d{2}-\d{2}-\d{2})_(?P<team1>.+?)_(?P<score1>\d+)_x_(?P<score2>\d+)_(?P<team2>.+?)_(?P<map>[a-z]+)$")
OTHER_TEAM = {"Blue": "Red", "Red": "Blue"}
# Sinal de cada métrica: +1 quando mais é melhor, -1 quando menos é melhor
FEATURE_SIGNS = {"abertura": 1, "troca": 1, "troca_1a_morte": 1, "plant_limpo": 1, "flanco_defesa": -1, "isolada": -1}
HEADLINE_FEATURES = ["abertura", "troca"]
MIN_OTHER_MATCHES = 2


def parse_match_name(match_file):
    parsed = MATCH_NAME.match(match_file.stem)
    if not parsed:
        raise ValueError(f"nome fora do padrão: {match_file.name}")
    return parsed.groupdict()


def team_names_by_color(match, parsed_name):
    """O placar do nome do arquivo diz qual time é Blue e qual é Red."""
    rounds_won = {team["teamId"]: team["roundsWon"] for team in match["teams"]}
    if int(parsed_name["score1"]) == rounds_won["Blue"] and int(parsed_name["score2"]) == rounds_won["Red"]:
        return {"Blue": parsed_name["team1"], "Red": parsed_name["team2"]}
    if int(parsed_name["score1"]) == rounds_won["Red"] and int(parsed_name["score2"]) == rounds_won["Blue"]:
        return {"Red": parsed_name["team1"], "Blue": parsed_name["team2"]}
    raise ValueError(f"placar do nome não bate com roundsWon: {parsed_name}")


def attacking_team_by_round(match):
    """Lado sem usar o resultado: quem planta a spike em cada metade é o ataque. Overtime é round a round."""
    team_by_puuid = {player["puuid"]: player["teamId"] for player in match["players"]}
    planter_team_by_half = {}
    for round_result in match["roundResults"]:
        half = half_of(round_result["roundNum"])
        if round_result["bombPlanter"]:
            planter_team_by_half.setdefault(half, team_by_puuid[round_result["bombPlanter"]])
    return {round_result["roundNum"] + 1: planter_team_by_half.get(half_of(round_result["roundNum"])) for round_result in match["roundResults"]}


def half_of(round_num):
    return round_num // 12 if round_num < 24 else 24 + round_num


def load_matches():
    rows = []
    for match_file in find_match_files(DEFAULT_DATA_DIR):
        match = load_match(match_file)
        parsed = parse_match_name(match_file)
        names = team_names_by_color(match, parsed)
        won = {team["teamId"]: team["won"] for team in match["teams"]}
        rows.append({
            "match_id": match["matchInfo"]["matchId"],
            "campeonato": match_file.relative_to(DEFAULT_DATA_DIR).parts[1],
            "inicio": match["matchInfo"]["gameStartMillis"],
            "nome_blue": names["Blue"],
            "nome_red": names["Red"],
            "venceu_blue": won["Blue"],
            "ataque_por_round": attacking_team_by_round(match),
        })
    return pd.DataFrame(rows)


def team_features(deaths, matches):
    """Por partida e time, só taxas sem resultado: abertura, trocas, plant limpo, flanco na defesa, isolamento."""
    attacking = {(row.match_id, round_number): team for row in matches.itertuples() for round_number, team in row.ataque_por_round.items()}
    deaths = deaths.copy()
    deaths["ataque_limpo"] = [attacking.get((match_id, round_number)) for match_id, round_number in zip(deaths["match_id"], deaths["round"])]
    deaths["lado_limpo"] = deaths["time_vitima"].where(deaths["ataque_limpo"].isna(), None)
    deaths["lado_limpo"] = ["?" if attacking_team is None else ("ataque" if victim_team == attacking_team else "defesa") for victim_team, attacking_team in zip(deaths["time_vitima"], deaths["ataque_limpo"])]
    deaths["time_killer"] = deaths["time_vitima"].map(OTHER_TEAM)
    rows = []
    for match_id, match_deaths in deaths.groupby("match_id"):
        first_deaths = match_deaths[match_deaths["ordem_da_morte"] == 1]
        for team in ["Blue", "Red"]:
            own = match_deaths[match_deaths["time_vitima"] == team]
            own_with_allies = own[own["aliados_vivos"] > 0]
            own_first = first_deaths[first_deaths["time_vitima"] == team]
            attack_rounds = {r for (m, r), t in attacking.items() if m == match_id and t == team}
            clean_plants = sum(1 for r in attack_rounds if (first_deaths[first_deaths["round"] == r]["fase"] == "pós-plant").any())
            defense_pre_plant = own[(own["lado_limpo"] == "defesa") & (own["fase"] == "pré-plant") & (own["aliados_vivos"] > 0)]
            rows.append({
                "match_id": match_id,
                "time": team,
                "abertura": (first_deaths["time_killer"] == team).mean() if len(first_deaths) else math.nan,
                "troca": own_with_allies["trocada"].mean() if len(own_with_allies) else math.nan,
                "troca_1a_morte": own_first["trocada"].mean() if len(own_first) else math.nan,
                "plant_limpo": clean_plants / len(attack_rounds) if attack_rounds else math.nan,
                "flanco_defesa": (defense_pre_plant["contexto"] == "flanco").mean() if len(defense_pre_plant) else math.nan,
                "isolada": (own_with_allies["dist_aliado_mais_proximo"] > 1000).mean() if len(own_with_allies) else math.nan,
            })
    return pd.DataFrame(rows)


def match_pairs(matches, features):
    """Uma linha por partida com a diferença Blue menos Red de cada métrica e se Blue venceu."""
    wide = features.pivot(index="match_id", columns="time")
    pairs = matches.set_index("match_id")[["campeonato", "inicio", "nome_blue", "nome_red", "venceu_blue"]].copy()
    for feature in FEATURE_SIGNS:
        pairs[feature] = wide[(feature, "Blue")] - wide[(feature, "Red")]
    return pairs


def combined_score(differences, features=tuple(FEATURE_SIGNS)):
    """Soma das diferenças padronizadas, cada uma com o sinal da métrica."""
    standardized = differences / differences.std()
    return sum(standardized[feature] * FEATURE_SIGNS[feature] for feature in features)


def in_match_accuracy(pairs):
    """Rounds embaralhados: o time com a métrica melhor na própria partida venceu?"""
    rows = []
    for feature, sign in FEATURE_SIGNS.items():
        decided = pairs[pairs[feature].fillna(0) != 0]
        predicted_blue = (decided[feature] * sign) > 0
        rows.append({"metrica": feature, "partidas": len(decided), "acerto": (predicted_blue == decided["venceu_blue"]).mean()})
    decided = pairs.dropna(subset=list(FEATURE_SIGNS))
    predicted_blue = combined_score(decided[list(FEATURE_SIGNS)]) > 0
    rows.append({"metrica": "combinada (todas)", "partidas": len(decided), "acerto": (predicted_blue == decided["venceu_blue"]).mean()})
    predicted_blue = combined_score(decided[list(FEATURE_SIGNS)], HEADLINE_FEATURES) > 0
    rows.append({"metrica": "combinada (abertura + troca)", "partidas": len(decided), "acerto": (predicted_blue == decided["venceu_blue"]).mean()})
    return pd.DataFrame(rows).round(3)


def team_profiles_out_of_match(matches, features, only_previous):
    """Perfil de cada time em cada partida usando só as outras partidas dele no campeonato (ou só as anteriores)."""
    long = features.merge(matches[["match_id", "campeonato", "inicio", "nome_blue", "nome_red", "venceu_blue"]], on="match_id")
    long["nome"] = long["nome_blue"].where(long["time"] == "Blue", long["nome_red"])
    long["venceu"] = long["venceu_blue"] == (long["time"] == "Blue")
    profiles = []
    for row in long.itertuples():
        others = long[(long["nome"] == row.nome) & (long["campeonato"] == row.campeonato) & (long["match_id"] != row.match_id)]
        if only_previous:
            others = others[others["inicio"] < row.inicio]
        profile = {"match_id": row.match_id, "time": row.time, "outras": len(others), "taxa_vitoria_outras": others["venceu"].mean() if len(others) else math.nan}
        for feature in FEATURE_SIGNS:
            profile[feature] = others[feature].mean() if len(others) else math.nan
        profiles.append(profile)
    return pd.DataFrame(profiles)


def forecast_accuracy(matches, features, only_previous):
    profiles = team_profiles_out_of_match(matches, features, only_previous)
    wide = profiles.pivot(index="match_id", columns="time")
    enough = (wide[("outras", "Blue")] >= MIN_OTHER_MATCHES) & (wide[("outras", "Red")] >= MIN_OTHER_MATCHES)
    labels = matches.set_index("match_id")["venceu_blue"]
    rows = []
    for feature, sign in FEATURE_SIGNS.items():
        difference = (wide[(feature, "Blue")] - wide[(feature, "Red")])[enough]
        decided = difference[difference.fillna(0) != 0]
        rows.append({"metrica": feature, "partidas": len(decided), "acerto": ((decided * sign > 0) == labels[decided.index]).mean()})
    differences = pd.DataFrame({feature: (wide[(feature, "Blue")] - wide[(feature, "Red")])[enough] for feature in FEATURE_SIGNS}).dropna()
    predicted_blue = combined_score(differences) > 0
    rows.append({"metrica": "combinada (todas)", "partidas": len(differences), "acerto": (predicted_blue == labels[differences.index]).mean()})
    predicted_blue = combined_score(differences, HEADLINE_FEATURES) > 0
    rows.append({"metrica": "combinada (abertura + troca)", "partidas": len(differences), "acerto": (predicted_blue == labels[differences.index]).mean()})
    win_rate_difference = (wide[("taxa_vitoria_outras", "Blue")] - wide[("taxa_vitoria_outras", "Red")])[enough]
    decided = win_rate_difference[win_rate_difference.fillna(0) != 0]
    rows.append({"metrica": "taxa de vitória nas outras partidas (base de comparação)", "partidas": len(decided), "acerto": ((decided > 0) == labels[decided.index]).mean()})
    return pd.DataFrame(rows).round(3)


def permutation_ceiling(pairs, repetitions=500, seed=0):
    """Acerto da combinada com os rótulos embaralhados: o que o acaso consegue com este tamanho de base."""
    decided = pairs.dropna(subset=list(FEATURE_SIGNS))
    predicted_blue = (combined_score(decided[list(FEATURE_SIGNS)]) > 0).to_numpy()
    labels = decided["venceu_blue"].to_numpy().copy()
    rng = random.Random(seed)
    accuracies = []
    for _ in range(repetitions):
        shuffled = labels.copy()
        rng.shuffle(shuffled)
        accuracies.append((predicted_blue == shuffled).mean())
    accuracies.sort()
    return accuracies[int(0.95 * repetitions)], accuracies[int(0.5 * repetitions)]


def tournament_ranking(matches, features, min_matches=3):
    """Por campeonato: times ordenados pelo perfil combinado, lado a lado com a taxa de vitória."""
    long = features.merge(matches[["match_id", "campeonato", "nome_blue", "nome_red", "venceu_blue"]], on="match_id")
    long["nome"] = long["nome_blue"].where(long["time"] == "Blue", long["nome_red"])
    long["venceu"] = long["venceu_blue"] == (long["time"] == "Blue")
    per_team = long.groupby(["campeonato", "nome"]).agg(partidas=("match_id", "size"), taxa_vitoria=("venceu", "mean"), **{feature: (feature, "mean") for feature in FEATURE_SIGNS}).reset_index()
    per_team = per_team[per_team["partidas"] >= min_matches].copy()
    tables = {}
    for tournament, group in per_team.groupby("campeonato"):
        centered = group[list(FEATURE_SIGNS)] - group[list(FEATURE_SIGNS)].mean()
        group = group.assign(perfil=combined_score(centered).round(2)).sort_values("perfil", ascending=False)
        group["spearman"] = round(group["perfil"].rank().corr(group["taxa_vitoria"].rank()), 2)
        tables[tournament] = group.set_index("nome")[["partidas", "taxa_vitoria", "perfil", "spearman"]].round(2)
    return tables


def main():
    matches = load_matches()
    deaths = build_deaths_table()
    features = team_features(deaths, matches)
    pairs = match_pairs(matches, features)
    print(f"Partidas: {len(matches)}, campeonatos: {matches['campeonato'].nunique()}, times: {pd.concat([matches['nome_blue'], matches['nome_red']]).nunique()}\n")
    print("1. Dentro da partida, rounds embaralhados (sem ordem, placar ou número de rounds): o time com a métrica melhor venceu?")
    print(in_match_accuracy(pairs).to_string(index=False))
    ceiling_95, median = permutation_ceiling(pairs)
    print(f"   acaso para a combinada com rótulos embaralhados: mediana {median:.3f}, percentil 95 {ceiling_95:.3f}\n")
    print("2. Previsão de verdade: perfil de cada time só nas OUTRAS partidas dele no campeonato (pelo menos 2 para cada lado)")
    print(forecast_accuracy(matches, features, only_previous=False).to_string(index=False), "\n")
    print("3. Previsão só com partidas ANTERIORES no tempo (pelo menos 2 para cada lado)")
    print(forecast_accuracy(matches, features, only_previous=True).to_string(index=False), "\n")
    print("4. Ranking por campeonato: perfil combinado contra taxa de vitória (times com 3+ partidas)")
    for tournament, table in tournament_ranking(matches, features).items():
        print(f"\n== {tournament} (spearman {table['spearman'].iloc[0]})")
        print(table.drop(columns=["spearman"]).head(8).to_string())


if __name__ == "__main__":
    main()
