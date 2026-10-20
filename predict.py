"""Associações dentro da partida e avaliação retrospectiva/temporal fora dela.

As medidas calculadas na própria partida descrevem o jogo observado. Somente
only_previous=True usa perfis e escalas disponíveis antes da partida avaliada.
"""
import math
import random
import re
from pathlib import Path

import numpy as np
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


def load_matches(match_ids=None, data_dir=DEFAULT_DATA_DIR):
    from data_quality import eligible_match_ids
    allowed = eligible_match_ids(data_dir) if match_ids is None else set(match_ids)
    rows = []
    for match_file in find_match_files(data_dir):
        match = load_match(match_file)
        if match["matchInfo"]["matchId"] not in allowed:
            continue
        parsed = parse_match_name(match_file)
        names = team_names_by_color(match, parsed)
        won = {team["teamId"]: team["won"] for team in match["teams"]}
        from match_events import round_events, is_enemy_kill, alive_puuids
        from plants import plant_exclusion
        teams = {p["puuid"]: p["teamId"] for p in match["players"]}
        clean_plants = {}
        for rr in match["roundResults"]:
            events = round_events(rr, teams)
            plant = next((e for e in events if e["kind"] == "plant"), None)
            if plant is not None:
                actor_team = teams.get(plant["actor"])
                clean_plants[rr["roundNum"] + 1] = (not plant_exclusion(rr, teams) and not any(is_enemy_kill(e, teams) and e["time_ms"] < plant["time_ms"] for e in events))
        rows.append({
            "plant_limpo_por_round": clean_plants,
            "match_id": match["matchInfo"]["matchId"],
            "campeonato": match_file.relative_to(data_dir).parts[1] if len(match_file.relative_to(data_dir).parts) > 2 else match_file.parent.name,
            "inicio": match["matchInfo"]["gameStartMillis"],
            "nome_blue": names["Blue"],
            "nome_red": names["Red"],
            "venceu_blue": won["Blue"],
            "ataque_por_round": attacking_team_by_round(match),
        })
    return pd.DataFrame(rows, columns=["match_id", "campeonato", "inicio", "nome_blue", "nome_red", "venceu_blue", "ataque_por_round", "plant_limpo_por_round"])


def team_features(deaths, matches):
    """Por partida e time, só taxas sem resultado: abertura, trocas, plant limpo, flanco na defesa, isolamento."""
    attacking = {(row.match_id, round_number): team for row in matches.itertuples() for round_number, team in row.ataque_por_round.items()}
    clean_by_match = matches.set_index("match_id")["plant_limpo_por_round"].to_dict() if "plant_limpo_por_round" in matches else {}
    deaths = deaths[deaths["match_id"].isin(matches["match_id"])].copy()
    if "diagnostico_tatico" in deaths:
        deaths = deaths[deaths["diagnostico_tatico"]].copy()
    if "abate_adversario" in deaths:
        deaths = deaths[deaths["abate_adversario"]].copy()
    deaths["ataque_limpo"] = [attacking.get((match_id, round_number)) for match_id, round_number in zip(deaths["match_id"], deaths["round"])]
    deaths["lado_limpo"] = deaths["time_vitima"].where(deaths["ataque_limpo"].isna(), None)
    deaths["lado_limpo"] = ["?" if attacking_team is None else ("ataque" if victim_team == attacking_team else "defesa") for victim_team, attacking_team in zip(deaths["time_vitima"], deaths["ataque_limpo"])]
    deaths["time_killer"] = deaths["time_vitima"].map(OTHER_TEAM)
    rows = []
    for match_id, match_deaths in deaths.groupby("match_id"):
        first_deaths = match_deaths[match_deaths["abertura_valida"]].drop_duplicates("round") if "abertura_valida" in match_deaths else match_deaths[match_deaths["ordem_da_morte"] == 1]
        for team in ["Blue", "Red"]:
            own = match_deaths[match_deaths["time_vitima"] == team]
            own_with_allies = own[own["aliados_vivos"] > 0]
            own_first = first_deaths[first_deaths["time_vitima"] == team]
            if "primeira_vitima_unica" in own_first:
                own_first = own_first[own_first["primeira_vitima_unica"]]
            attack_rounds = {r for (m, r), t in attacking.items() if m == match_id and t == team}
            clean_plants = sum(bool(clean_by_match[match_id].get(r)) for r in attack_rounds) if match_id in clean_by_match else sum(1 for r in attack_rounds if (first_deaths[first_deaths["round"] == r]["fase"] == "pós-plant").any())
            defense_pre_plant = own[(own["lado_limpo"] == "defesa") & (own["fase"] == "pré-plant") & (own["aliados_vivos"] > 0)]
            rows.append({
                "match_id": match_id,
                "time": team,
                "aberturas_desconhecidas": int(match_deaths.loc[match_deaths.get("abertura_ambigua", pd.Series(False, index=match_deaths.index)), "round"].nunique()),
                "abertura": (first_deaths["time_killer"] == team).mean() if len(first_deaths) else math.nan,
                "troca": own_with_allies["trocada"].mean() if len(own_with_allies) else math.nan,
                "troca_1a_morte": own_first["trocada"].mean() if len(own_first) else math.nan,
                "plant_limpo": clean_plants / len(attack_rounds) if attack_rounds else math.nan,
                "flanco_defesa": (defense_pre_plant["contexto"] == "flanco").mean() if len(defense_pre_plant) else math.nan,
                "isolada": (own_with_allies["dist_aliado_mais_proximo"] > 1000).mean() if len(own_with_allies) else math.nan,
            })
    return pd.DataFrame(rows, columns=["match_id", "time", "aberturas_desconhecidas", *FEATURE_SIGNS])


