"""Rounds do time: colapsos (três mortes do mesmo time em poucos segundos) e estilo de round (execução rápida, default, sem plant; contato cedo ou tarde).

Uso: python -m valorant.analysis.round_style
"""

import math

import pandas as pd

from valorant.analysis.economy import build_rounds_table
from valorant.data.fields import DEFAULT_DATA_DIR, find_match_files, load_match
from valorant.analysis.prediction import load_matches
from valorant.analysis.deaths import build_deaths_table

COLLAPSE_WINDOW_S = 10
COLLAPSE_DEATHS = 3
FAST_PLANT_S = 40
EARLY_CONTACT_S = 20
STYLE_ORDER = ["execução rápida", "default", "sem plant", "plant excluído"]


COLLAPSE_COLUMNS = [
    "match_id",
    "round",
    "time",
    "tres_em_10s",
    "tres_com_abate",
    "colapso",
    "inicio_colapso",
    "regiao_colapso",
    "fase_colapso",
]


def tactical_deaths(deaths):
    return (
        deaths[deaths["diagnostico_tatico"].eq(True)] if "diagnostico_tatico" in deaths else deaths
    )


def collapse_of(team_deaths, enemy_times):
    """Três vítimas distintas em até 10 s; sem abate adversário pela equipe na janela."""
    team_deaths = tactical_deaths(team_deaths).sort_values(["segundos", "vitima"])
    times = list(team_deaths["segundos"])
    result = {
        "tres_em_10s": False,
        "tres_com_abate": False,
        "colapso": False,
        "inicio_colapso": math.nan,
        "regiao_colapso": "",
        "fase_colapso": "",
    }
    for start in range(len(times)):
        victims = set()
        for end in range(start, len(times)):
            if times[end] - times[start] > COLLAPSE_WINDOW_S:
                break
            victims.add(team_deaths.iloc[end]["vitima"])
            if len(victims) < COLLAPSE_DEATHS:
                continue
            result["tres_em_10s"] = True
            if any(times[start] <= time <= times[end] for time in enemy_times):
                result["tres_com_abate"] = True
            elif not result["colapso"]:
                window = team_deaths.iloc[start : end + 1]
                regions = set(window["regiao"].dropna())
                result.update(
                    colapso=True,
                    inicio_colapso=times[start],
                    regiao_colapso=(
                        next(iter(regions)) if len(regions) == 1 else "múltiplas regiões"
                    ),
                    fase_colapso=window["fase"].iloc[0],
                )
            break
    return result


def collapse_rows(deaths):
    rows = []
    deaths = tactical_deaths(deaths)
    for (match_id, round_number), round_deaths in deaths.groupby(["match_id", "round"]):
        for team, team_deaths in round_deaths.groupby("time_vitima"):
            enemy_times = round_deaths.loc[round_deaths["time_vitima"] != team, "segundos"]
            rows.append(
                {
                    "match_id": match_id,
                    "round": round_number,
                    "time": team,
                    **collapse_of(team_deaths, enemy_times),
                }
            )
    return pd.DataFrame(rows, columns=COLLAPSE_COLUMNS)


def attack_style(plant_seconds):
    if pd.isna(plant_seconds):
        return "sem plant"
    return "execução rápida" if plant_seconds <= FAST_PLANT_S else "default"


def score_state(difference):
    if difference < 0:
        return "atrás"
    return "na frente" if difference > 0 else "empate"


def raw_round_metadata(match_ids=None, data_dir=DEFAULT_DATA_DIR):
    """Plant e mapa diretamente dos campos de round, inclusive rounds sem mortes."""
    rows = []
    for match_file in find_match_files(data_dir):
        match = load_match(match_file)
        info = match["matchInfo"]
        if match_ids is not None and info["matchId"] not in match_ids:
            continue
        for rr in match["roundResults"]:
            seconds = rr.get("plantRoundTime", 0) / 1000 if rr.get("bombPlanter") else math.nan
            rows.append(
                {
                    "match_id": info["matchId"],
                    "round": rr["roundNum"] + 1,
                    "mapa": info["mapId"].rsplit("/", 1)[-1],
                    "segundos_plant": seconds,
                }
            )
    return pd.DataFrame(rows, columns=["match_id", "round", "mapa", "segundos_plant"])


