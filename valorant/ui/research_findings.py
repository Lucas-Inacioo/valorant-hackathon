"""Achados do recorte selecionado, com definições perto dos números."""

import pandas as pd
import streamlit as st

from valorant.analysis.research import pattern_findings
from valorant.ui.presentation import display_table

# Padrões cuja base da frequência não é mais explicada no texto
FREQUENCY_BASE_HIDDEN = {"isolated_death", "numerical_advantage_lost", "isolated_opening_untraded", "collapse"}


def percent(value):
    return f"{value:.1%}".replace(".", ",") if pd.notna(value) else "Sem dados"


def decimal(value, places=2):
    return f"{value:.{places}f}".replace(".", ",") if pd.notna(value) else "Sem dados"


def interval_text(low, high, percentage=False):
    if pd.isna(low) or pd.isna(high):
        return "Intervalo indisponível neste recorte."
    format_value = percent if percentage else decimal
    return f"Intervalo de 95% de {format_value(low)} a {format_value(high)}."


def show_findings(data, match_ids):
    st.subheader("O que se destacou nas partidas")
    openings = data.openings[data.openings["match_id"].isin(match_ids)]
    support = data.support_deaths[data.support_deaths["match_id"].isin(match_ids)].copy()
    support["isolated"] = support["dist_aliado_mais_proximo"].gt(1000)
    near, far = support[~support["isolated"]], support[support["isolated"]]
    rounds = data.team_rounds[data.team_rounds["match_id"].isin(match_ids)]
    observations = data.observations[data.observations["match_id"].isin(match_ids)]
    collapsed = observations[observations["pattern_id"].eq("collapse")][
        ["match_id", "team_id", "round"]
    ].drop_duplicates().assign(collapsed=True)
    round_groups = rounds.merge(collapsed, on=["match_id", "team_id", "round"], how="left")
    flagged = round_groups["collapsed"].eq(True)
    first, second, third = st.columns(3)
    first.metric("Vitória de quem fez o primeiro abate", percent(openings["abriu_venceu"].mean()))
    first.caption(f"{int(openings['abriu_venceu'].sum())} vitórias e {int((~openings['abriu_venceu']).sum())} derrotas em {len(openings)} rounds")
    second.metric("Troca quando há aliado próximo", percent(near["trocada"].mean()))
    second.caption(
        f"Entre {len(near)} primeiras mortes com aliado próximo. Nas {len(far)} distantes, "
        f"a taxa foi {percent(far['trocada'].mean())}. Troca é vingar seu aliado, abatendo o inimigo que o matou em até cinco segundos."
    )
    third.metric("Vitória após três perdas sem resposta", percent(round_groups.loc[flagged, "won_round"].mean()))
    third.caption(
        f"Foram {int(flagged.sum())} rounds com três pessoas diferentes da mesma equipe mortas em até dez "
        "segundos, sem abater adversários nesse intervalo."
    )
    with st.expander("Entender a proximidade e a troca"):
        table = pd.DataFrame([
            {"Situação da primeira vítima": label, "Mortes": len(frame),
             "Troca em até 5 s": frame["trocada"].mean(),
             "Vitória da equipe": frame["venceu_round"].mean()}
            for label, frame in [("Com aliado próximo", near), ("Longe dos aliados", far)]
        ])
        display_table(table, hide_index=True, percentage_columns=["Troca em até 5 s", "Vitória da equipe"])
        st.write(
            "O limite de proximidade foi considerado como 1000 unidades do jogo, cerca de dez metros "
            "considerando o padrão da Unreal, engine em que Valorant é feito. A distância não verifica paredes ou visão."
        )
    with st.expander("Ver os padrões que geram revisão"):
        patterns = pattern_findings(data, match_ids)
        table = patterns[["pattern", "occurrences", "opportunities", "rate", "rounds", "round_win_rate"]].rename(columns={
            "pattern": "Padrão", "occurrences": "Ocorrências", "opportunities": "Casos avaliáveis",
            "rate": "Frequência", "rounds": "Rounds de equipe", "round_win_rate": "Vitória nesses rounds",
        })
        display_table(table, hide_index=True, percentage_columns=["Frequência", "Vitória nesses rounds"])
        for row in patterns.itertuples():
            st.markdown(f"**{row.pattern}**")
            st.write(row.description)
            if row.pattern_id not in FREQUENCY_BASE_HIDDEN:
                st.caption(f"A frequência usa {row.opportunity_label.lower()}.")
