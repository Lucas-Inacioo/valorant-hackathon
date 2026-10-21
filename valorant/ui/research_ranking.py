"""Ranking de revisão, comparação com desempenho e acesso às partidas."""

import altair as alt
import pandas as pd
import streamlit as st

from valorant.analysis.first_blood import wilson_interval
from valorant.analysis.rank_comparison import compare_rankings
from valorant.analysis.research import team_ranking
from valorant.ui.presentation import display_table
from valorant.ui.research_findings import decimal, interval_text, percent

PERFORMANCE = {"Vitórias em rounds": "round_win_rate", "Vitórias em partidas": "match_win_rate"}


def open_team_review(filename, team_id):
    st.session_state["section"] = "Análise pós-jogo"
    st.session_state["pos_match"] = filename
    st.session_state["review_team"] = team_id
    st.session_state["review_view"] = "Equipe"
    for key in ["review_return_to", "review_event_focus", "review_occurrence_id"]:
        st.session_state.pop(key, None)


def show_team_link(team_matches, ranking):
    st.subheader("Abrir as partidas de uma equipe")
    options = ranking["team_name"].tolist()
    if st.session_state.get("dashboard_team") not in options:
        st.session_state["dashboard_team"] = options[0]
    team = st.selectbox("Equipe para revisar", options, key="dashboard_team")
    matches = team_matches[team_matches["team_name"].eq(team)].sort_values("inicio", ascending=False)
    labels = {}
    for row in matches.itertuples():
        opponent = team_matches[
            team_matches["match_id"].eq(row.match_id) & team_matches["team_id"].ne(row.team_id)
        ].iloc[0]["team_name"]
        labels[row.arquivo] = f"{row.inicio:%d/%m} contra {opponent}. {row.review_events} lances para rever"
    if st.session_state.get("dashboard_match") not in labels:
        st.session_state["dashboard_match"] = next(iter(labels))
    filename = st.selectbox("Partida para revisar", list(labels), format_func=labels.get, key="dashboard_match")
    team_id = matches[matches["arquivo"].eq(filename)].iloc[0]["team_id"]
    st.button("Abrir análise pós-jogo", key="dashboard_open_review", on_click=open_team_review, args=(filename, team_id))


def comparison_charts(ranking, performance):
    left, right = st.columns(2)
    left.markdown("**Equipes com mais lances por 100 rounds**")
    bars = alt.Chart(ranking.head(10)).mark_bar(color="#7f7f7f").encode(
        x=alt.X("review_per_100:Q", title="Lances por 100 rounds"),
        y=alt.Y("team_name:N", title=None, sort="-x", axis=alt.Axis(labelLimit=220)),
        tooltip=[
            alt.Tooltip("team_name:N", title="Equipe"),
            alt.Tooltip("review_per_100:Q", title="Lances por 100 rounds", format=".1f"),
            alt.Tooltip("matches:Q", title="Partidas", format=".0f"),
        ],
    ).properties(height=300)
    left.altair_chart(bars, width="stretch")
    right.markdown("**Frequência de revisão e desempenho**")
    y_label = "Vitórias em rounds" if performance == "round_win_rate" else "Vitórias em partidas"
    points = alt.Chart(ranking).mark_circle(opacity=.75, color="#1f77b4").encode(
        x=alt.X("review_per_100:Q", title="Lances por 100 rounds"),
        y=alt.Y(f"{performance}:Q", title=y_label, scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format=".0%")),
        size=alt.Size("matches:Q", title="Partidas", scale=alt.Scale(range=[35, 230]),
                      legend=alt.Legend(format=".0f")),
        tooltip=[
            alt.Tooltip("team_name:N", title="Equipe"),
            alt.Tooltip("review_per_100:Q", title="Lances por 100 rounds", format=".1f"),
            alt.Tooltip("review_events:Q", title="Lances para rever", format=".0f"),
            alt.Tooltip("matches:Q", title="Partidas", format=".0f"),
            alt.Tooltip("round_win_rate:Q", title="Vitórias em rounds", format=".1%"),
            alt.Tooltip("match_win_rate:Q", title="Vitórias em partidas", format=".1%"),
        ],
    ).properties(height=300).interactive()
    right.altair_chart(points, width="stretch")