def match_pairs(matches, features):
    """Uma linha por partida com a diferença Blue menos Red de cada métrica e se Blue venceu."""
    wide = features.pivot(index="match_id", columns="time")
    pairs = matches.set_index("match_id")[["campeonato", "inicio", "nome_blue", "nome_red", "venceu_blue"]].copy()
    for feature in FEATURE_SIGNS:
        pairs[feature] = wide.get((feature, "Blue"), pd.Series(dtype=float)) - wide.get((feature, "Red"), pd.Series(dtype=float))
    return pairs


def combined_score(differences, features=tuple(FEATURE_SIGNS), scales=None):
    """Índice descritivo; escala explícita permite avaliação temporal sem futuro."""
    features = list(features)
    scales = differences[features].std() if scales is None else pd.Series(scales).reindex(features)
    scales = scales.mask(scales == 0, 1.0)
    return differences[features].div(scales).mul(pd.Series(FEATURE_SIGNS)).reindex(columns=features).sum(axis=1, min_count=len(features))


def _accuracy_row(name, predictions, labels, baseline=None, total=None):
    predictions = predictions.dropna()
    labels = labels.reindex(predictions.index)
    if baseline is not None:
        baseline = baseline.reindex(predictions.index)
        valid = baseline.notna() & labels.notna()
        predictions, labels, baseline = predictions[valid], labels[valid], baseline[valid]
    correct = predictions.astype(bool).eq(labels.astype(bool))
    n, rate = len(correct), correct.mean()
    z = 1.96
    denom = 1 + z*z/n if n else math.nan
    center = (rate + z*z/(2*n))/denom if n else math.nan
    width = z*math.sqrt(rate*(1-rate)/n + z*z/(4*n*n))/denom if n else math.nan
    row = {"metrica": name, "partidas": n, "acerto": rate, "ic_baixo": center-width, "ic_alto": center+width, "abstencoes_ou_sem_referencia": (total-n) if total is not None else 0}
    if baseline is not None:
        baseline_correct = baseline.astype(bool).eq(labels.astype(bool))
        delta = correct.astype(float) - baseline_correct.astype(float)
        if n:
            rng = np.random.default_rng(0)
            samples = rng.choice(delta.to_numpy(), (2000, n), replace=True).mean(axis=1)
            low, high = np.quantile(samples, [.025, .975])
        else:
            low = high = math.nan
        row.update(base_mesmos_jogos=baseline_correct.mean(), diferenca_pareada=delta.mean(), diferenca_ic_baixo=low, diferenca_ic_alto=high)
    return row


def _decisions(score):
    """Empate exato/ausência vira abstenção, nunca desempate por cor."""
    return (score > 0).astype(object).where(score.notna() & score.ne(0))


