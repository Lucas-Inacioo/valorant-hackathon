"""Regressão integrada de Streamlit, ativada com VALORANT_RUN_APPTEST=1.

Usa um único processo para compartilhar os caches entre cenários. Confere
navegação, filtros e consultas que já falharam com partidas da base local.
"""

import contextlib
import hashlib
import json
import os
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

        from valorant.ui.navigation import SECTIONS
        from valorant.ui.presentation import field_label

        report, failures = [], []
        source_before = source_digest()
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
        log_path = Path("/tmp/valorant-readable-apptest-stderr.log")
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
            app.selectbox(key="section").select(name)

        def tournaments(values):
            widget("multiselect", "Torneios").set_value(values)

        def selected_match_file():
            filename = app.selectbox(key="pos_match").value
            return next((ROOT / "data").rglob(filename))

        def check_selected_round_and_player():
            match = json.loads(selected_match_file().read_text(encoding="utf-8"))
            self.assertIn(app.selectbox(key="pos_round").value, range(len(match["roundResults"])))
            participants = {
                player["puuid"] for player in match["players"] if not player["isObserver"]
            }
            self.assertIn(app.selectbox(key="pos_player").value, participants)

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

        try:
            run(
                "Inicial com a visão geral",
                check=lambda: self.assertEqual(
                    "Visão geral",
                    app.selectbox(key="section").value,
                ),
            )
            all_tournaments = list(widget("multiselect", "Torneios").options)
            all_versions = list(widget("multiselect", "Versões do jogo").options)
            sections = list(app.selectbox(key="section").options)
            self.assertEqual(list(SECTIONS), sections)
            self.assertEqual(12, len(sections))
            report.append(f"Torneios disponíveis: {all_tournaments}")
            for name in sections:
                run(f"Seção {name}", lambda name=name: section(name))

            run("Abrir revisão de round", lambda: section("Revisar um round"))
            run(
                "Revisão com situações parecidas",
                lambda: widget(
                    "radio",
                    "Visualização",
                ).set_value("Situações parecidas"),
            )
            recorded_files = list(app.selectbox(key="pos_match").options)
            regression_file = next(
                filename for filename in recorded_files if filename.startswith("RUSH2_007_")
            )
            run(
                "Revisão após mudar para RUSH2_007",
                lambda: app.selectbox(
                    key="pos_match",
                ).select(regression_file),
                check_selected_round_and_player,
            )
            run(
                "Round 8 com ressurreição e oito eventos",
                lambda: app.selectbox(
                    key="pos_round",
                ).set_value(7),
                check_round_eight_references,
            )
            run(
                "Ocorrências no mesmo round com ressurreição",
                lambda: widget(
                    "radio",
                    "Visualização",
                ).set_value("Ocorrências da partida"),
                check_selected_round_and_player,
            )
            run(
                "Selecionar o último round de RUSH2_007",
                lambda: app.selectbox(
                    key="pos_round",
                ).set_value(17),
                check_selected_round_and_player,
            )
            shorter_file = next(
                filename for filename in recorded_files if filename.startswith("RUSH2_021_")
            )
            run(
                "Mudar para partida mais curta sem manter round ou jogador inválido",
                lambda: app.selectbox(
                    key="pos_match",
                ).select(shorter_file),
                check_selected_round_and_player,
            )
            run(
                "Sortear partida, round e jogador válidos",
                lambda: widget(
                    "button",
                    "Sortear partida, round e jogador",
                ).click(),
                check_selected_round_and_player,
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
                        section("Plant e desarme"),
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
            slider_label = "Distância para considerar uma morte isolada"
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
            passed = sum(line.startswith("PASS |") for line in report)
            report.append(f"Resultado: {len(failures)} falhas e {passed} cenários aprovados")
            save()
        finally:
            log.close()
            del app
        self.assertFalse(failures, "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
