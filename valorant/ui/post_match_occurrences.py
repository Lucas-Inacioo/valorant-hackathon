"""Controles para percorrer as ocorrências do filtro no replay."""

import streamlit as st

from valorant.ui.post_match_selection import jump_to_occurrence, matching_occurrences


def occurrence_neighbors(occurrences, round_number, event_index, time_ms, won_round, selected_id=None):
    """Localiza a ocorrência exibida ou os vizinhos de um evento escolhido à mão."""
    occurrences = occurrences.reset_index(drop=True)
    event_indices = occurrences["event_index"].fillna(0)
    same_event = occurrences[
        (occurrences["round"] == round_number) & (event_indices == (event_index or 0))
    ]
    if not same_event.empty:
        preferred = same_event[same_event["observation_id"] == selected_id]
        current = int((preferred if not preferred.empty else same_event).index[0])
        previous = current - 1 if current > 0 else None
        following = current + 1 if current + 1 < len(occurrences) else None
        return current, previous, following
    current_key = (bool(won_round), round_number, time_ms, event_index or 0)
    before, after = [], []
    for index, row in occurrences.iterrows():
        key = (bool(row["won_round"]), int(row["round"]), row["time_ms"], event_indices.iloc[index])
        if key < current_key:
            before.append(index)
        elif key > current_key:
            after.append(index)
    return None, before[-1] if before else None, after[0] if after else None


def render_occurrence_navigation(selection, recorded, event_index, pattern_id, player_id):
    occurrences = matching_occurrences(selection, pattern_id, player_id).reset_index(drop=True)
    event = recorded.events[event_index] if event_index is not None else None
    current, previous, following = occurrence_neighbors(
        occurrences,
        recorded.round_index + 1,
        event_index,
        event["time_ms"] if event else 0,
        recorded.result["winningTeam"] == selection.team_id,
        st.session_state.get("review_occurrence_id"),
    )
    if current is not None:
        row = occurrences.iloc[current]
        st.session_state["review_occurrence_id"] = row["observation_id"]
        st.caption(f"Ocorrência {current + 1} de {len(occurrences)}")
        st.caption(row["pattern"])
    elif occurrences.empty:
        st.caption("Nenhuma ocorrência para os filtros escolhidos.")
    else:
        st.caption(f"{len(occurrences)} ocorrências neste filtro. Este evento está fora da sequência.")
    with st.container(horizontal=True, wrap=True, gap="small"):
        for label, key, target in [
            ("Ocorrência anterior", "review_previous_occurrence", previous),
            ("Próxima ocorrência", "review_next_occurrence", following),
        ]:
            st.button(
                label,
                key=key,
                disabled=target is None,
                on_click=jump_to_occurrence,
                args=(
                    selection,
                    pattern_id,
                    player_id,
                    occurrences.iloc[target]["observation_id"] if target is not None else None,
                ),
            )
    if not occurrences.empty:
        st.caption("Os rounds perdidos aparecem primeiro. A sequência mantém os filtros escolhidos.")
