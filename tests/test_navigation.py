"""Três áreas principais, abas sob demanda e sincronização dos atalhos."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from valorant.ui.navigation import (
    DASHBOARD, EXPLORATORY_AREA, EXPLORATORY_SECTIONS, POST_MATCH, navigate,
    select_exploratory_tab,
)


NAVIGATION_APP = '''
import streamlit as st
from unittest.mock import patch
from valorant.ui.navigation import render_navigation, render_content, render_dashboard_paths, navigate

section = render_navigation()
with patch("valorant.ui.navigation.render_section", lambda name, context: st.write("Tela aberta " + name)):
    if section == "Dashboard da pesquisa":
        render_dashboard_paths()
    render_content(section, None)
# Simula o mesmo salto de uma ocorrência para a ferramenta.
st.button("Atalho de teste para o lance", key="fixture_evidence", on_click=navigate, args=("Análise pós-jogo",))
'''


class NavigationTests(unittest.TestCase):
    def app(self):
        app = AppTest.from_string(NAVIGATION_APP).run()
        self.assertFalse(app.exception)
        return app

    def test_dashboard_has_two_paths_and_tool_is_separate_from_research(self):
        app = self.app()
        self.assertEqual("Dashboard", app.radio(key="navigation_area").value)
        self.assertEqual(0, len(app.selectbox))
        app.button(key="dashboard_go_post_match").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(POST_MATCH, app.radio(key="navigation_area").value)
        self.assertEqual([], list(app.tabs))
        app.radio(key="navigation_area").set_value("Dashboard").run()
        app.button(key="dashboard_go_exploratory").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(EXPLORATORY_AREA, app.radio(key="navigation_area").value)
        self.assertEqual(list(EXPLORATORY_SECTIONS), [tab.label for tab in app.tabs])
        opened = [element.value for element in app.markdown if element.value.startswith("Tela aberta")]
        self.assertEqual(["Tela aberta Abertura"], opened, "Only the selected analysis should execute")

    def test_selected_tab_survives_leaving_research_and_shortcuts_sync_main_menu(self):
        app = self.app()
        app.session_state["section"] = "Economia"
        app.run()
        self.assertEqual(EXPLORATORY_AREA, app.radio(key="navigation_area").value)
        self.assertEqual("Economia", app.session_state["exploratory_tabs"])
        app.button(key="fixture_evidence").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(POST_MATCH, app.radio(key="navigation_area").value)
        app.radio(key="navigation_area").set_value(EXPLORATORY_AREA).run()
        self.assertFalse(app.exception)
        self.assertEqual("Economia", app.session_state["section"])
        self.assertEqual("Economia", app.session_state["exploratory_tabs"])
        opened = [element.value for element in app.markdown if element.value.startswith("Tela aberta")]
        self.assertEqual(["Tela aberta Economia"], opened)
        app.radio(key="navigation_area").set_value("Dashboard").run()
        app.button(key="dashboard_go_exploratory").click().run()
        self.assertFalse(app.exception)
        self.assertEqual("Economia", app.session_state["section"])

    def test_old_or_invalid_section_falls_back_to_dashboard(self):
        app = self.app()
        app.session_state["section"] = "Seção removida"
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(DASHBOARD, app.session_state["section"])
        self.assertEqual("Dashboard", app.radio(key="navigation_area").value)

    def test_tab_callback_updates_route_and_remembers_it_without_a_widget(self):
        state = {"exploratory_tabs": "Explorar dados"}
        with patch("valorant.ui.navigation.st", SimpleNamespace(session_state=state)):
            select_exploratory_tab()
            self.assertEqual("Explorar dados", state["section"])
            navigate(POST_MATCH)
            self.assertEqual("Explorar dados", state["last_exploratory_section"])


if __name__ == "__main__":
    unittest.main()
