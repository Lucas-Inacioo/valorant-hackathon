# Dashboard da pesquisa

Conferência feita em 20 de outubro de 2026 com a seleção padrão de 335 partidas e 6.588 rounds. Os dados originais e o documento CONCLUSOES.md foram preservados.

## Organização do aplicativo

O dashboard é a entrada do aplicativo e apresenta o resumo da pesquisa. Dois botões levam à ferramenta de análise pós-jogo ou à área de dados exploratórios e análises. A ferramenta fica separada das análises que deram origem aos resultados.

O menu principal mantém essas três áreas visíveis. Dentro da área exploratória estão as abas Abertura, Trocas e isolamento, Colapso e estilo, Economia, Plant e defuse e Explorar dados. Somente a aba escolhida executa sua análise. Ao sair e voltar, a última aba consultada é restaurada.

Os filtros laterais continuam compartilhados pelas três áreas. Os atalhos de equipes e exemplos do dashboard abrem a ferramenta na seleção correspondente e atualizam a opção marcada no menu principal.

## Como o ranking foi construído

O dashboard reutiliza `build_match_review`, a mesma função da análise pós-jogo. Entram os cinco padrões de revisão que descrevem ações ou sequências observadas. Acertos e condições classificadas como contexto ficam fora.

Os padrões são morte longe do apoio, morte longe do grupo, primeira morte longe do apoio e sem troca, vantagem numérica invertida e três mortes sem resposta em até dez segundos.

Um lance corresponde a uma partida, equipe, round e evento. Quando vários padrões apontam esse mesmo evento, ele conta uma vez. O resultado do round não decide se o lance entra na contagem. Entram rounds vencidos e perdidos.

Foram encontrados 44.105 registros de padrões, que correspondem a 28.121 lances únicos de equipe. As observações aparecem em 11.718 rounds de equipe. As duas equipes de uma partida têm sua própria contagem, por isso o total de rounds de equipe é 13.176.

O ranking mostra tanto o total de lances quanto a frequência por cem rounds. A frequência divide o total de lances pelos rounds jogados e multiplica por cem. Ela pode passar de cem porque um round pode ter vários lances. As taxas agregadas usam o total da exposição, sem fazer uma média simples de porcentagens de partidas com durações diferentes.

## Quantidade de jogos e desempenho

Há 68 nomes de equipes na seleção padrão. Elas têm média de 9,85 partidas e mediana de 7,5. Cinco equipes têm apenas um jogo e quatro têm dois. O mínimo inicial de três partidas mantém 59 equipes. O controle permite mudar esse mínimo e a seção de método compara os resultados com mínimos de um, três e cinco jogos.

A referência inicial de desempenho é a fração de rounds vencidos. Ela oferece uma ordenação menos cheia de empates que a fração de partidas vencidas quando há poucos jogos. Isso não transforma rounds da mesma partida em jogos independentes. Também é possível comparar diretamente com a taxa de vitória em partidas.

Nomes diferentes permanecem separados. Um mesmo nome em vários torneios é reunido no recorte geral. O filtro local permite consultar cada torneio, pois eles têm agendas e adversários diferentes. Não há ajuste por força de adversários, mapa, versão ou mudança de elenco.

## Comparação entre as ordenações

Spearman compara menos lances por cem rounds com mais vitórias. Empates recebem a posição média. O sinal positivo indica que frequências menores de revisão aparecem junto de desempenho maior.

A concordância compara pares com desempenho diferente. A equipe com menos lances precisa ter desempenho maior para o par concordar. Empate na frequência vale meio acerto e empate de desempenho fica fora. Os pares compartilham equipes e não são observações independentes.

| Desempenho observado | Equipes | Spearman | Intervalo de 95% | Concordância | Intervalo de 95% |
| --- | --- | --- | --- | --- | --- |
| Vitórias em rounds | 59 | 0,756 | 0,640 a 0,846 | 78,2% | 73,5% a 83,1% |
| Vitórias em partidas | 59 | 0,689 | 0,541 a 0,804 | 77,0% | 70,1% a 81,9% |

Na comparação por rounds há 1.708 pares com desempenho diferente e três empates de desempenho. Na comparação por partidas há 1.608 pares comparáveis e 103 empates de desempenho.

Os intervalos usam 500 reamostragens de partidas inteiras, com semente zero, mantendo as duas equipes juntas. A coorte do ranking original permanece fixa. Uma equipe sem exposição numa reamostragem fica fora da conta daquela reamostragem. As 500 reamostragens da seleção padrão tiveram Spearman calculável. Esses intervalos descrevem a agenda registrada e não corrigem todas as dependências de equipes e adversários recorrentes.

O dashboard também mostra a referência apenas pela frequência de mortes por cem rounds. Sua correlação de Spearman com vitórias em rounds é 0,95 nas mesmas 59 equipes. Isso mostra por que a associação de 0,76 dos lances não deve ser apresentada como ganho de previsão. A revisão serve para localizar situações concretas a estudar e não foi validada como uma nova medida de força das equipes.

AUC usa escores de classificação e classes conhecidas. Como a referência aqui é uma taxa contínua, o dashboard preserva a ordenação com Spearman e concordância, sem criar classes artificiais de equipes boas e ruins. As definições estão na [documentação de Spearman](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html) e na [documentação de ROC-AUC](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html).

## Achados mostrados na abertura

