"""Seletores usados pelas telas."""

import streamlit as st

from valorant.ui.context import AppContext


def select_map(context: AppContext, label, internal_names, key):
    """Mostra nomes de mapas e devolve o código e os metadados do escolhido."""
    names = list(dict.fromkeys(context.map_names.get(name, name) for name in internal_names))
    if not names:
        return None, None
    selected_name = st.selectbox(label, names, key=key)
    internal_name = context.internal_map_names.get(selected_name, selected_name)
    metadata = context.data.maps().get(f"/Game/Maps/{internal_name}/{internal_name}")
    return internal_name, metadata
