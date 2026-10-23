"""Regressão integrada de Streamlit, ativada com VALORANT_RUN_APPTEST=1.

Usa um único processo para compartilhar os caches entre cenários. Confere
navegação, filtros e consultas que já falharam com partidas da base local.
"""

import contextlib
import hashlib
import json
import os
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = Path(os.environ.get("VALORANT_APP_REPORT", "/tmp/valorant-app-validation.txt"))


def source_digest():
    """Inclui os módulos reais, pois o ponto de entrada só inicia a interface."""
    digest = hashlib.sha256()
    for source in [ROOT / "app.py", *sorted((ROOT / "valorant").rglob("*.py"))]:
        digest.update(str(source.relative_to(ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(source.read_bytes())
    return digest.hexdigest()


@unittest.skipUnless(
    os.environ.get("VALORANT_RUN_APPTEST") == "1",
    "AppTest completo é opt-in com VALORANT_RUN_APPTEST=1",
)
class AppIntegrationTests(unittest.TestCase):
    def test_all_sections_and_audited_filter_regressions(self):
        from streamlit.testing.v1 import AppTest

        from valorant.ui.navigation import EXPLORATORY_SECTIONS, MAIN_AREAS, SECTIONS
        from valorant.ui.presentation import field_label

        report, failures = [], []
        source_before = source_digest()
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
        log_path = Path("/tmp/valorant-postmatch-apptest-stderr.log")
        log = log_path.open("w", encoding="utf-8")

        def save():
            REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

        def run(label, action=None, check=None):
            passed = False
            try:
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    if action:
                        action()
                    app.run(timeout=180)
                errors = [exception.message for exception in app.exception]
                if errors:
                    for exception in app.exception:
                        report.extend(f"  {line}" for line in exception.stack_trace)
                    raise AssertionError(" | ".join(errors))
                if check:
                    check()
                report.append(f"PASS | {label}")
                passed = True
            except Exception as error:
                failures.append(f"{label}: {type(error).__name__}: {error}")
                report.append(f"FAIL | {failures[-1]}")
            save()
            print(report[-1], flush=True)
            return passed

        def widget(kind, label):
            return next(item for item in getattr(app, kind) if item.label == label)

        def section(name):
            app.session_state["section"] = name

        def tournaments(values):
            widget("multiselect", "Torneios").set_value(values)

        def selected_match_file():
            filename = app.selectbox(key="pos_match").value
            return next((ROOT / "data").rglob(filename))

        def selected_team_players():
            match = json.loads(selected_match_file().read_text(encoding="utf-8"))
            team_id = app.selectbox(key="review_team").value
            self.assertIn(team_id, {team["teamId"] for team in match["teams"]})
            return {
                player["puuid"]
                for player in match["players"]
                if not player["isObserver"] and player["teamId"] == team_id
            }

        def check_team_summary():
            match = json.loads(selected_match_file().read_text(encoding="utf-8"))
            team_id = app.selectbox(key="review_team").value
            wins = sum(result["winningTeam"] == team_id for result in match["roundResults"])
            losses = len(match["roundResults"]) - wins
            metrics = {item.label: item.value for item in app.metric}
            self.assertEqual(str(wins), metrics["Rounds vencidos"])
            self.assertEqual(str(losses), metrics["Rounds perdidos"])
            self.assertLessEqual(int(metrics["Rounds perdidos com pontos para rever"]), losses)
            self.assertFalse(any(item.key in {"pos_player", "pos_round"} for item in app.selectbox))

        def check_widget_reset_sent(key):
            selector = app.selectbox(key=key)
            self.assertTrue(selector.proto.set_value, f"O reset de {key} não foi enviado ao navegador")
            self.assertEqual(selector.format_func(selector.value), selector.proto.raw_value)

        def check_changed_match_summary():
            check_team_summary()
            check_widget_reset_sent("review_team")

        def check_team_players():
            participants = selected_team_players()
            player = app.selectbox(key="pos_player")
            expected_options = {player.format_func(player_id) for player_id in participants}
            if app.radio(key="review_view").value == "Lances":
                expected_options.add(player.format_func("Todos"))
            self.assertEqual(
                expected_options,
                set(player.options),
            )
            self.assertIn(player.value, participants | {"Todos"})

        def check_selected_round_and_player():
            match = json.loads(selected_match_file().read_text(encoding="utf-8"))
            self.assertIn(app.selectbox(key="pos_round").value, range(len(match["roundResults"])))
            check_team_players()

        def event_buttons():
            return [
                button
                for button in app.button
                if button.key and button.key.startswith("postmatch_event_")
            ]

        def check_event_selection(index, count):
            buttons = event_buttons()
            self.assertEqual(count, len(buttons))
            self.assertEqual("primary", buttons[index].proto.type)
            self.assertEqual(1, sum(button.proto.type == "primary" for button in buttons))
            self.assertTrue(
                any(item.value == f"Evento {index + 1} de {count}" for item in app.caption)
            )
            self.assertEqual(0, len(app.slider))

        def check_new_round_selection():
            check_selected_round_and_player()
            self.assertTrue(event_buttons())
            check_event_selection(0, len(event_buttons()))

        def check_new_match_selection():
            check_new_round_selection()
            for key in ["review_team", "pos_player", "review_pattern", "pos_round"]:
                check_widget_reset_sent(key)

        def check_pattern_jump():
            self.assertEqual("Lances", app.radio(key="review_view").value)
            self.assertNotEqual("all", app.selectbox(key="review_pattern").value)
            check_selected_round_and_player()
            self.assertTrue(event_buttons())

        def check_occurrence(number):
            check_pattern_jump()
            counts = [
                re.fullmatch(r"Ocorrência (\d+) de (\d+)", caption.value)
                for caption in app.caption
            ]
            current = next(match for match in counts if match)
            self.assertEqual(number, int(current[1]))
            self.assertGreaterEqual(int(current[2]), number)
            focus = app.session_state["review_event_focus"]
            self.assertEqual(focus["round"] - 1, app.selectbox(key="pos_round").value)
            check_event_selection(focus["event_index"], len(event_buttons()))

        def check_return_to_players(player_id):
            self.assertEqual("Jogadores", app.radio(key="review_view").value)
            self.assertEqual(player_id, app.selectbox(key="pos_player").value)
            check_team_players()

        def open_first_pattern():
            buttons = [
                button
                for button in app.button
                if button.key and button.key.startswith("review_pattern_")
            ]
            self.assertTrue(buttons, "A visão da equipe não mostrou padrões com exemplos")
            buttons[0].click()

        def check_round_eight_references():
            self.assertEqual(7, app.selectbox(key="pos_round").value)
            metric = next(
                item for item in app.metric if item.label == "Eventos com comparação disponível"
            )
            self.assertTrue(metric.value.endswith(" / 8"), metric.value)
            references = next(
                frame.value
                for frame in app.dataframe
                if field_label("depois_ataque") in frame.value.columns
            )
            self.assertEqual(8, len(references))
            check_selected_round_and_player()

        def check_dashboard(matches=335, teams=68):
            metrics = {item.label: item.value for item in app.metric}
            self.assertEqual(str(matches), metrics["Partidas"])
            self.assertEqual(str(teams), metrics["Equipes"])
            self.assertIn("Spearman entre menos lances e mais vitórias", metrics)
            self.assertIn("Spearman apenas pela frequência de mortes", metrics)
            self.assertTrue(app.selectbox(key="dashboard_team").options)

        def check_empty_dashboard_ranking():
            self.assertTrue(any("Nenhuma equipe atingiu" in message.value for message in app.info))
            self.assertNotIn("dashboard_open_review", [button.key for button in app.button])

        def check_dashboard_review(filename, team_name):
            from valorant.analysis.prediction import parse_match_name, team_names_by_color

            self.assertEqual("Análise pós-jogo", app.session_state["section"])
            self.assertEqual("Análise pós-jogo", app.radio(key="navigation_area").value)
            self.assertEqual("Equipe", app.radio(key="review_view").value)
            self.assertEqual(filename, app.selectbox(key="pos_match").value)
            match = json.loads(selected_match_file().read_text(encoding="utf-8"))
            names = team_names_by_color(match, parse_match_name(Path(filename)))
            self.assertEqual(team_name, names[app.selectbox(key="review_team").value])

        def check_evidence_tables():
            tables = [frame.value for frame in app.dataframe]
            trade = next(table for table in tables if "Primeira morte" in table)
            self.assertEqual([907, 2065, 406, 3159], trade["Primeiras mortes"].tolist())
            advantage = next(table for table in tables if "Situação" in table and "Ficou atrás depois de estar à frente" in table["Situação"].tolist())
            self.assertEqual([3320], advantage["Rounds de equipe"].tolist())
            self.assertEqual(838, advantage.iloc[0]["Vitórias"])

        def check_evidence_context():
            tables = [frame.value for frame in app.dataframe]
            postplant = next(table for table in tables if "No instante do desarme" in table)
            self.assertEqual([1246, 103], postplant["Desarmes"].tolist())
            plants = next(table for table in tables if "Momento do plant" in table)
            self.assertEqual([1976, 2460], plants["Plants"].tolist())
            self.assertTrue(any("Equipamento da equipe menos o adversário" in table for table in tables))
            self.assertTrue(any("Equipamento inicial médio no seguinte" in table for table in tables))

        def check_scoped_evidence():
            check_dashboard(13, 7)
            tables = [frame.value for frame in app.dataframe]
            for column in ["Primeira morte", "No instante do desarme", "Momento do plant"]:
                table = next(table for table in tables if column in table)
                self.assertTrue(table["Partidas"].le(13).all(), column)

        def open_evidence_panels():
            for key in ["dashboard_equipment", "dashboard_postplant", "dashboard_examples"]:
                app.session_state[key] = True

        def check_dashboard_example():
            self.assertEqual("Análise pós-jogo", app.session_state["section"])
            self.assertEqual("Análise pós-jogo", app.radio(key="navigation_area").value)
            self.assertEqual("Lances", app.radio(key="review_view").value)
            focus = app.session_state["review_event_focus"]
            self.assertEqual(focus["round"] - 1, app.selectbox(key="pos_round").value)
            check_event_selection(focus["event_index"], len(event_buttons()))
            self.assertEqual("Voltar para o dashboard", app.button(key="review_return").label)

        try:
            run(
                "Inicial com a visão geral",
                check=lambda: self.assertEqual(
                    "Dashboard da pesquisa",
                    app.session_state["section"],
                ),
            )
            all_tournaments = list(widget("multiselect", "Torneios").options)
            all_versions = list(widget("multiselect", "Versões do jogo").options)
            sections = list(SECTIONS)
            self.assertEqual(list(MAIN_AREAS), app.radio(key="navigation_area").options)
            self.assertEqual("Dashboard", app.radio(key="navigation_area").value)
            self.assertEqual(6, len(EXPLORATORY_SECTIONS))
            self.assertFalse(any(item.key == "section" for item in app.selectbox))
            self.assertEqual(8, len(sections))
            report.append(f"Torneios disponíveis: {all_tournaments}")
            check_dashboard()
            check_evidence_tables()
            run("Acesso principal do dashboard abre a ferramenta",
                lambda: app.button(key="dashboard_go_post_match").click(), check_team_summary)
            run("Menu principal retorna da ferramenta ao dashboard",
                lambda: app.radio(key="navigation_area").set_value("Dashboard"), check_dashboard)
            run("Acesso exploratório abre apenas as seis abas de apoio",
                lambda: app.button(key="dashboard_go_exploratory").click(),
                lambda: self.assertEqual(list(EXPLORATORY_SECTIONS), [tab.label for tab in app.tabs]))
            run("Menu principal retorna das análises ao dashboard",
                lambda: app.radio(key="navigation_area").set_value("Dashboard"), check_dashboard)
            run("Dashboard carrega equipamento e pós-plant no recorte completo", open_evidence_panels, check_evidence_context)
            run("Dashboard abre um exemplo no round e evento corretos",
                lambda: app.button(key="dashboard_open_example").click(), check_dashboard_example)
            run("Exemplo retorna ao dashboard de origem", lambda: app.button(key="review_return").click(), check_dashboard)
            run("Dashboard oferece exemplos de rounds vencidos",
                lambda: app.selectbox(key="dashboard_example_outcome").select("Rounds vencidos"),
                lambda: self.assertTrue(app.button(key="dashboard_open_example")))
            run("Exemplo de round vencido abre no evento indicado",
                lambda: app.button(key="dashboard_open_example").click(), check_dashboard_example)
            run("Exemplo vencedor retorna ao dashboard", lambda: app.button(key="review_return").click(), check_dashboard)
            run(
                "Dashboard mostra falta de equipes acima do mínimo",
                lambda: app.number_input(key="dashboard_minimum").set_value(100),
                check_empty_dashboard_ranking,
            )
            run(
                "Dashboard restaura o ranking e compara vitórias em partidas",
                lambda: (
                    app.number_input(key="dashboard_minimum").set_value(3),
                    app.selectbox(key="dashboard_performance").select("Vitórias em partidas"),
                ),
                check_dashboard,
            )
            run(
                "Dashboard aplica o recorte local de torneio",
                lambda: app.selectbox(key="dashboard_tournament").select("Rush Series Inclusivo"),
                check_scoped_evidence,
            )
            run(
                "Dashboard restaura o recorte completo e a comparação por rounds",
                lambda: (
                    app.selectbox(key="dashboard_tournament").select("Todos os torneios selecionados"),
                    app.selectbox(key="dashboard_performance").select("Vitórias em rounds"),
                ),
                check_dashboard,
            )
            dashboard_file = app.selectbox(key="dashboard_match").value
            dashboard_team = app.selectbox(key="dashboard_team").value
            run(
                "Dashboard abre a partida e equipe indicadas no ranking",
                lambda: app.button(key="dashboard_open_review").click(),
                lambda: check_dashboard_review(dashboard_file, dashboard_team),
            )
            for name in sections:
                run(f"Seção {name}", lambda name=name: section(name))

            run("Abrir análise da partida", lambda: section("Análise pós-jogo"))
            run(
                "Visão da equipe começa sem exigir round ou jogador",
                lambda: app.radio(key="review_view").set_value("Equipe"),
                check_team_summary,
            )
            recorded_files = list(app.selectbox(key="pos_match").options)
            regression_file = next(
                filename for filename in recorded_files if filename.startswith("RUSH2_007_")
            )
            run(
                "Análise da equipe após mudar para RUSH2_007",
                lambda: app.selectbox(
                    key="pos_match",
                ).select(regression_file),
                check_changed_match_summary,
            )
            run(
                "Abrir os rounds de um padrão da equipe",
                open_first_pattern,
                lambda: check_occurrence(1),
            )
            run(
                "Próxima ocorrência abre o round e evento correspondentes",
                lambda: app.button(key="review_next_occurrence").click(),
                lambda: check_occurrence(2),
            )
            run(
                "Ocorrência anterior retorna ao primeiro lance",
                lambda: app.button(key="review_previous_occurrence").click(),
                lambda: check_occurrence(1),
            )
            run(
                "Voltar restaura a análise da equipe",
                lambda: app.button(key="review_return").click(),
                lambda: self.assertEqual("Equipe", app.radio(key="review_view").value),
            )
            run(
                "Visão dos jogadores usa somente os integrantes da equipe",
                lambda: app.radio(key="review_view").set_value("Jogadores"),
                check_team_players,
            )
            run(
                "Trocar equipe também muda os jogadores disponíveis",
                lambda: app.selectbox(
                    key="review_team",
                ).select("Red" if app.selectbox(key="review_team").value == "Blue" else "Blue"),
                check_team_players,
            )
            origin_player = app.selectbox(key="pos_player").value
            run(
                "Abrir os rounds de um padrão individual",
                open_first_pattern,
                lambda: check_occurrence(1),
            )
            run(
                "Voltar restaura a análise do mesmo jogador",
                lambda: app.button(key="review_return").click(),
                lambda: check_return_to_players(origin_player),
            )
            run(
                "Reabrir lances mantém a origem do jogador",
                open_first_pattern,
                lambda: check_occurrence(1),
            )
            run(
                "Lances de todos os jogadores e padrões",
                lambda: (
                    app.selectbox(key="pos_player").select("Todos"),
                    app.selectbox(key="review_pattern").select("all"),
                ),
                check_selected_round_and_player,
            )
            run(
                "Round 8 com ressurreição oferece oito botões de eventos",
                lambda: app.selectbox(key="pos_round").set_value(7),
                lambda: check_event_selection(0, 8),
            )
            run(
                "Saltar diretamente para o último evento",
                lambda: event_buttons()[-1].click(),
                lambda: check_event_selection(7, 8),
            )
            run(
                "Voltar diretamente ao primeiro evento",
                lambda: event_buttons()[0].click(),
                lambda: check_event_selection(0, 8),
            )
            run(
                "Comparar situações parecidas no round com ressurreição",
                lambda: app.checkbox(key="review_references").check(),
                check_round_eight_references,
            )
            run(
                "Ocultar comparação mantém a revisão do mesmo round",
                lambda: app.checkbox(key="review_references").uncheck(),
                check_selected_round_and_player,
            )
            run(
                "Selecionar o último round de RUSH2_007",
                lambda: app.selectbox(key="pos_round").set_value(17),
                check_new_round_selection,
            )
            shorter_file = next(
                filename for filename in recorded_files if filename.startswith("RUSH2_021_")
            )
            run(
                "Mudar para partida mais curta sem manter round ou jogador inválido",
                lambda: app.selectbox(
                    key="pos_match",
                ).select(shorter_file),
                check_new_match_selection,
            )

            run(
                "Filtro vazio de torneios",
                lambda: tournaments([]),
                lambda: self.assertTrue(
                    any("Selecione ao menos" in item.value for item in app.info),
                ),
            )
            run("Restaurar torneios", lambda: tournaments(all_tournaments))
            run(
                "Filtro vazio de versões",
                lambda: widget(
                    "multiselect",
                    "Versões do jogo",
                ).set_value([]),
                lambda: self.assertTrue(
                    any("Selecione ao menos" in item.value for item in app.info),
                ),
            )
            run(
                "Restaurar versões",
                lambda: widget(
                    "multiselect",
                    "Versões do jogo",
                ).set_value(all_versions),
            )

            for tournament in [
                "Rush Series Esquenta",
                "Rush Series Esquenta 2",
                "Rush Series Inclusivo",
            ]:
                run(
                    f"Isolamento somente em {tournament}",
                    lambda tournament=tournament: (
                        tournaments([tournament]),
                        section("Trocas e isolamento"),
                    ),
                )
                run(
                    f"Depois do plant somente em {tournament}",
                    lambda: widget(
                        "radio",
                        "Momento do round",
                    ).set_value("pós-plant"),
                )

            pairs = [
                ("Rush Series Inclusivo", "ascent"),
                ("Rush Series Inclusivo", "sunset"),
                ("Univavá/Classificatória 2", "breeze"),
                ("Univavá/Classificatória 2", "sunset"),
            ]
            for tournament, chosen_map in pairs:
                normalize = lambda name: name.casefold().replace("/", " ").replace("  ", " ")
                selected = next(
                    (name for name in all_tournaments if normalize(name) == normalize(tournament)),
                    tournament,
                )
                if not run(
                    f"Plants com poucos casos em {tournament}",
                    lambda selected=selected: (
                        tournaments([selected]),
                        section("Plant e defuse"),
                    ),
                ):
                    continue
                options = list(app.selectbox(key="plant_map").options)
                map_value = next(
                    (option for option in options if option.casefold() == chosen_map), None
                )
                if map_value is None:
                    failures.append(f"Mapa {chosen_map} ausente em {tournament}. Opções {options}")
                    report.append(f"FAIL | {failures[-1]}")
                    save()
                    continue
                run(
                    f"Mapa sem quadrados suficientes em {tournament} e {chosen_map}",
                    lambda map_value=map_value: app.selectbox(key="plant_map").select(map_value),
                    lambda: self.assertTrue(
                        any("Nenhum quadrado" in item.value for item in app.info)
                    ),
                )

            run(
                "Restaurar a amostra de isolamento",
                lambda: (
                    tournaments(all_tournaments),
                    section("Trocas e isolamento"),
                ),
            )
            run(
                "Considerar todos os momentos do round",
                lambda: widget(
                    "radio",
                    "Momento do round",
                ).set_value("todas"),
            )
            slider_label = "Distância a partir da qual a morte conta como isolada (unidades do jogo, cerca de 100 por metro)"
            context_snapshots = {}

            def context_counts():
                index_names = [field_label("lado"), field_label("contexto")]
                deaths_column = field_label("mortes")
                for frame in app.dataframe:
                    values = frame.value
                    if list(values.index.names) == index_names and deaths_column in values:
                        return values[deaths_column].groupby(level=index_names[1]).sum().to_dict()
                raise AssertionError("Tabela por posição dos aliados não foi encontrada")

            for distance in [500, 3000]:
                run(
                    f"Contexto com limite de {distance} unidades",
                    lambda distance=distance: widget(
                        "slider",
                        slider_label,
                    ).set_value(distance),
                    lambda distance=distance: context_snapshots.update(
                        {distance: context_counts()}
                    ),
                )
            if len(context_snapshots) == 2:
                report.append(f"Contexto em 500 unidades: {context_snapshots[500]}")
                report.append(f"Contexto em 3000 unidades: {context_snapshots[3000]}")
                try:
                    self.assertNotEqual(context_snapshots[500], context_snapshots[3000])
                    self.assertGreater(
                        context_snapshots[3000].get("em grupo", 0),
                        context_snapshots[500].get("em grupo", 0),
                    )
                    self.assertEqual(
                        sum(context_snapshots[500].values()), sum(context_snapshots[3000].values())
                    )
                    report.append("PASS | Slider muda o contexto e conserva a quantidade de mortes")
                except AssertionError as error:
                    failures.append(f"Consistência do slider: {error}")
                    report.append(f"FAIL | {failures[-1]}")
            source_after = source_digest()
            report.append(f"SHA256 do aplicativo e módulos no início: {source_before}")
            report.append(f"SHA256 do aplicativo e módulos no fim: {source_after}")
            report.append(
                f"Código permaneceu igual durante a execução: {source_before == source_after}"
            )
            if source_before != source_after:
                failures.append("O código do aplicativo mudou durante a execução dos cenários")
                report.append(f"FAIL | {failures[-1]}")
            passed = sum(line.startswith("PASS |") for line in report)
            report.append(f"Resultado: {len(failures)} falhas e {passed} cenários aprovados")
            save()
        finally:
            log.close()
            del app
        self.assertFalse(failures, "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
