# VALORANT Hackathon

Análise de partidas de VALORANT (SEMCOMP, Riot Games e AcadArena, outubro de 2026).

## Como rodar

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python download_data.py
.venv/bin/streamlit run app.py
```

`download_data.py` baixa os 336 JSONs da pasta pública do Drive para `data/` (ignorada pelo git).
`explore_fields.py` imprime cada campo com tipos, ocorrências e valores mais frequentes. A saída está em `fields_report.txt`.
`app.py` é o painel local em http://localhost:8501.
`maps.py` baixa uma vez, para `data/maps/`, o minimapa e as constantes de conversão de coordenada de cada mapa, metadados públicos do jogo na valorant-api.com (não são dados de partida). `round_map.py` desenha as posições dos jogadores ao longo de um round sobre o minimapa, na aba Partida. A mesma fonte dá nome e função aos agentes (`characterId`), usados em `agent_roles.py`, e nome e categoria às armas, usados em `fights.py` (troca possível, distância, reação, peso econômico), `round_style.py` (colapsos e estilo de round por time) e `setups.py` (posições no plant e no defuse).
