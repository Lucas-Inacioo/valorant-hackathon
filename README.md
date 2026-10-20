# VALORANT Hackathon

Exploração descritiva de partidas de VALORANT para o hackathon SEMCOMP, Riot Games e AcadArena, outubro de 2026. As observações não estimam contribuição causal dos jogadores nem validam uma política de compra, caça ou posicionamento.

## Executar localmente

Ambiente validado com Python 3.12. As dependências diretas estão fixadas em `requirements.txt`; `requirements-lock.txt` registra também as versões transitivas do ambiente testado.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python download_data.py
.venv/bin/python maps.py --download
.venv/bin/python data_quality.py --manifest data-manifest.json
.venv/bin/python analysis_report.py --output CONCLUSOES.md
.venv/bin/python -m streamlit run app.py
```

O painel fica em <http://localhost:8501>. Se os dados e metadados já estiverem disponíveis, basta o último comando. Os loaders de metadados só leem o cache local; a atualização remota é explícita com `maps.py --download`.

`download_data.py` baixa os arquivos da pasta pública do Drive para `data/`, ignorada pelo Git. Os downloads validam JSON e campos mínimos, gravam atomicamente e propagam falhas paralelas. Arquivos previamente existentes são validados. O manifesto registra hashes e a origem conhecida; arquivos anteriores sem origem verificada são identificados dessa forma, sem inventar data de coleta.

## Amostra e definições

- O inventário bruto contém 336 partidas, 6.618 rounds, 46.753 mortes, 411 participantes e dois observadores exclusivos.
- A análise padrão usa 335 partidas. Uma partida com 24 rounds iniciais por tempo esgotado sem mortes/plant é sinalizada, sem atribuir causa, e pode ser incluída pelo controle de qualidade.
- Torneios, builds e qualidade definem a amostra e recalculam as referências. O documento `CONCLUSOES.md` é um retrato gerado da amostra padrão, explicitamente separado dos filtros da interface.
- `match_events.py` preserva eventos brutos e snapshots, identifica ressurreições, simultaneidade, abates adversários, plants válidos e decisões observáveis. A morte por Bomb em um round de detonação também fornece evidência de decisão. Quando o fim não tem timestamp observável, a limitação é contabilizada na qualidade, sem inventar um instante.
- Aberturas e trocas temporais exigem abates adversários válidos. Empates de abertura entre equipes são excluídos das taxas, com denominador explícito. Simultaneidade não comprova reação.
- A antiga indicação de troca possível agora descreve apenas proximidade e direção compatíveis. Não há informação suficiente para comprovar parede, smoke, linha de tiro, recarga ou culpa do jogador.
- As categorias de luta descrevem dano agregado no round. Assistência não comprova dano; dano no round não identifica reação em um confronto específico. A arma atribuída à vítima é o equipamento inicial.
- Metadados de mapas/agentes/armas também influenciam agrupamentos analíticos e são incluídos na assinatura/manifesto. A conversão aproximada de 100 unidades por metro não foi validada.

## Ferramentas e incerteza

A Ferramenta proposta mostra contagens de indicadores e associações, sem somar pontos sobrepostos ou atribuir saldo individual. As associações por round e por morte são apresentadas separadamente, com contraste definido e reamostragem por partida. Tabelas por morte ponderam um round pelo número de eventos que ele fornece.

A referência por estado exclui a partida selecionada. Condiciona vivos, fase, faixa da diferença de equipamento e tempo, com suporte mínimo de 20 rounds e cinco partidas. Sem suporte, o valor fica indisponível; não há fallback para outra população. Não é um modelo de probabilidade calibrado e não credita a variação a quem agiu. Resultados finais são fatos observados.

A previsão temporal estima perfis e escalas somente no passado. Modelo e histórico são comparados nos mesmos jogos, com abstenções explícitas. A avaliação retrospectiva permite jogos posteriores e recebe esse nome. Intervalos exploratórios não provam equivalência nem eliminam dependência entre equipes, seleção ou confusão causal.

## Qualidade e reprodução

```bash
# Inspeção somente de leitura:
.venv/bin/python data_quality.py

# Atualizações explícitas de artefatos derivados:
.venv/bin/python data_quality.py --manifest data-manifest.json
.venv/bin/python analysis_report.py --output CONCLUSOES.md
```

O manifesto contém hashes SHA256 dos JSONs e metadados, cobertura, anomalias e origem disponível, sem PUUIDs. Não certifica a completude contra a pasta remota. Os caches do painel recebem a assinatura de arquivos e a seleção de partidas, invalidando quando dados ou metadados mudam. As seções executam sob demanda.

`explore_fields.py` inspeciona campos; `fields_report.txt` é a exploração histórica bruta e não substitui o inventário atual de qualidade. As conclusões revisadas e os tipos de correção estão em `CONCLUSOES.md` e `CORRECOES.md`.

## Validação

```bash
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -v

# Integração da interface com o corpus local, incluindo filtros que falhavam:
VALORANT_RUN_APPTEST=1 PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -p test_app.py -v
```

Os testes sintéticos cobrem ressurreições, empates, friendly fire, trocas, medianas, coortes/censura, flags simultâneas, referências ausentes, vazio, cache, download e figuras. O AppTest visita as 12 seções, referências por estado, filtros vazios, pós-plant por campeonato e os quatro recortes sem células de plant. Ele requer os JSONs e metadados locais.
