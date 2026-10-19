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
