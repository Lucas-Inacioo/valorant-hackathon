# VALORANT Hackathon

Protótipo em Streamlit para consultar partidas de VALORANT do hackathon SEMCOMP, Riot Games e AcadArena de outubro de 2026. O projeto compara primeiros abates, trocas, posição, equipamento e plant. Os resultados descrevem as partidas disponíveis e ajudam a escolher lances para rever.

## Rodar o aplicativo

O ambiente foi validado com Python 3.12. As versões diretas estão em `requirements.txt` e o ambiente completo está em `requirements-lock.txt`.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m valorant.data.download
.venv/bin/python -m valorant.data.metadata --download
.venv/bin/python -m streamlit run app.py
```

O painel abre em <http://localhost:8501>. Se `data/` já contiver as partidas e os metadados, basta executar o último comando. A navegação e os filtros ficam no menu lateral. Cada análise explica os termos perto dos gráficos.

Os arquivos baixados ficam em `data/`, fora do Git. O download valida o JSON antes de gravar e também confere os arquivos existentes. O app só lê os metadados locais. Para atualizá-los, use o comando de metadados com `--download`.

## Entender o código

```text
app.py                      Entrada do Streamlit
valorant/
  paths.py                  Raiz do projeto, pasta de dados e manifesto
  data/                     Leitura, download, metadados e conferência da base
  analysis/                 Cálculos por assunto, sem dependência do Streamlit
  ui/
    application.py          Inicialização e filtros
    context.py              Dados da seleção entregues às telas
    data.py                 Acesso às análises e cache por seleção
    navigation.py           Ordem das seções e carregamento de cada tela
    sections/               Uma tela por assunto, com funções por gráfico
    charts.py               Gráficos compartilhados
    presentation.py         Nomes de colunas e formatos exibidos
    tables.py               Preparo de tabelas de consulta
    controls.py             Seletores compartilhados
    replay.py               Consulta de um round e seus eventos
    round_map.py            Desenho do minimapa
  report.py                 Geração das 15 seções de conclusões
tests/                     Testes de dados, cálculos, figuras e interface
docs/LINGUAGEM.md          Critérios de escrita e fontes consultadas
```

Para mudar um texto ou organizar uma tela, comece em `valorant/ui/sections/`. Para mudar a aparência de uma medida em várias tabelas, veja `presentation.py`. Para revisar uma conta, procure o assunto em `valorant/analysis/`.

Os módulos de análise recebem tabelas ou identificadores de partidas. Eles podem ser usados fora do app. A interface entrega a seleção por `AppContext` e `AnalysisData`, sem depender de variáveis globais que mudam com os filtros. Os caches incluem a assinatura dos arquivos e a seleção de partidas. Só a tela escolhida executa suas análises.

Os comandos antigos como `python economy.py` passaram a ser módulos, por exemplo `python -m valorant.analysis.economy`. A leitura de campos usa `python -m valorant.data.fields`. Execute esses comandos a partir da raiz do repositório.

## Dados e resultados

A base local contém 336 partidas, 6.618 rounds, 46.753 mortes, 411 jogadores e dois observadores exclusivos. A seleção padrão usa 335 partidas. Uma partida começa com 24 rounds encerrados pelo tempo sem mortes nem plant. Ela fica sinalizada, pode ser incluída nos filtros e não tem causa conhecida nos arquivos.

Os eventos originais são preservados. `valorant/analysis/events.py` trata simultaneidade, reaparições, abates entre adversários, plants válidos e momentos em que o round já estava decidido. Posições são registros em instantes específicos, sem caminho contínuo ou informação completa de linha de tiro. A aproximação de 100 unidades do jogo por metro não foi validada.

Trocas contam abates do autor da morte em até cinco segundos, incluindo o mesmo instante. Esse intervalo não comprova reação. Proximidade e direção do olhar também não comprovam que seria possível atirar. As classes de dano usam o total do round e a arma da vítima corresponde ao equipamento inicial.

Em **Revisar um round**, as ocorrências são contagens, sem soma de pontos por jogador. A consulta de situações parecidas usa outras partidas da seleção e combina vivos, fase, equipamento inicial e tempo. Ela exige pelo menos 20 rounds de cinco outras partidas. Quando faltam casos, o valor fica indisponível.

Em **Previsão**, a avaliação com jogos anteriores usa apenas o histórico disponível antes de cada partida. As regras e o histórico são comparados nos mesmos jogos. A comparação retrospectiva também pode usar jogos posteriores e aparece separada. As análises não demonstram o efeito de uma decisão individual nem validam uma estratégia de compra ou posição.

## Conferir a base e gerar conclusões

```bash
# Conferência de leitura
.venv/bin/python -m valorant.data.quality

# Atualização dos documentos gerados
.venv/bin/python -m valorant.data.quality --manifest data-manifest.json
.venv/bin/python -m valorant.report --output CONCLUSOES.md
```

O manifesto registra hashes SHA256, cobertura, anomalias e a origem conhecida de cada arquivo. Ele não garante que a pasta remota esteja completa. Os metadados de mapas, agentes e armas também entram na assinatura.

[CONCLUSOES.md](CONCLUSOES.md) reúne os resultados da seleção padrão. Os filtros do site não alteram esse documento. [CORRECOES.md](CORRECOES.md) registra a revisão anterior e [VALIDACAO.md](VALIDACAO.md) descreve as conferências. `fields_report.txt` mantém a exploração histórica dos campos.

## Verificar mudanças

```bash
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -v

VALORANT_RUN_APPTEST=1 PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -p test_app.py -v
```

Os testes de interface precisam das partidas e dos metadados em `data/`. Eles percorrem as 12 seções e os filtros que apresentavam falhas, além de conferir as duas formas de revisar um round.
