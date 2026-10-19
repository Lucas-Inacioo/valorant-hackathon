"""Rounds do time: colapsos (três mortes do mesmo time em poucos segundos) e estilo de round (execução rápida, default, sem plant; contato cedo ou tarde).

Uso: python round_style.py
"""
import math

import pandas as pd

from economy import build_rounds_table
from predict import load_matches
from solo_deaths import build_deaths_table

COLLAPSE_WINDOW_S = 10
COLLAPSE_DEATHS = 3
FAST_PLANT_S = 40
EARLY_CONTACT_S = 20
STYLE_ORDER = ["execução rápida", "default", "sem plant"]


def collapse_of(team_deaths, enemy_times):
    """Três mortes do time em 10 s. Colapso quando o time não fez nenhuma kill nessa janela. Retorna a primeira janela encontrada."""
    team_deaths = team_deaths.sort_values("segundos")
    times = list(team_deaths["segundos"])
    result = {"tres_em_10s": False, "colapso": False, "inicio_colapso": math.nan, "regiao_colapso": "", "fase_colapso": ""}
    for start in range(len(times) - COLLAPSE_DEATHS + 1):
        end = start + COLLAPSE_DEATHS - 1
        if times[end] - times[start] > COLLAPSE_WINDOW_S:
            continue
        result["tres_em_10s"] = True
        if any(times[start] <= time <= times[end] for time in enemy_times):
            continue
        window = team_deaths.iloc[start:end + 1]
        return {"tres_em_10s": True, "colapso": True, "inicio_colapso": times[start], "regiao_colapso": window["regiao"].mode().iloc[0], "fase_colapso": window["fase"].iloc[0]}
    return result


def collapse_rows(deaths):
    rows = []
    for (match_id, round_number), round_deaths in deaths.groupby(["match_id", "round"]):
        for team, team_deaths in round_deaths.groupby("time_vitima"):
            enemy_times = round_deaths.loc[round_deaths["time_vitima"] != team, "segundos"]
            rows.append({"match_id": match_id, "round": round_number, "time": team, **collapse_of(team_deaths, enemy_times)})
    return pd.DataFrame(rows)


def attack_style(plant_seconds):
    if math.isnan(plant_seconds):
        return "sem plant"
    return "execução rápida" if plant_seconds <= FAST_PLANT_S else "default"


def score_state(difference):
    if difference < 0:
        return "atrás"
    return "na frente" if difference > 0 else "empate"


def build_round_styles(deaths=None, rounds=None, matches=None):
    """Uma linha por round e time com colapso, estilo do ataque, contato e placar antes do round."""
    deaths = build_deaths_table() if deaths is None else deaths
    rounds = build_rounds_table() if rounds is None else rounds
    matches = load_matches() if matches is None else matches
    per_round = deaths.groupby(["match_id", "round"]).agg(primeira_morte=("segundos", "min"), segundos_plant=("segundos_plant", "first"), mapa=("mapa", "first"))
    styles = rounds.merge(per_round, left_on=["match_id", "round"], right_index=True, how="left")
    styles = styles.merge(collapse_rows(deaths), on=["match_id", "round", "time"], how="left").fillna({"colapso": False, "tres_em_10s": False, "regiao_colapso": "", "fase_colapso": ""})
    styles["colapso"] = styles["colapso"].astype(bool)
    styles["tres_em_10s"] = styles["tres_em_10s"].astype(bool)
    styles["estilo"] = styles["segundos_plant"].map(attack_style)
    styles["contato"] = styles["primeira_morte"].map(lambda seconds: "contato cedo" if seconds <= EARLY_CONTACT_S else "contato tarde")
    styles = styles.sort_values(["match_id", "time", "round"])
    by_team = styles.groupby(["match_id", "time"])
    wins_before = by_team["venceu"].cumsum() - styles["venceu"]
    rounds_before = styles["round"] - 1
    styles["placar"] = (2 * wins_before - rounds_before).map(score_state)
    name_by_match_team = {(row.match_id, color): getattr(row, f"nome_{color.lower()}") for row in matches.itertuples() for color in ["Blue", "Red"]}
    styles["nome_time"] = [name_by_match_team.get((match_id, team), team) for match_id, team in zip(styles["match_id"], styles["time"])]
    return styles


