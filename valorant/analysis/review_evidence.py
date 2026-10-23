"""Comparações descritivas dos lances, usando as tabelas das outras análises."""

import pandas as pd

from valorant.analysis.factors import cluster_contrast

ROUND_KEYS = ["match_id", "team_id", "round"]


def selected_rows(frame, match_ids):
    return frame[frame["match_id"].isin(match_ids)].copy()


def outcome_summary(frame, outcome):
    """Resultados ausentes não viram derrotas nem entram na taxa de vitória."""
    known = frame[outcome].dropna()
    wins = int(known.eq(True).sum())
    return {
        "Casos": len(frame), "Partidas": frame["match_id"].nunique(),
        "Com resultado": len(known), "Vitórias": wins,
        "Derrotas": int(known.eq(False).sum()),
        "Vitória da equipe": wins / len(known) if len(known) else float("nan"),
    }


def first_death_comparison(data, match_ids):
    support = selected_rows(data.support_deaths, match_ids)
    support = support[support["dist_aliado_mais_proximo"].notna()]
    table = pd.DataFrame([
        {"Resposta": label, **outcome_summary(support[support["trocada"].eq(traded)], "venceu_round")}
        for traded, label in [(True, "Com troca"), (False, "Sem troca")]
    ])
    return table, cluster_contrast(support, "trocada", "venceu_round", repetitions=500)


def pattern_round_groups(data, match_ids, pattern_id):
    """Um round de equipe por linha, limitado às oportunidades do padrão."""
    rounds = selected_rows(data.team_rounds, match_ids).drop_duplicates(ROUND_KEYS)
    opportunities = selected_rows(data.opportunities, match_ids)
    eligible = opportunities[opportunities["pattern_id"].eq(pattern_id)][ROUND_KEYS].drop_duplicates()
    rounds = rounds.merge(eligible, on=ROUND_KEYS, how="inner", validate="one_to_one")
    observations = selected_rows(data.observations, match_ids)
    flagged = observations[observations["pattern_id"].eq(pattern_id)][ROUND_KEYS].drop_duplicates()
    rounds = rounds.merge(flagged.assign(observed=True), on=ROUND_KEYS, how="left", validate="one_to_one")
    rounds["observed"] = rounds["observed"].eq(True)
    return rounds


def pattern_round_comparison(data, match_ids, pattern_id):
    rounds = pattern_round_groups(data, match_ids, pattern_id)
    labels = {
        "collapse": ("Com três perdas sem resposta", "Sem essa sequência registrada"),
        "numerical_advantage_lost": ("Ficou atrás depois de estar à frente", "Sem perda da vantagem registrada"),
    }
    table = pd.DataFrame([
        {"Situação": label, **outcome_summary(rounds[rounds["observed"].eq(observed)], "won_round")}
        for observed, label in zip([True, False], labels[pattern_id])
    ])
    contrast = cluster_contrast(rounds, "observed", "won_round", repetitions=500)
    return table, contrast


def plant_time_comparison(plants):
    """Recalcula a referência por vivos no recorte recebido, sem herdar a global."""
    valid = plants[plants["plant_valido"].eq(True)].copy()
    keys = ["ataque_vivos", "defesa_vivos"]
    valid["alive_reference"] = valid.groupby(keys)["ataque_venceu"].transform("mean")
    rows = []
    for early, label in [(True, "Plant até 40 segundos"), (False, "Plant depois de 40 segundos")]:
        group = valid[valid["segundos_plant"].notna() & valid["segundos_plant"].le(40).eq(early)]
        rate = group["ataque_venceu"].mean()
        reference = group["alive_reference"].mean()
        rows.append({
            "Momento do plant": label, "Plants": len(group), "Partidas": group["match_id"].nunique(),
            "Vitória do ataque": rate, "Referência por jogadores vivos": reference,
            "Diferença em pontos percentuais": 100 * (rate - reference),
        })
    return pd.DataFrame(rows)


def defuse_survival_comparison(setups):
    defused = setups[setups["plant_valido"].eq(True) & setups["defusada"].eq(True)]
    rows = []
    alive = defused["atacantes_vivos_no_defuse"]
    for label, mask in [
        ("Nenhum atacante vivo", alive.eq(0)),
        ("Ao menos um atacante vivo", alive.gt(0)),
        ("Sem informação de vivos", alive.isna()),
    ]:
        group = defused[mask]
        rows.append({"No instante do desarme": label, "Desarmes": len(group),
                     "Partidas": group["match_id"].nunique(),
                     "Fração dos desarmes": len(group) / len(defused) if len(defused) else float("nan")})
    return pd.DataFrame(rows)
