"""Evidências para interpretar a revisão, sem criar uma pontuação de culpa."""

import pandas as pd
import streamlit as st

from valorant.analysis.economy import win_rate_by_loadout
from valorant.analysis.fights import save_effect
from valorant.analysis.post_match import PATTERNS
from valorant.analysis.review_evidence import (
    defuse_survival_comparison, first_death_comparison, pattern_round_comparison,
    plant_time_comparison, selected_rows,
)
from valorant.ui.data import AnalysisData
from valorant.ui.post_match_selection import open_dashboard_evidence
from valorant.ui.presentation import display_table
from valorant.ui.research_findings import decimal, percent


def show_contrast(values, description):
    difference, low, high = values
    if pd.isna(difference):
        st.caption("A diferença precisa de casos nos dois grupos com resultado conhecido.")
        return
    text = f"{description} {decimal(100 * difference, 1)} pontos percentuais."
    if pd.notna(low) and pd.notna(high):
        text += f" O intervalo de 95% vai de {decimal(100 * low, 1)} a {decimal(100 * high, 1)} pontos."
    else:
        text += " Há poucos dados para calcular o intervalo entre partidas."
    st.caption(text)


def show_review_comparisons(data, match_ids):
    st.subheader("Por que vale rever esses lances")
    st.write(
        "Comparação do resultado dos rounds em que cada situação apareceu."
    )
    trades, collapses, advantage = st.tabs(["Primeira morte e troca", "Sequências sem resposta", "Vantagem numérica"])
    with trades:
        table, contrasts = first_death_comparison(data, match_ids)
        display_table(table.drop(columns="Com resultado").rename(columns={"Casos": "Primeiras mortes"}), hide_index=True,
                      percentage_columns=["Vitória da equipe"])
        st.write(
            "A chance de vitória considerada é da equipe que sofreu a primeira morte. A troca acontece quando "
            "ela abate o autor dessa morte em até cinco segundos e há um aliado próximo quando a distância "
            "registrada é de até 1000 unidades do jogo."
        )
        for label, contrast in contrasts:
            show_contrast(contrast, f"{label}, a diferença de vitórias entre com troca e sem troca foi de")
        st.caption("A proximidade não verifica paredes ou linha de tiro.")
    with collapses:
        table, contrast = pattern_round_comparison(data, match_ids, "collapse")
        display_table(table.drop(columns="Com resultado").rename(columns={"Casos": "Rounds de equipe"}), hide_index=True,
                      percentage_columns=["Vitória da equipe"])
        st.write(
            "A sequência diz respeito a três jogadores diferentes da equipe morrerem em até 10 segundos "
            "sem abater adversários."
        )
        show_contrast(contrast, "A diferença de vitórias entre com a sequência e sem ela foi de")
    with advantage:
        table, _ = pattern_round_comparison(data, match_ids, "numerical_advantage_lost")
        # A linha sem perda fica de fora porque quase repete o resultado do round
        display_table(table.iloc[:1].drop(columns="Com resultado").rename(columns={"Casos": "Rounds de equipe"}), hide_index=True,
                      percentage_columns=["Vitória da equipe"])
        flagged = table.iloc[0]
        st.write(
            "Há vantagem numérica quando a equipe tem mais jogadores vivos que a adversária. "
            "Entram apenas rounds em que essa vantagem foi observada. A perda é registrada quando "
            "ela deixa de existir nos instantes disponíveis, inclusive após ressurreições."
        )
        st.write(
            f"A equipe ainda venceu {int(flagged['Vitórias'])} dos {int(flagged['Com resultado'])} "
            f"rounds com perda da vantagem, ou {percent(flagged['Vitória da equipe'])}. "
            "Esses exemplos podem mostrar recuperação e também decisões que merecem revisão."
        )
        st.caption(
            "Sem perda registrada não significa vantagem mantida em todos os instantes. Esse grupo está "
            "muito próximo da própria definição do resultado, por isso a diferença entre os grupos não "
            "mede quantos rounds uma decisão teria salvado."
        )


def show_equipment_context(scoped):
    panel = st.expander("Entender o equipamento e o round seguinte", key="dashboard_equipment", on_change="rerun")
    if not panel.open:
        return
    with panel:
        rounds = scoped.rounds()
        _, differences = win_rate_by_loadout(rounds)
        st.markdown("**Equipamento inicial e resultado do round**")
        display_table(differences.reset_index().rename(columns={
            "faixa_diferenca": "Equipamento da equipe menos o adversário",
            "rounds": "Rounds de equipe", "vitoria": "Vitória da equipe",
        }), hide_index=True, percentage_columns=["Vitória da equipe"])
        st.write(
            "O valor soma o equipamento inicial dos cinco jogadores. A diferença compara as duas equipes "
            "em créditos e a letra k significa mil. Esse valor não é o gasto do round nem o valor perdido "
            "numa morte. Antes de avaliar um lance, veja se as equipes começaram com recursos parecidos."
        )
        st.markdown("**O que aconteceu depois dos rounds perdidos**")
        following = save_effect(rounds).reset_index().rename(columns={
            "sobreviventes": "Sobreviventes da equipe", "rounds": "Rounds perdidos",
            "loadout": "Equipamento inicial médio",
            "loadout_seguinte": "Equipamento inicial médio no seguinte",
            "venceu_seguinte": "Vitória no round seguinte",
        })
        display_table(following, hide_index=True, percentage_columns=["Vitória no round seguinte"])
        st.caption(
            "Entram derrotas com round consecutivo disponível, sem passagem de metade ou prorrogação. "
            "Sobreviventes são os jogadores vivos ao final. Grupos pequenos aparecem com sua contagem. "
            "As médias não demonstram que guardar uma arma causou a diferença, pois os grupos já "
            "podiam ter equipamento e força diferentes."
        )