Quem fez o primeiro abate venceu 71,3% dos 6.578 rounds com equipe de abertura identificada.

Nas primeiras mortes individuais com aliado vivo e distância disponível, a troca ocorreu em 30,5% das 2.972 mortes com aliado próximo e 11,4% das 3.565 distantes. A taxa de vitória da equipe nesses mesmos grupos ficou em 28,8% e 28,7%. A distância acompanha uma frequência de troca diferente, mas a comparação isolada dessas mortes não demonstra um efeito causal na vitória. A conversão de mil unidades do jogo para cerca de dez metros é aproximada e não verifica paredes ou visão.

Em 2.850 rounds de equipe houve três mortes de pessoas diferentes em até dez segundos sem abate adversário pela equipe no intervalo. A equipe venceu 6,5% desses rounds. Esse número descreve a sequência observada e não atribui culpa individual.

## Comparações para orientar a revisão

O painel também cruza as análises já existentes nas outras abas. Não foram coletados novos dados, alterados os arquivos das partidas ou treinados modelos adicionais. Todas as tabelas acompanham os filtros laterais e o recorte local de torneio.

A primeira comparação separa primeiras mortes individuais por proximidade do aliado e troca efetivamente registrada. A vitória é sempre da equipe da vítima.

| Primeira morte | Resposta | Casos | Vitórias | Taxa de vitória |
| --- | --- | --- | --- | --- |
| Com aliado próximo | Com troca | 907 | 398 | 43,9% |
| Com aliado próximo | Sem troca | 2.065 | 457 | 22,1% |
| Longe dos aliados | Com troca | 406 | 195 | 48,0% |
| Longe dos aliados | Sem troca | 3.159 | 828 | 26,2% |

A diferença com troca menos sem troca é de 21,8 pontos percentuais nos dois grupos, com arredondamento. Os intervalos de 95% são de 18,7 a 25,0 pontos no grupo próximo e de 17,2 a 25,6 no distante. Eles usam a função existente `cluster_contrast`, com 500 reamostragens de partidas inteiras e semente zero. Essa separação não controla equipamento, equipe ou todos os jogadores vivos e não demonstra o ganho causal de executar uma troca.

A sequência de três perdas sem resposta aparece em 2.850 rounds de equipe, com 184 vitórias e 2.666 derrotas. Nos 10.326 rounds sem essa sequência registrada houve 6.404 vitórias, ou 62,0%. O grupo de referência inclui rounds sem três mortes próximas, por isso não significa três mortes equivalentes que receberam resposta. A diferença bruta de vitórias é de menos 55,6 pontos, com intervalo de menos 56,6 a menos 54,4 pontos. A sequência não atribui culpa ao primeiro jogador morto.

A comparação de vantagem numérica se limita aos 9.107 rounds de equipe com vantagem observada. Em 3.320 a equipe ficou atrás depois de estar à frente e ainda venceu 838, ou 25,2%. Igualar o número de vivos, como numa troca, não conta como perda.

Dois painéis de contexto são calculados ao abrir. O primeiro reutiliza a vitória por diferença de equipamento inicial e o equipamento e resultado do round seguinte às derrotas, separados por sobreviventes. As transições excluem a passagem de metade, a prorrogação e rounds sem seguinte consecutivo. Valores iniciais não equivalem ao gasto ou ao valor perdido em uma morte. Os grupos mostram as próprias contagens, inclusive quando pequenos.

O segundo painel mostra os 1.349 desarmes de plants válidos. Em 1.246 havia zero atacantes vivos e em 103 havia pelo menos um. Os 92,4% são a fração dos desarmes com zero atacantes vivos, não a probabilidade de desarme depois da morte do último atacante.

Nesse mesmo painel, os 1.976 plants até 40 segundos e os 2.460 posteriores são comparados com a vitória média de plants com as mesmas quantidades de atacantes e defensores vivos. A referência é recalculada no recorte selecionado e usa os próprios rounds. A diferença para ela é de aproximadamente mais 0,2 e menos 0,2 pontos percentuais, respectivamente, apesar da diferença bruta de cerca de 6,5 pontos entre tempos. Isso descreve a composição dos grupos e não valida acelerar o plant como intervenção.

O painel de exemplos permite escolher o padrão, a equipe e rounds vencidos ou perdidos, abrir a partida no evento selecionado e voltar ao dashboard com o recorte e as escolhas anteriores. A escolha da equipe mantém a lista de eventos curta. Os identificadores combinam partida e ocorrência, pois o identificador da ocorrência sozinho pode se repetir entre jogos.

## Código e verificações

`valorant/analysis/research.py` prepara as contagens. `rank_comparison.py` compara as ordenações e calcula os intervalos. `review_evidence.py` organiza os cruzamentos por troca, sequência, vantagem e plant. A interface fica em `ui/research_findings.py`, `ui/research_evidence.py`, `ui/research_ranking.py` e `ui/sections/overview.py`.

Os testes conferem sobreposição de padrões, rounds únicos, inclusão de vitórias na revisão, bases de exposição, resultados ausentes, empates, orientação do coeficiente e reamostragem por partida. A integração confere os filtros, os recortes sem equipes suficientes, a troca da referência de desempenho e a abertura da equipe e partida corretas na análise pós-jogo. A exportação inclui o ranking completo do recorte.

A assinatura dos dados continua sendo `df71e403d1d939578ca48bb0dac73aa709a99ef6a7593af24576a1d2ee0ffcb9`.