def build_round_styles(deaths=None, rounds=None, matches=None, match_ids=None):
    """Descrição observada do plant e das mortes; não identifica intenção tática."""
    deaths = build_deaths_table(match_ids=match_ids) if deaths is None else deaths
    rounds = build_rounds_table(match_ids=match_ids) if rounds is None else rounds.copy()
    matches = load_matches(match_ids=match_ids) if matches is None else matches
    if match_ids is not None:
        deaths = deaths[deaths["match_id"].isin(match_ids)]
        rounds = rounds[rounds["match_id"].isin(match_ids)]
    per_round = (
        tactical_deaths(deaths)
        .groupby(["match_id", "round"])
        .agg(primeira_morte=("segundos", "min"))
    )
    styles = rounds.merge(per_round, left_on=["match_id", "round"], right_index=True, how="left")
    if "mapa" not in styles and "mapa_interno" in styles:
        styles["mapa"] = styles["mapa_interno"].str.rsplit("/", n=1).str[-1]
    if "mapa" not in styles or "segundos_plant" not in styles:
        raw = raw_round_metadata(set(rounds["match_id"]))
        styles = styles.merge(raw, on=["match_id", "round"], how="left", suffixes=("", "_raw"))
        for column in ["mapa", "segundos_plant"]:
            if f"{column}_raw" in styles:
                styles[column] = styles.pop(f"{column}_raw")
    styles = styles.merge(collapse_rows(deaths), on=["match_id", "round", "time"], how="left")
    styles = styles.fillna(
        {
            "colapso": False,
            "tres_em_10s": False,
            "tres_com_abate": False,
            "regiao_colapso": "",
            "fase_colapso": "",
        }
    )
    for column in ["colapso", "tres_em_10s", "tres_com_abate"]:
        styles[column] = styles[column].astype(bool)
    styles["estilo"] = styles["segundos_plant"].map(attack_style)
    if "plant_valido" in styles:
        styles.loc[
            styles["segundos_plant"].notna() & ~styles["plant_valido"].eq(True), "estilo"
        ] = "plant excluído"
    styles["contato"] = styles["primeira_morte"].map(
        lambda sec: (
            "sem abate adversário"
            if pd.isna(sec)
            else ("contato cedo" if sec <= EARLY_CONTACT_S else "contato tarde")
        )
    )
    styles = styles.sort_values(["match_id", "time", "round"])
    if styles.empty:
        styles["placar"] = pd.Series(dtype=str)
    else:
        wins_before = styles.groupby(["match_id", "time"])["venceu"].cumsum() - styles["venceu"]
        styles["placar"] = (2 * wins_before - (styles["round"] - 1)).map(score_state)
    name_by_match_team = {
        (row.match_id, color): getattr(row, f"nome_{color.lower()}")
        for row in matches.itertuples()
        for color in ["Blue", "Red"]
    }
    styles["nome_time"] = [
        name_by_match_team.get((match_id, team), team)
        for match_id, team in zip(styles["match_id"], styles["time"])
    ]
    return styles


def collapse_summary(styles, group_columns=()):
    """Por grupo: rounds, fração com três mortes em 10 s, fração com colapso (sem kill na janela), vitória sem e com colapso e quando ele começa."""
    rows = []
    groups = styles.groupby(list(group_columns)) if group_columns else [((), styles)]
    for key, group in groups:
        key = key if isinstance(key, tuple) else (key,)
        collapsed = group[group["colapso"]]
        rows.append(
            {
                **dict(zip(group_columns, key)),
                "rounds": len(group),
                "tres_em_10s": group["tres_em_10s"].mean(),
                "tres_com_abate": group["tres_com_abate"].mean(),
                "colapsos": group["colapso"].mean(),
                "venceu_sem_colapso": group.loc[~group["colapso"], "venceu"].mean(),
                "venceu_com_colapso": collapsed["venceu"].mean(),
                "inicio_mediano": collapsed["inicio_colapso"].median(),
            }
        )
    columns = [
        *group_columns,
        "rounds",
        "tres_em_10s",
        "tres_com_abate",
        "colapsos",
        "venceu_sem_colapso",
        "venceu_com_colapso",
        "inicio_mediano",
    ]
    table = pd.DataFrame(rows, columns=columns)
    return (table.set_index(list(group_columns)) if group_columns else table).round(3)