def show_postplant_context(scoped):
    panel = st.expander("Entender a sobrevivência e o tempo no pós-plant", key="dashboard_postplant", on_change="rerun")
    if not panel.open:
        return
    with panel:
        st.markdown("**Quem ainda estava vivo quando a spike foi desarmada**")
        display_table(defuse_survival_comparison(scoped.setups()), hide_index=True,
                      percentage_columns=["Fração dos desarmes"])
        st.write(
            "Pós-plant é o período depois de plantar a spike. A tabela conta somente plants válidos "
            "que terminaram em desarme e usa os atacantes registrados naquele instante. Ela ajuda a "
            "escolher entre rever as mortes anteriores e rever a posição dos atacantes ainda vivos."
        )
        st.caption(
            "A fração entre os desarmes não é a chance de desarme após a morte do último atacante. "
            "O registro também não revela a intenção do jogador ou se ele tinha linha de tiro."
        )
        st.markdown("**O tempo do plant junto de quem estava vivo**")
        display_table(plant_time_comparison(scoped.plants()), hide_index=True, percentage_columns=[
            "Vitória do ataque", "Referência por jogadores vivos",
        ])
        st.write(
            "O tempo é contado desde o início do round. A referência por jogadores vivos é a taxa de "
            "vitória do ataque nos plants deste recorte com a mesma quantidade de atacantes e defensores "
            "vivos. A tabela mostra a média dessas referências em cada grupo de tempo. "
            "A diferença subtrai essa média da taxa observada e é expressa em pontos percentuais."
        )
        st.caption(
            "A referência usa os próprios rounds selecionados. Ela descreve a composição dos grupos "
            "e não é uma previsão independente nem uma prova de que plantar mais rápido melhora o resultado."
        )


def show_examples(data, match_ids):
    panel = st.expander("Abrir exemplos dos padrões de revisão", key="dashboard_examples", on_change="rerun")
    if not panel.open:
        return
    with panel:
        observations = selected_rows(data.observations, match_ids)
        if observations.empty:
            st.info("Não há ocorrências de revisão neste recorte.")
            return
        patterns = sorted(observations["pattern_id"].unique(), key=lambda key: PATTERNS[key].name)
        if st.session_state.get("dashboard_example_pattern") not in patterns:
            st.session_state["dashboard_example_pattern"] = patterns[0]
        pattern = st.selectbox("Padrão para ver no replay", patterns, format_func=lambda key: PATTERNS[key].name,
                               key="dashboard_example_pattern")
        outcome = st.selectbox("Resultado dos exemplos", ["Rounds perdidos", "Rounds vencidos", "Todos os resultados"],
                               key="dashboard_example_outcome")
        chosen = observations[observations["pattern_id"].eq(pattern)]
        if outcome != "Todos os resultados":
            chosen = chosen[chosen["won_round"].eq(outcome == "Rounds vencidos")]
        if chosen.empty:
            st.info("Não há exemplos com esse resultado no recorte.")
            return
        teams = data.team_matches[["match_id", "team_id", "team_name", "arquivo"]]
        chosen = chosen.merge(teams, on=["match_id", "team_id"], validate="many_to_one").sort_values(
            ["arquivo", "team_name", "round", "event_index"])
        team_names = sorted(chosen["team_name"].unique())
        if st.session_state.get("dashboard_example_team") not in team_names:
            st.session_state["dashboard_example_team"] = team_names[0]
        team_name = st.selectbox("Equipe dos exemplos", team_names, key="dashboard_example_team")
        chosen = chosen[chosen["team_name"].eq(team_name)]
        examples = {f"{row['match_id']}|{row['observation_id']}": row for row in chosen.to_dict("records")}
        if st.session_state.get("dashboard_example") not in examples:
            st.session_state["dashboard_example"] = next(iter(examples))
        def label(key):
            row = examples[key]
            return f"{row['team_name']} no round {row['round']}, evento {int(row['event_index']) + 1}. {row['arquivo']}"
        selected = st.selectbox("Lance para abrir", list(examples), format_func=label, key="dashboard_example")
        row = examples[selected]
        st.write(PATTERNS[pattern].question)
        st.caption(f"Há {len(chosen)} ocorrências desta equipe em {chosen['match_id'].nunique()} partidas neste filtro. Um round pode ter mais de uma ocorrência.")
        st.button("Rever este lance", key="dashboard_open_example", on_click=open_dashboard_evidence,
                  args=(row["arquivo"], row))


def show_evidence_context(context, data, match_ids):
    show_review_comparisons(data, match_ids)
    scoped = AnalysisData(context.data.data_version, tuple(sorted(match_ids)))
    show_equipment_context(scoped)
    show_postplant_context(scoped)
    show_examples(data, match_ids)