def in_match_accuracy(pairs):
    """Associação pós-jogo; não simula uma previsão anterior à partida."""
    rows = [_accuracy_row(feature, _decisions(pairs[feature]*sign), pairs["venceu_blue"], total=len(pairs)) for feature, sign in FEATURE_SIGNS.items()]
    for name, columns in [("combinada (todas)", list(FEATURE_SIGNS)), ("combinada (abertura + troca)", HEADLINE_FEATURES)]:
        rows.append(_accuracy_row(name, _decisions(combined_score(pairs, columns)), pairs["venceu_blue"], total=len(pairs)))
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
    return pd.DataFrame(profiles, columns=["match_id", "time", "outras", "taxa_vitoria_outras", *FEATURE_SIGNS])


def forecast_accuracy(matches, features, only_previous):
    """Compara modelo/histórico nos mesmos jogos, ambos com abstenção em empate.

    No modo temporal, a escala de cada jogo usa somente diferenças de perfis de
    partidas estritamente anteriores (mínimo três). No outro modo a avaliação é
    retrospectiva fora da partida: jogos futuros podem formar o perfil.
    """
    profiles = team_profiles_out_of_match(matches, features, only_previous)
    if profiles.empty:
        return pd.DataFrame(columns=["metrica", "partidas", "acerto", "ic_baixo", "ic_alto"])
    wide = profiles.pivot(index="match_id", columns="time")
    enough = (wide[("outras", "Blue")] >= MIN_OTHER_MATCHES) & (wide[("outras", "Red")] >= MIN_OTHER_MATCHES)
    labels = matches.set_index("match_id")["venceu_blue"]
    starts = matches.set_index("match_id")["inicio"]
    differences = pd.DataFrame({f: (wide[(f, "Blue")] - wide[(f, "Red")])[enough] for f in FEATURE_SIGNS})
    baseline_score = (wide[("taxa_vitoria_outras", "Blue")] - wide[("taxa_vitoria_outras", "Red")])[enough]
    baseline = _decisions(baseline_score)
    rows = [_accuracy_row(feature, _decisions(differences[feature]*sign), labels, baseline, total=len(matches)) for feature, sign in FEATURE_SIGNS.items()]
    for name, columns in [("combinada (todas)", list(FEATURE_SIGNS)), ("combinada (abertura + troca)", HEADLINE_FEATURES)]:
        if only_previous:
            score = pd.Series(math.nan, index=differences.index)
            for match_id in differences.index:
                past = differences.loc[starts.reindex(differences.index) < starts[match_id], columns].dropna()
                if len(past) >= 3:
                    score.loc[match_id] = combined_score(differences.loc[[match_id]], columns, past.std()).iloc[0]
        else:
            score = combined_score(differences, columns)
        rows.append(_accuracy_row(name, _decisions(score), labels, baseline, total=len(matches)))
    rows.append(_accuracy_row("histórico (jogos elegíveis; empates abstêm)", baseline, labels, total=len(matches)))
    result = pd.DataFrame(rows).round(3)
    result["protocolo"] = "somente anteriores" if only_previous else "retrospectivo fora da partida"
    return result


def permutation_ceiling(pairs, repetitions=500, seed=0):
    """Acerto da combinada com os rótulos embaralhados: o que o acaso consegue com este tamanho de base."""
    decided = pairs.dropna(subset=list(FEATURE_SIGNS))
    score = combined_score(decided[list(FEATURE_SIGNS)])
    decided = decided[score.notna() & score.ne(0)]
    if decided.empty:
        return math.nan, math.nan
    predicted_blue = (score.reindex(decided.index) > 0).to_numpy()
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
    print("2. Avaliação retrospectiva fora da partida: perfil de cada time só nas OUTRAS partidas dele no campeonato (pelo menos 2 para cada lado)")
    print(forecast_accuracy(matches, features, only_previous=False).to_string(index=False), "\n")
    print("3. Previsão só com partidas ANTERIORES no tempo (pelo menos 2 para cada lado)")
    print(forecast_accuracy(matches, features, only_previous=True).to_string(index=False), "\n")
    print("4. Ranking por campeonato: perfil combinado contra taxa de vitória (times com 3+ partidas)")
    for tournament, table in tournament_ranking(matches, features).items():
        print(f"\n== {tournament} (spearman {table['spearman'].iloc[0]})")
        print(table.drop(columns=["spearman"]).head(8).to_string())


if __name__ == "__main__":
    main()
