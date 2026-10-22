"""Dados que uma tela pode consultar durante uma execução do aplicativo."""

from dataclasses import dataclass

import pandas as pd

from valorant.ui.data import AnalysisData


@dataclass(frozen=True)
class AppContext:
    data: AnalysisData
    matches: pd.DataFrame
    players: pd.DataFrame
    rounds: pd.DataFrame
    selected_matches: pd.DataFrame
    selected_players: pd.DataFrame
    quality: dict

    @property
    def selected_match_ids(self) -> set[str]:
        return set(self.data.match_ids)

    @property
    def map_names(self) -> dict[str, str]:
        return dict(zip(self.matches["mapa_interno"], self.matches["mapa"]))

    @property
    def internal_map_names(self) -> dict[str, str]:
        return {name: internal for internal, name in self.map_names.items()}