def show_methods(team_matches, ranking, comparison, performance):
    with st.expander("Como ler a comparação e a incerteza"):
        st.write(
            "Spearman compara as ordens de duas medidas e dá a mesma posição média aos empates. "
            "Aqui comparamos menos lances por 100 rounds com mais vitórias. O valor vai de menos um a um. "
            "Um significa a mesma ordem, zero indica ausência de relação monotônica e menos um indica ordens opostas. "
            "Com menos de três equipes ou sem variação em alguma medida, o valor fica indisponível."
        )
        st.write(
            "A concordância compara os pares de equipes com desempenho diferente. Ela conta em quantos pares "
            "a equipe com menos lances teve mais vitórias. Empate na frequência dos lances vale meio acerto. "
            "Empates de desempenho ficam fora. Uma concordância de 50% corresponde à referência de uma ordem aleatória."
        )
        st.caption(
            f"Foram {comparison.comparable_pairs} pares comparáveis, {comparison.performance_ties} pares com "
            f"desempenho empatado e {comparison.review_ties} empates de frequência entre os pares comparáveis. "
            "Esses pares compartilham equipes e não são observações independentes."
        )
        st.write(
            "Os intervalos de 95% usam 500 reamostragens de partidas inteiras, mantendo as duas equipes juntas. "
            "O grupo de equipes é o mesmo do ranking original. Uma equipe que fica sem jogos em uma reamostragem "
            "não entra naquela conta. A conta não trata cada round como um jogo independente. "
            "Os intervalos descrevem esta agenda e não corrigem a força dos adversários ou mudanças de elenco."
        )
        st.caption(f"Foram {comparison.valid_resamples} reamostragens com Spearman calculável.")
        st.write(
            "AUC avalia escores de classificação contra classes conhecidas. Aqui o desempenho é uma taxa, "
            "então usamos Spearman e concordância sem criar uma divisão arbitrária de equipes boas e ruins. "
            "Todas as medidas usam as mesmas partidas já encerradas. A comparação não é uma avaliação de previsão."
        )
        st.markdown(
            "Consulte as definições na [documentação de Spearman](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html) "
            "e na [documentação de ROC-AUC](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html)."
        )
        sensitivity = []
        for minimum in [1, 3, 5]:
            result = compare_rankings(team_ranking(team_matches, minimum), performance)
            sensitivity.append({"Mínimo de partidas": minimum, "Equipes": result.teams,
                                "Spearman": result.spearman, "Concordância": result.concordance})
        st.markdown("**O resultado muda ao exigir mais partidas?**")
        display_table(pd.DataFrame(sensitivity), hide_index=True, percentage_columns=["Concordância"])
        intervals = ranking[["team_name", "matches", "decided_matches", "match_wins", "match_win_rate"]].copy()
        limits = [wilson_interval(row.match_wins, row.decided_matches) for row in intervals.itertuples()]
        intervals["Limite inferior de 95%"] = [item[0] for item in limits]
        intervals["Limite superior de 95%"] = [item[1] for item in limits]
        st.markdown("**Quanto sabemos sobre as vitórias em partidas?**")
        display_table(
            intervals.rename(columns={"team_name": "Equipe", "matches": "Partidas", "decided_matches": "Com vencedor", "match_wins": "Vitórias", "match_win_rate": "Taxa de vitória"}),
            hide_index=True,
            percentage_columns=["Taxa de vitória", "Limite inferior de 95%", "Limite superior de 95%"],
        )
        st.caption(
            "Os intervalos individuais de Wilson tratam partidas como tentativas independentes e servem como descrição. "
            "A repetição de adversários e o calendário limitam essa aproximação. "
            "A cobertura de posição na tabela principal conta mortes com aliado vivo em que foi possível avaliar isolamento."
        )


