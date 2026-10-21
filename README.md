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

A página inicial é o Dashboard da pesquisa. Ele reúne os achados, o ranking de equipes por lances únicos a revisar e sua comparação com o desempenho observado. O total de lances aparece junto da frequência por cem rounds. Você pode escolher o torneio, o mínimo de jogos e a referência por rounds ou por partidas, exportar o ranking e abrir uma equipe na análise pós-jogo. [docs/DASHBOARD.md](docs/DASHBOARD.md) registra os critérios e os resultados da base padrão.

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
    post_match_selection.py Seleção de partida e saltos para lances
    post_match_views.py     Visões de equipe, jogadores e lances
    post_match_occurrences.py Sequência de ocorrências e seus botões
    state_comparison.py     Comparação com situações parecidas
    association_comparison.py Comparação histórica das ocorrências
    replay.py               Botões por evento e consulta das posições
    round_map.py            Desenho do minimapa
  report.py                 Geração das 15 seções de conclusões
tests/                     Testes de dados, cálculos, figuras e interface
docs/LINGUAGEM.md          Critérios de escrita e fontes consultadas
```

Para mudar um texto ou organizar uma tela, comece em `valorant/ui/sections/`. Para mudar a aparência de uma medida em várias tabelas, veja `presentation.py`. Para revisar uma conta, procure o assunto em `valorant/analysis/`.

Os módulos de análise recebem tabelas ou identificadores de partidas. Eles podem ser usados fora do app. A interface entrega a seleção por `AppContext` e `AnalysisData`, sem depender de variáveis globais que mudam com os filtros. Os caches incluem a assinatura dos arquivos e a seleção de partidas. Só a tela escolhida executa suas análises.

O dashboard usa `analysis/research.py` para reunir as mesmas observações da revisão pós-jogo e `analysis/rank_comparison.py` para comparar as ordenações. Os achados e o ranking são apresentados por `ui/research_findings.py` e `ui/research_ranking.py`. A primeira consulta calcula toda a seleção e as seguintes usam o cache.

Os comandos antigos como `python economy.py` passaram a ser módulos, por exemplo `python -m valorant.analysis.economy`. A leitura de campos usa `python -m valorant.data.fields`. Execute esses comandos a partir da raiz do repositório.

## Dados e resultados

A base local contém 336 partidas, 6.618 rounds, 46.753 mortes, 411 jogadores e dois observadores exclusivos. A seleção padrão usa 335 partidas. Uma partida começa com 24 rounds encerrados pelo tempo sem mortes nem plant. Ela fica sinalizada, pode ser incluída nos filtros e não tem causa conhecida nos arquivos.

Os eventos originais são preservados. `valorant/analysis/events.py` trata simultaneidade, reaparições, abates entre adversários, plants válidos e momentos em que o round já estava decidido. Posições são registros em instantes específicos, sem caminho contínuo ou informação completa de linha de tiro. A aproximação de 100 unidades do jogo por metro não foi validada.

Trocas contam abates do autor da morte em até cinco segundos, incluindo o mesmo instante. Esse intervalo não comprova reação. Proximidade e direção do olhar também não comprovam que seria possível atirar. As classes de dano usam o total do round e a arma da vítima corresponde ao equipamento inicial.

Em **Análise pós-jogo**, você começa pela partida e pela equipe. As visões Equipe e Jogadores mostram padrões, sua frequência e os rounds que os sustentam. A visão Lances abre a sequência de eventos. Cada evento tem um botão, e o mapa usa símbolos sem nomes sobre os jogadores. Estrela indica quem abateu e X indica quem morreu naquele instante. A legenda fica abaixo da imagem e os nomes aparecem no texto e na tabela.

O botão Selecionar equipe aleatória escolhe outra partida dos filtros atuais e abre a visão Equipe. Quando há apenas uma partida no filtro, ele escolhe a outra equipe dessa partida.

As observações saem de `valorant/analysis/post_match.py`. Cada padrão tem uma base de oportunidades definida. O resumo conta rounds distintos e separa ações individuais das situações da equipe. Informações de equipamento, posição compatível com troca e ataque sem plant continuam como contexto. As situações coletivas em que um jogador participou aparecem separadas de suas próprias ações.

Os botões dos padrões abrem os lances correspondentes. O estado da navegação é separado por partida e round, para uma troca de seleção não abrir um evento inválido. As análises da partida usam somente os dados daquela partida e os detalhes adicionais são carregados quando você os abre.

Na visão Lances, os botões Ocorrência anterior e Próxima ocorrência percorrem os casos do filtro e mudam o round e o evento automaticamente. O contador indica a posição na sequência, com os rounds perdidos primeiro. O botão de voltar restaura a visão de equipe ou de jogador de onde os lances foram abertos, incluindo o jogador e o round que estavam selecionados naquela tela.

A consulta opcional de situações parecidas usa outras partidas da seleção e combina vivos, fase, equipamento inicial e tempo. Ela exige pelo menos 20 rounds de cinco outras partidas. Quando faltam casos, o valor fica indisponível. As associações históricas e os detalhes de arma inicial, distância e dano do round continuam disponíveis como apoio à revisão.

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

Os testes de interface precisam das partidas e dos metadados em `data/`. Eles percorrem as 11 seções e os filtros que apresentavam falhas, além de conferir as três visões do pós-jogo, saltos para lances e os botões dos eventos.
