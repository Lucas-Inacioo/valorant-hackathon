"""Regressão integrada de Streamlit; execute com VALORANT_RUN_APPTEST=1.

O fluxo usa um processo para compartilhar os caches de análise entre cenários.
O relatório inclui repros e exceções, sem alterar dados ou o aplicativo.
"""
import contextlib
import hashlib
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = Path(os.environ.get("VALORANT_APP_REPORT", "/tmp/valorant-app-validation.txt"))


@unittest.skipUnless(os.environ.get("VALORANT_RUN_APPTEST") == "1", "AppTest completo é opt-in: VALORANT_RUN_APPTEST=1")
class AppIntegrationTests(unittest.TestCase):
    def test_all_sections_and_audited_filter_regressions(self):
        from streamlit.testing.v1 import AppTest

        report = []
        failures = []
        source_before = hashlib.sha256((ROOT / "app.py").read_bytes()).hexdigest()
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
        log_path = Path("/tmp/valorant-apptest-stderr.log")
        log = log_path.open("w", encoding="utf-8")

        def save():
            REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")

        def run(label, action=None, check=None):
            try:
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    if action:
                        action()
                    app.run(timeout=120)
                errors = [exception.message for exception in app.exception]
                if errors:
                    detail = " | ".join(errors)
                    for exception in app.exception:
                        report.extend(f"  {line}" for line in exception.stack_trace)
                    raise AssertionError(detail)
                if check:
                    check()
                report.append(f"PASS | {label}")
            except Exception as error:
                failures.append(f"{label}: {type(error).__name__}: {error}")
                report.append(f"FAIL | {failures[-1]}")
            save()
            print(report[-1], flush=True)

        def widget(kind, label):
            return next(w for w in getattr(app, kind) if w.label == label)

        def section(name):
            app.selectbox(key="section").select(name)

        def tournaments(values):
            widget("multiselect", "Torneios").set_value(values)

        try:
            run("Inicial: seção padrão Visão geral", check=lambda: self.assertEqual("Visão geral", app.selectbox(key="section").value))
            all_tournaments = list(widget("multiselect", "Torneios").options)
            all_versions = list(widget("multiselect", "Versões do jogo").options)
            sections = list(app.selectbox(key="section").options)
            self.assertEqual(12, len(sections))
            report.append(f"Torneios disponíveis: {all_tournaments}")
            for name in sections:
                run(f"Seção: {name}", lambda name=name: section(name))
            run("Ferramenta: visualização Referência por estado", lambda: section("Ferramenta proposta"))
            run("Ferramenta: Referência por estado selecionada", lambda: widget("radio", "Visualização").set_value("Referência por estado"))
            run("Filtro vazio: todos os torneios removidos", lambda: tournaments([]),
                lambda: self.assertTrue(any("Selecione ao menos" in item.value for item in app.info)))
            run("Restaurar todos os torneios", lambda: tournaments(all_tournaments))
            run("Filtro vazio: todas as versões removidas", lambda: widget("multiselect", "Versões do jogo").set_value([]),
                lambda: self.assertTrue(any("Selecione ao menos" in item.value for item in app.info)))
            run("Restaurar todas as versões", lambda: widget("multiselect", "Versões do jogo").set_value(all_versions))

            for tournament in ["Rush Series Esquenta", "Rush Series Esquenta 2", "Rush Series Inclusivo"]:
                run(f"Isolamento: selecionar somente {tournament}", lambda tournament=tournament: (tournaments([tournament]), section("Trocas e isolamento")))
                run(f"Pós-plant: somente {tournament}", lambda: widget("radio", "Momento do round").set_value("pós-plant"))

            pairs = [("Rush Series Inclusivo", "ascent"), ("Rush Series Inclusivo", "sunset"),
                     ("Univavá/Classificatória 2", "breeze"), ("Univavá/Classificatória 2", "sunset")]
            for tournament, chosen_map in pairs:
                candidates = [name for name in all_tournaments if name.casefold().replace("/", " ").replace("  ", " ") == tournament.casefold().replace("/", " ")]
                selected = candidates[0] if candidates else tournament
                run(f"Plants sem células: selecionar {tournament}", lambda selected=selected: (tournaments([selected]), section("Plant e defuse")))
                options = list(app.selectbox(key="plant_map").options) if not app.exception else []
                map_value = next((option for option in options if option.casefold() == chosen_map), None)
                if map_value is None:
                    failures.append(f"Mapa {chosen_map} não disponível em {tournament}; opções={options}")
                    report.append(f"FAIL | {failures[-1]}")
                    save()
                else:
                    run(f"Plants sem células: {tournament} / {chosen_map}", lambda map_value=map_value: app.selectbox(key="plant_map").select(map_value),
                        lambda: self.assertTrue(any("nenhuma célula" in item.value for item in app.info)))

            run("Contexto: restaurar amostra completa", lambda: (tournaments(all_tournaments), section("Trocas e isolamento")))
            run("Contexto: todas as fases", lambda: widget("radio", "Momento do round").set_value("todas"))
            slider_label = next(w.label for w in app.slider if w.label.startswith("Distância a partir"))
            snapshots = {}

            def context_counts():
                for frame in app.dataframe:
                    value = frame.value
                    if list(value.index.names) == ["lado", "contexto"] and "mortes" in value:
                        return value["mortes"].groupby(level="contexto").sum().to_dict()
                raise AssertionError("Tabela por contexto não foi encontrada")

            for distance in [500, 3000]:
                run(f"Contexto: slider {distance}", lambda distance=distance: widget("slider", slider_label).set_value(distance),
                    lambda distance=distance: snapshots.update({distance: context_counts()}))
            if len(snapshots) == 2:
                report.append(f"Contexto 500: {snapshots[500]}")
                report.append(f"Contexto 3000: {snapshots[3000]}")
                try:
                    self.assertNotEqual(snapshots[500], snapshots[3000])
                    self.assertGreater(snapshots[3000].get("em grupo", 0), snapshots[500].get("em grupo", 0))
                    self.assertEqual(sum(snapshots[500].values()), sum(snapshots[3000].values()))
                    report.append("PASS | Slider recalcula contexto e conserva o número de mortes elegíveis")
                except AssertionError as error:
                    failures.append(f"Consistência do slider: {error}")
                    report.append(f"FAIL | {failures[-1]}")
            source_after = hashlib.sha256((ROOT / "app.py").read_bytes()).hexdigest()
            report.append(f"SHA256 app início: {source_before}")
            report.append(f"SHA256 app fim: {source_after}")
            report.append(f"Resultado: {len(failures)} falhas; {sum(line.startswith('PASS |') for line in report)} cenários aprovados")
            save()
        finally:
            log.close()
            # AppTest.run encerra seu LocalScriptRunner após cada execução.
            del app
        self.assertFalse(failures, "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