def collapse_summary(styles, group_columns=()):
    """Por grupo: rounds, fração com três mortes em 10 s, fração com colapso (sem kill na janela), vitória sem e com colapso e quando ele começa."""
    rows = []
    groups = styles.groupby(list(group_columns)) if group_columns else [((), styles)]
    for key, group in groups:
        key = key if isinstance(key, tuple) else (key,)
        collapsed = group[group["colapso"]]
        rows.append({**dict(zip(group_columns, key)), "rounds": len(group), "tres_em_10s": group["tres_em_10s"].mean(), "colapsos": group["colapso"].mean(), "venceu_sem_colapso": group.loc[~group["colapso"], "venceu"].mean(), "venceu_com_colapso": collapsed["venceu"].mean(), "inicio_mediano": collapsed["inicio_colapso"].median()})
    table = pd.DataFrame(rows)
    return (table.set_index(list(group_columns)) if group_columns else table).round(3)


def collapse_regions(styles, map_name, min_collapses=5):
    collapsed = styles[styles["colapso"] & (styles["mapa"] == map_name)]
    table = collapsed.groupby(["lado", "regiao_colapso"]).agg(colapsos=("venceu", "size"), pre_plant=("fase_colapso", lambda phase: (phase == "pré-plant").mean()), inicio_mediano=("inicio_colapso", "median"))
    return table[table["colapsos"] >= min_collapses].sort_values("colapsos", ascending=False).round(3)


def style_summary(styles):
    """Ataque por estilo e qualquer lado por contato: rounds e vitória."""
    attack = styles[styles["lado"] == "ataque"].groupby("estilo").agg(rounds=("venceu", "size"), venceu=("venceu", "mean"), plant_mediano=("segundos_plant", "median")).reindex(STYLE_ORDER)
    contact = styles[styles["contato"].notna()].groupby(["lado", "contato"]).agg(rounds=("venceu", "size"), venceu=("venceu", "mean"))
    return attack.round(3), contact.round(3)


def style_by_score(styles):
    """Estilo do ataque conforme o placar antes do round, com a vitória de cada combinação."""
    attack = styles[styles["lado"] == "ataque"]
    shares = pd.crosstab(attack["placar"], attack["estilo"], normalize="index").reindex(columns=STYLE_ORDER)
    wins = pd.crosstab(attack["placar"], attack["estilo"], values=attack["venceu"], aggfunc="mean").reindex(columns=STYLE_ORDER)
    counts = attack.groupby("placar").size().rename("rounds")
    return shares.round(3), wins.round(3), counts


def team_profiles(styles, min_attack_rounds=40):
    """Por time: rounds de ataque, fração de cada estilo, vitória por estilo, colapsos por round e contato cedo na defesa."""
    rows = []
    for name, team_rounds in styles.groupby("nome_time"):
        attack = team_rounds[team_rounds["lado"] == "ataque"]
        defense = team_rounds[team_rounds["lado"] == "defesa"]
        if len(attack) < min_attack_rounds:
            continue
        row = {"time": name, "partidas": team_rounds["match_id"].nunique(), "rounds_ataque": len(attack), "vitoria_ataque": attack["venceu"].mean()}
        for style in STYLE_ORDER:
            style_rounds = attack[attack["estilo"] == style]
            row[f"{style}"] = len(style_rounds) / len(attack)
            row[f"vence {style}"] = style_rounds["venceu"].mean() if len(style_rounds) else math.nan
        row["rápida quando atrás"] = (attack.loc[attack["placar"] == "atrás", "estilo"] == "execução rápida").mean()
        row["rápida na frente"] = (attack.loc[attack["placar"] == "na frente", "estilo"] == "execução rápida").mean()
        row["colapsos por round"] = team_rounds["colapso"].mean()
        row["contato cedo na defesa"] = (defense["contato"] == "contato cedo").mean()
        rows.append(row)
    return pd.DataFrame(rows).set_index("time").sort_values("rounds_ataque", ascending=False).round(3)


def main():
    styles = build_round_styles()
    print(f"Rounds e times: {len(styles)}, com colapso: {int(styles['colapso'].sum())}\n")
    print("Colapsos por lado:")
    print(collapse_summary(styles, ["lado"]).to_string(), "\n")
    print("Colapsos por mapa e lado:")
    print(collapse_summary(styles, ["mapa", "lado"]).sort_values("rounds", ascending=False).to_string(), "\n")
    attack, contact = style_summary(styles)
    print("Estilo do ataque:")
    print(attack.to_string(), "\n")
    print("Contato:")
    print(contact.to_string(), "\n")
    shares, wins, counts = style_by_score(styles)
    print("Estilo conforme o placar (fração, vitória, rounds):")
    print(shares.to_string(), "\n", wins.to_string(), "\n", counts.to_string(), "\n")
    print("Perfil dos times (40+ rounds de ataque):")
    print(team_profiles(styles).head(15).to_string())


if __name__ == "__main__":
    main()