def collapse_regions(styles, map_name, min_collapses=5):
    collapsed = styles[styles["colapso"] & (styles["mapa"] == map_name)]
    table = collapsed.groupby(["lado", "regiao_colapso"]).agg(
        colapsos=("venceu", "size"),
        pre_plant=("fase_colapso", lambda phase: (phase == "pré-plant").mean()),
        inicio_mediano=("inicio_colapso", "median"),
    )
    return (
        table[table["colapsos"] >= min_collapses].sort_values("colapsos", ascending=False).round(3)
    )


def style_summary(styles):
    """Ataque por estilo e qualquer lado por contato: rounds e vitória."""
    attack = (
        styles[styles["lado"] == "ataque"]
        .groupby("estilo")
        .agg(
            rounds=("venceu", "size"),
            venceu=("venceu", "mean"),
            plant_mediano=("segundos_plant", "median"),
        )
        .reindex(STYLE_ORDER)
    )
    contact = (
        styles[styles["contato"].notna()]
        .groupby(["lado", "contato"])
        .agg(rounds=("venceu", "size"), venceu=("venceu", "mean"))
    )
    return attack.round(3), contact.round(3)


def style_by_score(styles):
    """Estilo do ataque conforme o placar antes do round, com a vitória de cada combinação."""
    attack = styles[styles["lado"] == "ataque"]
    shares = pd.crosstab(attack["placar"], attack["estilo"], normalize="index").reindex(
        columns=STYLE_ORDER
    )
    wins = pd.crosstab(
        attack["placar"], attack["estilo"], values=attack["venceu"], aggfunc="mean"
    ).reindex(columns=STYLE_ORDER)
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
        row = {
            "time": name,
            "partidas": team_rounds["match_id"].nunique(),
            "rounds_ataque": len(attack),
            "vitoria_ataque": attack["venceu"].mean(),
        }
        for style in STYLE_ORDER:
            style_rounds = attack[attack["estilo"] == style]
            row[f"{style}"] = len(style_rounds) / len(attack)
            row[f"vence {style}"] = style_rounds["venceu"].mean() if len(style_rounds) else math.nan
        row["rápida quando atrás"] = (
            attack.loc[
                (attack["placar"] == "atrás") & attack["estilo"].isin(STYLE_ORDER[:2]), "estilo"
            ]
            == "execução rápida"
        ).mean()
        row["rápida na frente"] = (
            attack.loc[
                (attack["placar"] == "na frente") & attack["estilo"].isin(STYLE_ORDER[:2]), "estilo"
            ]
            == "execução rápida"
        ).mean()
        row["colapsos por round"] = team_rounds["colapso"].mean()
        row["contato cedo na defesa"] = (defense["contato"] == "contato cedo").mean()
        rows.append(row)
    columns = [
        "time",
        "partidas",
        "rounds_ataque",
        "vitoria_ataque",
        *[column for style in STYLE_ORDER for column in [style, f"vence {style}"]],
        "rápida quando atrás",
        "rápida na frente",
        "colapsos por round",
        "contato cedo na defesa",
    ]
    return (
        pd.DataFrame(rows, columns=columns)
        .set_index("time")
        .sort_values("rounds_ataque", ascending=False)
        .round(3)
    )


def main():
    styles = build_round_styles()
    print(f"Rounds e times: {len(styles)}, com colapso: {int(styles['colapso'].sum())}\n")
    print("Colapsos por lado:")
    print(collapse_summary(styles, ["lado"]).to_string(), "\n")
    print("Colapsos por mapa e lado:")
    print(
        collapse_summary(styles, ["mapa", "lado"])
        .sort_values("rounds", ascending=False)
        .to_string(),
        "\n",
    )
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