def show_ranking(context, team_matches, tournament):
    st.subheader("Ranking das equipes por lances a revisar")
    st.write(
        "Um lance é um evento com pelo menos um dos padrões de revisão. Quando três padrões apontam o mesmo evento "
        "da mesma equipe, ele conta uma vez. Entram lances de rounds vencidos e perdidos. Acertos e condições como "
        "equipamento inferior ficam fora dessa contagem."
    )
    first, second = st.columns(2)
    minimum = int(first.number_input("Mínimo de partidas por equipe", min_value=1, value=3, step=1, key="dashboard_minimum"))
    label = second.selectbox("Desempenho usado na comparação", list(PERFORMANCE), key="dashboard_performance")
    performance = PERFORMANCE[label]
    ranking = team_ranking(team_matches, minimum)
    total_teams = team_matches["team_name"].nunique()
    st.caption(
        f"O recorte tem {total_teams} equipes. Entraram {len(ranking)} no ranking e {total_teams - len(ranking)} "
        "ficaram abaixo do mínimo. A frequência é o total de lances dividido pelos rounds jogados, vezes cem. "
        "Ela pode passar de cem, pois um round pode ter vários lances."
    )
    if ranking.empty:
        st.info("Nenhuma equipe atingiu o mínimo de partidas. Reduza o mínimo ou amplie os filtros.")
        return
    with st.spinner("Comparando as equipes e a variação entre partidas"):
        comparison = context.data.rank_comparison(tournament, minimum, performance)
    baseline = compare_rankings(ranking.assign(review_per_100=ranking["deaths_per_100"]), performance)
    columns = st.columns(3)
    columns[0].metric("Spearman entre menos lances e mais vitórias", decimal(comparison.spearman))
    columns[0].caption(interval_text(comparison.spearman_low, comparison.spearman_high))
    columns[1].metric("Concordância entre pares de equipes", percent(comparison.concordance))
    columns[1].caption(interval_text(comparison.concordance_low, comparison.concordance_high, percentage=True))
    columns[2].metric("Spearman apenas pela frequência de mortes", decimal(baseline.spearman))
    columns[2].caption("Referência com menos mortes por 100 rounds, nas mesmas equipes. Essa conta não usa os padrões de revisão.")
    if comparison.teams < 5:
        st.info("Há poucas equipes neste recorte. Uma mudança pequena nos jogos pode alterar muito a ordenação.")
    st.caption(
        "Valores maiores nas duas medidas de concordância indicam mais alinhamento entre poucos lances e bom desempenho. "
        "A frequência de mortes também acompanha o resultado, então uma correlação alta dos lances não demonstra ganho de previsão."
    )
    st.caption(
        "A referência inicial usa vitórias em rounds porque poucas partidas produzem muitos empates na taxa de vitória em jogos. "
        "Rounds da mesma partida compartilham condições. A incerteza continua sendo avaliada por partida. "
        "Os torneios têm adversários diferentes. Use o recorte por torneio para consultar cada competição."
    )
    comparison_charts(ranking, performance)
    ranking["performance_rank"] = ranking[performance].rank(ascending=False, method="min")
    table = ranking[["review_rank", "team_name", "review_events", "review_per_100", "matches", "rounds", "review_round_rate", "round_win_rate", "match_win_rate", "performance_rank", "position_coverage"]].rename(columns={
        "review_rank": "Posição por lances", "team_name": "Equipe", "review_events": "Lances para rever",
        "review_per_100": "Lances por 100 rounds", "matches": "Partidas", "rounds": "Rounds",
        "review_round_rate": "Rounds com revisão", "round_win_rate": "Vitórias em rounds",
        "match_win_rate": "Vitórias em partidas", "performance_rank": "Posição no desempenho",
        "position_coverage": "Cobertura de posição",
    })
    st.caption("A lista começa com mais lances por 100 rounds. No desempenho, a primeira posição é a maior taxa de vitória. Posições empatadas são preservadas.")
    display_table(table, hide_index=True, percentage_columns=["Rounds com revisão", "Vitórias em rounds", "Vitórias em partidas", "Cobertura de posição"])
    st.download_button("Baixar ranking em CSV", data=table.to_csv(index=False).encode("utf-8-sig"), file_name="ranking_equipes.csv", mime="text/csv", key="dashboard_download")
    show_methods(team_matches, ranking, comparison, performance)
    show_team_link(team_matches, ranking)
