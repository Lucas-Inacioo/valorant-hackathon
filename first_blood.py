"""Primeira morte do round: quando acontece, quem abre o placar e quanto isso pesa no resultado.

Uso: python first_blood.py
"""
import math

import pandas as pd

from solo_deaths import build_deaths_table

TIME_BINS = [0, 10, 20, 30, 45, 60, 80, 1000]
TIME_LABELS = ["0-10 s", "10-20 s", "20-30 s", "30-45 s", "45-60 s", "60-80 s", "80+ s"]
OPPOSITE_SIDE = {"ataque": "defesa", "defesa": "ataque"}


def first_blood_table(deaths):
    """Uma linha por round com a primeira morte vista pelo lado de quem matou (quem abriu o placar)."""
    first = deaths[deaths["ordem_da_morte"] == 1].copy()
    first["lado_abriu"] = first["lado"].map(OPPOSITE_SIDE)
    first["time_abriu"] = first["time_vitima"].map({"Blue": "Red", "Red": "Blue"})
    first["abriu_venceu"] = ~first["venceu_round"]
    first["antes_do_plant"] = first["segundos_plant"].isna() | (first["segundos"] < first["segundos_plant"])
    first["faixa"] = pd.cut(first["segundos"], TIME_BINS, labels=TIME_LABELS)
    return first[["match_id", "arquivo", "mapa", "round", "segundos", "faixa", "lado_abriu", "time_abriu", "vitima", "vitima_x", "vitima_y", "killer_x", "killer_y", "trocada", "antes_do_plant", "abriu_venceu", "venceu_partida"]]


def win_rate_by_time(first):
    """Por lado de quem abriu e faixa de tempo: quantos rounds e quanto o time que abriu venceu."""
    return first.groupby(["lado_abriu", "faixa"], observed=True).agg(rounds=("round", "size"), abriu_venceu=("abriu_venceu", "mean"), trocada=("trocada", "mean")).round(3)


def who_opens_by_time(first):
    """Por faixa de tempo: fração dos rounds em que o ataque abriu o placar."""
    opened_by_attack = first["lado_abriu"] == "ataque"
    return opened_by_attack.groupby(first["faixa"], observed=True).agg(["size", "mean"]).rename(columns={"size": "rounds", "mean": "ataque_abriu"}).round(3)


def wilson_interval(successes, total, z=1.96):
    """Intervalo de 95% de uma proporção, que se comporta bem com poucas amostras."""
    if total == 0:
        return math.nan, math.nan
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    half_width = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return centre - half_width, centre + half_width


def difference_interval(proportion_a, total_a, proportion_b, total_b, z=1.96):
    """Intervalo de 95% da diferença entre duas proporções, aproximação normal."""
    if total_a == 0 or total_b == 0:
        return math.nan, math.nan
    half_width = z * math.sqrt(proportion_a * (1 - proportion_a) / total_a + proportion_b * (1 - proportion_b) / total_b)
    return proportion_a - proportion_b - half_width, proportion_a - proportion_b + half_width


def summary_by_map(first):
    """Por mapa: quanto o ataque abre, quanto vence e quanto a abertura do ataque pesa (vitória se abre menos vitória se a defesa abre)."""
    rows = []
    for map_name, group in first.groupby("mapa"):
        attack_opened = group["lado_abriu"] == "ataque"
        attack_won = attack_opened == group["abriu_venceu"]
        opened_count, total = int(attack_opened.sum()), len(group)
        win_if_attack_opens = attack_won[attack_opened].mean()
        win_if_defense_opens = attack_won[~attack_opened].mean()
        open_low, open_high = wilson_interval(opened_count, total)
        impact_low, impact_high = difference_interval(win_if_attack_opens, opened_count, win_if_defense_opens, total - opened_count)
        rows.append({
            "mapa": map_name,
            "rounds": total,
            "mediana_segundos": group["segundos"].median(),
            "ataque_abriu": attack_opened.mean(),
            "ataque_abriu_ic95": f"{open_low:.2f} a {open_high:.2f}",
            "ataque_vence": attack_won.mean(),
            "ataque_vence_se_abre": win_if_attack_opens,
            "ataque_vence_se_defesa_abre": win_if_defense_opens,
            "impacto_da_abertura": win_if_attack_opens - win_if_defense_opens,
            "impacto_ic95_baixo": impact_low,
            "impacto_ic95_alto": impact_high,
        })
    return pd.DataFrame(rows).sort_values("rounds", ascending=False).set_index("mapa").round(3)


def plant_summary(first):
    """Primeira morte antes ou depois do plant, por lado de quem abriu."""
    return first.groupby(["antes_do_plant", "lado_abriu"]).agg(rounds=("round", "size"), abriu_venceu=("abriu_venceu", "mean")).round(3)


def main():
    first = first_blood_table(build_deaths_table())
    print(f"Rounds com pelo menos uma morte: {len(first)}; mediana da primeira morte: {first['segundos'].median():.1f} s; o time que abre vence {first['abriu_venceu'].mean():.1%}\n")
    print("Quem abre vence, por lado e faixa de tempo:")
    print(win_rate_by_time(first).to_string(), "\n")
    print("Quem abre o placar por faixa de tempo:")
    print(who_opens_by_time(first).to_string(), "\n")
    print("Por mapa:")
    print(summary_by_map(first).to_string(), "\n")
    print("Antes ou depois do plant:")
    print(plant_summary(first).to_string())


if __name__ == "__main__":
    main()
