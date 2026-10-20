# O que os dados mostram

Relatório gerado em 20/10/2026 com `python -m valorant.report --output CONCLUSOES.md`.

A base local tem **336 partidas, 6.618 rounds, 46.753 mortes e 411 participantes**. Há também 2 observadores que não jogaram. A análise usa por padrão **335 partidas e 6.588 rounds**.

Uma partida fica fora da análise padrão porque seus primeiros 24 rounds terminam por tempo, sem combate ou plant. O motivo desse registro é desconhecido. Os arquivos originais foram preservados.

Na seleção padrão, há 46.708 mortes registradas, 46.187 mortes usadas na análise de combate, 6.578 rounds com equipe de abertura definida e 4.436 plants válidos. O arquivo `data-manifest.json` e a página Qualidade dos dados detalham as exclusões.

As taxas nas tabelas vão de zero a um. Por exemplo, 0,700 corresponde a 70%. Uma diferença de 0,050 corresponde a cinco pontos percentuais. As tabelas descrevem as partidas registradas e não mostram, por si só, o que causou uma vitória.

Cada morte conta como uma observação nas tabelas por morte. Assim, um round com mais mortes pesa mais nessas tabelas. Os rounds da mesma partida também compartilham condições e não são observações independentes. As comparações servem para levantar perguntas. Não houve ajuste estatístico para o grande número de comparações feitas.

A assinatura dos dados e metadados é `df71e403d1d939578ca48bb0dac73aa709a99ef6a7593af24576a1d2ee0ffcb9`.

## 1. Abertura e troca de abates

Abertura é o primeiro abate de um adversário antes do encerramento observável do round. Se as duas equipes abatem no mesmo instante, a abertura fica indefinida. Se só uma equipe faz abates simultâneos, sabemos quem abriu, mas não escolhemos uma vítima ou posição individual.

A equipe que faz a abertura vence 71,3% dos rounds com abertura definida. Ficaram fora dessa comparação 3 rounds com abertura simultânea entre equipes.

Troca em até cinco segundos ocorre quando a equipe da vítima abate o autor da morte nessa janela. Ela inclui abates simultâneos e, por isso, não comprova uma reação ao primeiro abate. Mortes por ambiente, fogo amigo ou após o encerramento observável ficam fora.

| Lado que fez a abertura | Tempo da abertura | Rounds | Vitória de quem abriu | Troca em até 5 s |
| --- | --- | --- | --- | --- |
| ataque | 0-10 s | 905 | 0,767 | 0,154 |
| ataque | 10-20 s | 902 | 0,748 | 0,152 |
| ataque | 20-30 s | 493 | 0,769 | 0,159 |
| ataque | 30-45 s | 365 | 0,718 | 0,198 |
| ataque | 45-60 s | 197 | 0,782 | 0,132 |
| ataque | 60-80 s | 112 | 0,679 | 0,143 |
| ataque | 80+ s | 28 | 0,857 | 0,214 |
| defesa | 0-10 s | 1152 | 0,691 | 0,198 |
| defesa | 10-20 s | 1059 | 0,692 | 0,254 |
| defesa | 20-30 s | 531 | 0,653 | 0,245 |
| defesa | 30-45 s | 430 | 0,663 | 0,241 |
| defesa | 45-60 s | 217 | 0,668 | 0,302 |
| defesa | 60-80 s | 147 | 0,653 | 0,279 |
| defesa | 80+ s | 40 | 0,625 | 0,231 |

A tabela seguinte separa os plants válidos sem nenhuma morte anterior ao plant. A comparação não exige que o ataque consiga um abate depois do plant.

| Sem morte anterior ao plant | Plants | Vitória do ataque |
| --- | --- | --- |
| Não | 4038 | 0,698 |
| Sim | 398 | 0,671 |

## 2. Distância dos aliados

Uma morte fica no grupo sem aliado próximo quando o aliado vivo mais próximo está a mais de 1.000 unidades do jogo. A conversão aproximada é de dez metros, mas essa escala não foi validada nestes arquivos. Se não há aliado vivo, a distância fica sem valor. A tabela usa somente a primeira vítima identificada de cada round.

| Sem aliado próximo | Mortes | Vitória da equipe da vítima | Troca em até 5 s |
| --- | --- | --- | --- |
| Não | 2972 | 0,288 | 0,305 |
| Sim | 3565 | 0,287 | 0,114 |

O controle de distância na interface recalcula os grupos. Taxas de vitória próximas não provam que a posição seja irrelevante. A base registra as mortes e não todas as situações em que um jogador ficou exposto e sobreviveu.

## 3. Posição dos aliados e regiões do mapa

Em grupo significa que há um aliado dentro do limite de distância. Isolado significa que não há aliado próximo. O nome separado do grupo é usado quando, além dessa distância, pelo menos dois aliados estão na mesma grande região do mapa. Estar na mesma região não garante que esses aliados estejam próximos entre si. Essa classificação não identifica um flanco.

A referência por vivos é a taxa de vitória nas mortes da defesa antes do plant com a mesma quantidade de aliados e adversários vivos. A diferença da referência subtrai essa taxa do resultado observado e depois calcula a média do grupo. Ela não compara situações iguais em todos os outros aspectos.

| Posição dos aliados | Mortes | Taxa de vitória | Diferença da referência por vivos |
| --- | --- | --- | --- |
| em grupo | 3252 | 0,438 | 0,009 |
| isolado | 8464 | 0,360 | 0,000 |
| separado do grupo | 1214 | 0,376 | -0,026 |

A ocupação das regiões usa as posições no primeiro abate válido ocorrido em até 20 segundos, incluindo a vítima. É um registro por round com esse evento, e não a posição inicial de todos os rounds. A região ocupada não diz se o jogador segurava uma posição ou avançava.

## 4. Diferenças entre mapas

A diferença de abertura subtrai a taxa de vitória do ataque quando a defesa abre da taxa de vitória do ataque quando ele próprio abre. Os limites de 95% mostram a incerteza estimada por uma aproximação normal. Essa conta trata os rounds como independentes, embora rounds de uma partida compartilhem equipes e condições.

| Mapa | Rounds | Abertura pelo ataque | Vitória do ataque | Diferença de vitória do ataque conforme quem abriu | Limite inferior de 95% | Limite superior de 95% |
| --- | --- | --- | --- | --- | --- | --- |
| Ascent | 1670 | 0,416 | 0,472 | 0,440 | 0,397 | 0,484 |
| Lotus | 1652 | 0,487 | 0,531 | 0,441 | 0,398 | 0,484 |
| Haven | 1399 | 0,460 | 0,538 | 0,410 | 0,362 | 0,457 |
| Split | 703 | 0,474 | 0,538 | 0,439 | 0,373 | 0,505 |
| Sunset | 478 | 0,450 | 0,519 | 0,435 | 0,355 | 0,515 |
| Abyss | 260 | 0,500 | 0,608 | 0,385 | 0,276 | 0,494 |
| Summit | 224 | 0,388 | 0,496 | 0,411 | 0,291 | 0,532 |
| Breeze | 92 | 0,533 | 0,609 | 0,401 | 0,216 | 0,585 |
| Pearl | 60 | 0,350 | 0,350 | 0,560 | 0,336 | 0,784 |
| Fracture | 40 | 0,600 | 0,550 | 0,396 | 0,105 | 0,687 |

Os mapas têm quantidades diferentes de partidas, jogadores e versões do jogo. Por isso, a comparação exige cuidado, sobretudo nos mapas com menos rounds. Intervalos sobrepostos não provam que dois resultados sejam iguais. As regiões usam o nome do ponto conhecido mais próximo no mapa em duas dimensões, sem verificar paredes ou caminhos.

## 5. Combate depois do plant

Pós-plant é o período entre plantar a spike e encerrar o round. Nas mortes desse período, a troca em até cinco segundos aparece junto de taxas de vitória diferentes em várias situações de jogadores vivos. Os gráficos estão na página Trocas e isolamento e indicam quando faltam dados para comparar.

Separar os casos pela quantidade de vivos não revela por que a troca e a vitória aparecem juntas. A própria troca acontece depois da morte e muda o número de vivos. Portanto, essa comparação não mede quanto a proximidade ajudou por permitir a troca.

## 6. Resultado observado e previsão de outras partidas

A primeira tabela usa medidas da própria partida já encerrada. A taxa de acerto informa quantas vezes a equipe favorecida pela medida foi a vencedora. Ela descreve o jogo conhecido e não simula um palpite feito antes dele.

| Medida | Partidas | Taxa de acerto | Limite inferior de 95% | Limite superior de 95% | Jogos sem palpite ou referência |
| --- | --- | --- | --- | --- | --- |
| abertura | 313 | 0,764 | 0,713 | 0,807 | 22 |
| troca | 334 | 0,778 | 0,731 | 0,820 | 1 |
| troca após a primeira morte | 326 | 0,629 | 0,575 | 0,679 | 9 |
| plant sem abate adversário anterior | 195 | 0,605 | 0,535 | 0,671 | 140 |
| defensor separado do grupo | 311 | 0,476 | 0,421 | 0,531 | 24 |
| morte sem aliado próximo | 334 | 0,485 | 0,432 | 0,538 | 1 |
| combinada (todas) | 322 | 0,708 | 0,656 | 0,755 | 13 |
| combinada (abertura + troca) | 335 | 0,824 | 0,779 | 0,861 | 0 |

A medida de plant sem abate adversário anterior conta plants válidos antes de qualquer abate entre adversários no round. Mortes por ambiente ou fogo amigo não impedem essa condição. Ela é diferente do grupo sem nenhuma morte anterior da seção de abertura.

A segunda tabela usa outras partidas para formar o perfil de cada equipe. Elas podem ter ocorrido antes ou depois do jogo avaliado, então essa avaliação serve como comparação retrospectiva.

| Medida | Partidas | Taxa de acerto | Limite inferior de 95% | Limite superior de 95% | Jogos sem palpite ou referência | Acerto do histórico nos mesmos jogos | Diferença de acerto para o histórico | Limite inferior da diferença | Limite superior da diferença | Dados usados |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abertura | 281 | 0,591 | 0,532 | 0,647 | 54 | 0,552 | 0,039 | -0,036 | 0,110 | outras partidas, anteriores ou posteriores |
| troca | 281 | 0,566 | 0,507 | 0,623 | 54 | 0,552 | 0,014 | -0,057 | 0,085 | outras partidas, anteriores ou posteriores |
| troca após a primeira morte | 281 | 0,591 | 0,532 | 0,647 | 54 | 0,552 | 0,039 | -0,043 | 0,125 | outras partidas, anteriores ou posteriores |
| plant sem abate adversário anterior | 275 | 0,556 | 0,497 | 0,614 | 60 | 0,556 | 0,000 | -0,080 | 0,076 | outras partidas, anteriores ou posteriores |
| defensor separado do grupo | 281 | 0,530 | 0,472 | 0,588 | 54 | 0,552 | -0,021 | -0,110 | 0,060 | outras partidas, anteriores ou posteriores |
| morte sem aliado próximo | 281 | 0,509 | 0,451 | 0,567 | 54 | 0,552 | -0,043 | -0,132 | 0,039 | outras partidas, anteriores ou posteriores |
| combinada (todas) | 281 | 0,641 | 0,583 | 0,694 | 54 | 0,552 | 0,089 | 0,018 | 0,160 | outras partidas, anteriores ou posteriores |
| combinada (abertura + troca) | 281 | 0,605 | 0,547 | 0,660 | 54 | 0,552 | 0,053 | -0,011 | 0,117 | outras partidas, anteriores ou posteriores |
| histórico de vitórias com palpite definido | 281 | 0,552 | 0,493 | 0,609 | 54 | Sem dado | Sem dado | Sem dado | Sem dado | outras partidas, anteriores ou posteriores |

A terceira tabela usa apenas jogos anteriores. A escala que combina as medidas também é calculada com dados do passado. Essa é a avaliação que respeita a ordem das partidas.

| Medida | Partidas | Taxa de acerto | Limite inferior de 95% | Limite superior de 95% | Jogos sem palpite ou referência | Acerto do histórico nos mesmos jogos | Diferença de acerto para o histórico | Limite inferior da diferença | Limite superior da diferença | Dados usados |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abertura | 175 | 0,606 | 0,532 | 0,675 | 160 | 0,657 | -0,051 | -0,137 | 0,034 | somente partidas anteriores |
| troca | 175 | 0,669 | 0,596 | 0,734 | 160 | 0,657 | 0,011 | -0,074 | 0,091 | somente partidas anteriores |
| troca após a primeira morte | 175 | 0,560 | 0,486 | 0,631 | 160 | 0,657 | -0,097 | -0,200 | 0,006 | somente partidas anteriores |
| plant sem abate adversário anterior | 170 | 0,541 | 0,466 | 0,614 | 165 | 0,665 | -0,124 | -0,224 | -0,029 | somente partidas anteriores |
| defensor separado do grupo | 175 | 0,531 | 0,458 | 0,604 | 160 | 0,657 | -0,126 | -0,217 | -0,029 | somente partidas anteriores |
| morte sem aliado próximo | 175 | 0,509 | 0,435 | 0,582 | 160 | 0,657 | -0,149 | -0,263 | -0,040 | somente partidas anteriores |
| combinada (todas) | 175 | 0,617 | 0,543 | 0,686 | 160 | 0,657 | -0,040 | -0,131 | 0,051 | somente partidas anteriores |
| combinada (abertura + troca) | 175 | 0,640 | 0,567 | 0,707 | 160 | 0,657 | -0,017 | -0,097 | 0,057 | somente partidas anteriores |
| histórico de vitórias com palpite definido | 175 | 0,657 | 0,584 | 0,723 | 160 | Sem dado | Sem dado | Sem dado | Sem dado | somente partidas anteriores |

O histórico escolhe a equipe com maior taxa de vitória nos jogos de referência. Cada medida é comparada com esse histórico nos mesmos jogos. Se há empate ou faltam dados, não há palpite. A coluna de jogos sem palpite ou referência mostra essas exclusões. O erro entre os palpites feitos é um menos a taxa de acerto. Esse erro não inclui os jogos sem palpite.

A diferença de acerto é a média das diferenças entre os dois palpites em cada jogo avaliado. Os limites estimados ajudam a ver a incerteza, mas equipes se repetem entre partidas. Os intervalos das taxas usam Wilson, um cálculo para proporções que supõe observações independentes. Nenhuma dessas medidas demonstra contribuição causal de um jogador. As posições por correlação de Spearman descrevem a ordem das equipes no mesmo campeonato observado.

CEUB Octopus e CEUB Octopus Vulgaris permanecem separados porque não compartilham jogadores nesta base. A semelhança dos nomes não basta para juntar os elencos.

## 7. Equipamento e rounds após o pistol

Valor do equipamento é a soma do equipamento registrado para a equipe no começo do round, também chamada de loadout nos dados. Esse valor não informa o gasto naquele round nem o dinheiro disponível. A primeira tabela compara a diferença de equipamento entre as equipes.

| Diferença de equipamento entre equipes | Rounds | Taxa de vitória |
| --- | --- | --- |
| ≤ -10k | 1923 | 0,175 |
| (-10k, -5k] | 958 | 0,341 |
| (-5k, -2k] | 1526 | 0,458 |
| (-2k, 2k] | 4399 | 0,500 |
| (2k, 5k] | 1501 | 0,544 |
| (5k, 10k] | 957 | 0,662 |
| > 10k | 1912 | 0,824 |

A tabela seguinte usa somente rounds normais contra adversários com mais de 20 mil de equipamento. A diferença por mil resume a mudança entre faixas vizinhas e não mede o efeito de comprar mais.

| Equipamento da equipe | Rounds | Taxa de vitória | Valor médio do equipamento | Diferença de vitória por mil de equipamento |
| --- | --- | --- | --- | --- |
| até 4k | 12 | 0,000 | 3075,000 | Sem dado |
| (4k, 8k] | 306 | 0,157 | 6676,144 | 0,044 |
| (8k, 12k] | 838 | 0,212 | 9882,757 | 0,017 |
| (12k, 16k] | 511 | 0,303 | 14040,313 | 0,022 |
| (16k, 20k] | 1028 | 0,427 | 18390,175 | 0,029 |
| > 20k | 4780 | 0,500 | 23024,592 | 0,016 |

A referência pelo equipamento vem de uma curva calculada apenas com os rounds normais da seleção. A diferença da referência mostra quanto a taxa observada fica acima ou abaixo dessa curva depois de cada resultado anterior.

| Resultado anterior | Rounds | Taxa de vitória | Referência pelo equipamento | Diferença da referência | Diferença média de equipamento |
| --- | --- | --- | --- | --- | --- |
| perdeu | 4793 | 0,407 | 0,414 | -0,007 | -4398,154 |
| perdeu round fácil (clutch ou thrifty do adversário) | 396 | 0,394 | 0,397 | -0,003 | -5538,636 |
| venceu | 5189 | 0,594 | 0,588 | 0,007 | 4485,190 |

Diferenças pequenas não provam que perder um round não abale a equipe ou que o dinheiro explique toda sequência de resultados. Separar partidas pelo placar final também usa informação que depende dos resultados.

Pistol é o primeiro round de cada metade. Após perder o pistol, os ciclos acompanham o segundo, o terceiro e o quarto round da mesma metade. Eco, compra leve e force são faixas de equipamento registrado, e não decisões de compra confirmadas. As taxas e a soma de vitórias usam os mesmos ciclos completos. Os ciclos interrompidos pelo fim da partida aparecem em uma coluna separada.

| Metade | Faixa de equipamento | Rounds | Ciclos completos | Ciclos interrompidos pelo fim da partida | Ciclos com terceiro round | Ciclos com quarto round | Vitória no segundo round | Vitória no terceiro round | Vitória no quarto round | Vitórias médias do segundo ao quarto round |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| primeira | eco (até 4k) | 305 | 305 | 0 | 305 | 305 | 0,092 | 0,577 | 0,377 | 1,046 |
| primeira | leve (4-8k) | 23 | 23 | 0 | 23 | 23 | 0,174 | 0,435 | 0,391 | 1,000 |
| primeira | force (> 8k) | 7 | 7 | 0 | 7 | 7 | 0,571 | 0,714 | 0,714 | 2,000 |
| segunda | eco (até 4k) | 232 | 228 | 4 | 232 | 228 | 0,118 | 0,680 | 0,364 | 1,162 |
| segunda | leve (4-8k) | 32 | 29 | 3 | 31 | 29 | 0,138 | 0,724 | 0,276 | 1,138 |
| segunda | force (> 8k) | 56 | 35 | 21 | 46 | 35 | 0,543 | 0,743 | 0,543 | 1,829 |

Os ciclos completos dependem de a partida ter durado até o quarto round da metade. Por isso, as médias não mostram o retorno de escolher force ou eco. Quando há taxa anterior ao pistol, ela usa somente rounds anteriores a ele.

## 8. Plant e defuse

Plant é a colocação da spike e defuse é o seu desarme. Um plant é válido nesta análise quando ocorre antes do encerramento observável e ainda há defensores vivos. Registros de plant após eliminação ou em rounds encerrados pelo tempo ficam fora das taxas de combate. Os motivos de exclusão continuam na página de qualidade.

Há 4.436 plants válidos e 1.349 defuses. A taxa de defuse é 30,4%.

A referência por jogadores vivos é a taxa de defuse entre os plants com a mesma quantidade de atacantes e defensores vivos. Por exemplo, um plant com três atacantes e dois defensores é comparado com outros plants em 3 contra 2. A referência de uma linha é a média dessas taxas para os plants daquela linha. A diferença da referência subtrai esse valor da taxa observada.

Os limites de 95% usam Wilson, um cálculo de incerteza para proporções. Ele trata os plants como independentes, embora vários venham da mesma partida. Aqui, os intervalos servem como descrição.

| Tempo até plantar | Plants | Partidas | Taxa de defuse | Referência por jogadores vivos | Diferença da referência | Tempo mediano até plantar em segundos | Limite inferior de 95% | Limite superior de 95% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0-20 s | 218 | 142 | 0,271 | 0,281 | -0,010 | 18,084 | 0,216 | 0,333 |
| 20-40 s | 1758 | 332 | 0,267 | 0,268 | -0,001 | 29,338 | 0,247 | 0,289 |
| 40-60 s | 1103 | 311 | 0,271 | 0,287 | -0,016 | 49,140 | 0,246 | 0,298 |
| 60-80 s | 850 | 295 | 0,336 | 0,330 | 0,007 | 68,953 | 0,306 | 0,369 |
| 80-100 s | 507 | 228 | 0,464 | 0,432 | 0,032 | 88,325 | 0,421 | 0,507 |

| Mapa | Local de plant | Plants | Taxa de defuse | Referência por jogadores vivos | Diferença da referência |
| --- | --- | --- | --- | --- | --- |
| Ascent | A | 479 | 0,311 | 0,295 | 0,016 |
| Ascent | B | 517 | 0,288 | 0,312 | -0,023 |
| Split | A | 235 | 0,277 | 0,312 | -0,035 |
| Split | B | 224 | 0,232 | 0,293 | -0,061 |
| Fracture | A | 15 | 0,200 | 0,357 | -0,157 |
| Fracture | B | 13 | 0,231 | 0,233 | -0,002 |
| Breeze | A | 31 | 0,258 | 0,340 | -0,082 |
| Breeze | B | 31 | 0,226 | 0,297 | -0,071 |
| Abyss | A | 90 | 0,244 | 0,302 | -0,057 |
| Abyss | B | 110 | 0,318 | 0,324 | -0,006 |
| Lotus | A | 453 | 0,291 | 0,274 | 0,018 |
| Lotus | B | 215 | 0,330 | 0,307 | 0,024 |
| Lotus | C | 537 | 0,363 | 0,330 | 0,033 |
| Sunset | A | 145 | 0,234 | 0,259 | -0,024 |
| Sunset | B | 171 | 0,368 | 0,325 | 0,044 |
| Pearl | A | 18 | 0,278 | 0,394 | -0,116 |
| Pearl | B | 17 | 0,588 | 0,365 | 0,223 |
| Summit | A | 89 | 0,360 | 0,326 | 0,034 |
| Summit | B | 79 | 0,405 | 0,347 | 0,058 |
| Haven | A | 385 | 0,281 | 0,293 | -0,012 |
| Haven | B | 142 | 0,394 | 0,361 | 0,033 |
| Haven | C | 440 | 0,268 | 0,279 | -0,011 |

Essa referência considera os vivos, mas não toda a situação do round. Uma diferença entre locais não mede o efeito de escolher onde plantar. A tabela seguinte mostra o tempo entre plant e defuse apenas nos casos em que houve desarme.

| Defuses | Média em segundos | Desvio padrão em segundos | Menor tempo | Um quarto dos casos até | Metade dos casos até | Três quartos dos casos até | Maior tempo |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1349,000 | 29,799 | 8,302 | 8,446 | 23,750 | 30,563 | 36,505 | 44,999 |

Os tempos observados não sustentam a afirmação de que quase todos os defuses acontecem perto do limite de 45 segundos.

## 9. Função do agente

Duelista, iniciador, controlador e sentinela são as funções dos agentes nos metadados locais. A participação nas escalações conta jogadores, sem observadores. A primeira tabela compara essa participação com a presença entre as primeiras vítimas.

| Função | escalações | primeira morte no ataque | primeira morte na defesa |
| --- | --- | --- | --- |
| duelista | 0,361 | 0,523 | 0,464 |
| iniciador | 0,214 | 0,114 | 0,168 |
| controlador | 0,237 | 0,166 | 0,188 |
| sentinela | 0,187 | 0,197 | 0,181 |

A segunda tabela usa somente primeiras vítimas identificadas individualmente. Mortes simultâneas sem uma vítima única ficam fora. A diferença da média da equipe subtrai a taxa de vitória daquela equipe nos outros rounds da mesma partida, sem incluir o round analisado.

| Lado | Função | Rounds | Troca em até 5 s | Vitória da equipe da vítima | Diferença da média da equipe | Limite inferior de 95% | Limite superior de 95% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ataque | duelista | 1853 | 0,280 | 0,317 | -0,152 | 0,297 | 0,339 |
| ataque | iniciador | 403 | 0,310 | 0,342 | -0,115 | 0,298 | 0,390 |
| ataque | controlador | 587 | 0,172 | 0,342 | -0,131 | 0,305 | 0,382 |
| ataque | sentinela | 699 | 0,134 | 0,305 | -0,170 | 0,272 | 0,340 |
| defesa | duelista | 1390 | 0,174 | 0,245 | -0,226 | 0,223 | 0,268 |
| defesa | iniciador | 503 | 0,167 | 0,249 | -0,209 | 0,213 | 0,288 |
| defesa | controlador | 562 | 0,157 | 0,258 | -0,208 | 0,224 | 0,296 |
| defesa | sentinela | 541 | 0,111 | 0,237 | -0,219 | 0,203 | 0,274 |

Essa subtração não separa a influência de força da equipe, lado, equipamento ou adversário. Os limites de 95% usam Wilson e são descritivos. Intervalos sobrepostos não provam que perder primeiro agentes de funções diferentes tenha o mesmo custo.

## 10. Distância e direção dos aliados nas trocas

O teste procura um aliado a até 2.000 unidades do jogo e verifica se sua direção está a até 45 graus da direção do autor do abate. Proximidade e direção compatíveis significam apenas que essas duas condições foram atendidas.

| Lado | Distância e direção do aliado | Mortes | Troca em até 5 s | Vitória da equipe da vítima |
| --- | --- | --- | --- | --- |
| ataque | aliado em alcance olhando para outro lado | 3049 | 0,236 | 0,353 |
| ataque | proximidade e direção compatíveis | 7021 | 0,470 | 0,440 |
| ataque | sem aliado em alcance | 13159 | 0,104 | 0,266 |
| defesa | aliado em alcance olhando para outro lado | 2551 | 0,218 | 0,295 |
| defesa | proximidade e direção compatíveis | 6063 | 0,425 | 0,413 |
| defesa | sem aliado em alcance | 14280 | 0,089 | 0,229 |

A conta usa duas dimensões e não verifica linha de tiro, paredes, fumaça, altura, cegueira, munição ou recarga. Quando falta a direção, ela permanece desconhecida. A ausência de troca não demonstra erro de um jogador.

## 11. Mortes em sequência

Colapso é uma janela de até dez segundos com pelo menos três vítimas distintas da mesma equipe, mortas por adversários válidos, sem abate da própria equipe no intervalo. A tabela também mostra janelas com três mortes e algum abate da própria equipe. Mortes por spike ou ambiente e eventos após o encerramento observável ficam fora.

| Lado | Rounds | Três mortes em 10 s | Três mortes com abate da própria equipe na janela | Rounds com colapso | Vitória sem colapso | Vitória com colapso | Início mediano em segundos |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ataque | 6588 | 0,391 | 0,230 | 0,234 | 0,656 | 0,073 | 35,795 |
| defesa | 6588 | 0,348 | 0,197 | 0,198 | 0,586 | 0,055 | 41,608 |

Se as mortes ocorrem em regiões diferentes, o registro indica múltiplas regiões. A sequência de mortes descreve o que aconteceu, mas não identifica se mira ou posição causou o colapso.

## 12. Dano registrado e arma inicial

As categorias contam quantos adversários causaram dano à vítima durante o round inteiro. Dano de vários adversários não significa fogo simultâneo. O dano recebido pelo autor do abate também é somado no round e não identifica uma reação naquela vida.

| Lado | Adversários que causaram dano | Mortes | Distância média até o autor em unidades | Troca em até 5 s | Vitória da equipe da vítima |
| --- | --- | --- | --- | --- | --- |
| ataque | dano de múltiplos adversários no round | 8987 | 1595,160 | 0,216 | 0,331 |
| ataque | dano de um adversário no round | 14286 | 1670,709 | 0,241 | 0,330 |
| defesa | dano de múltiplos adversários no round | 8433 | 1572,670 | 0,191 | 0,296 |
| defesa | dano de um adversário no round | 14481 | 1588,678 | 0,193 | 0,279 |

Assistência não conta como prova de dano, e registros repetidos de dano são somados. A arma da vítima é a registrada no início do round porque armas coletadas e trocadas não são conhecidas. As distâncias nas mortes, sozinhas, não demonstram bom uso de alcance nem erro.

## 13. Sobrevivência e equipamento no round seguinte

A tabela usa equipes que perderam o round. Sobrevivente é quem está vivo no último registro de posições disponível, incluindo quem voltou à vida. A comparação com o próximo round exclui transições no fim de uma metade e na prorrogação. Os valores de equipamento são os registrados no começo de cada round.

| Sobreviventes | Rounds | Equipamento médio no round | Equipamento médio no próximo round | Vitória no próximo round |
| --- | --- | --- | --- | --- |
| 0 | 5355 | 15087,946 | 16325,901 | 0,373 |
| 1 | 348 | 20067,816 | 17515,374 | 0,382 |
| 2 | 103 | 20463,592 | 18780,097 | 0,379 |
| 3 | 37 | 21870,270 | 20074,324 | 0,568 |
| 4 | 1 | 21900,000 | 24550,000 | 1,000 |

As médias não medem o valor de salvar um jogador. As equipes também diferem em equipamento inicial, bônus e força. Os dados não identificam a intenção de caçar adversários. Recortar apenas vitórias do ataque não mostra se essa escolha compensa nem qual troca de abates seria aceitável.

## 14. Tempo do plant e resultado

Os grupos usam o momento em que a spike foi plantada. Plant em até 40 segundos corresponde ao antigo nome execução rápida, e plant depois de 40 segundos corresponde ao antigo nome default. O relógio não revela a intenção da equipe. Sem plant e plant excluído têm grupos próprios.

| Tempo do plant | Rounds | Taxa de vitória | Tempo mediano até plantar em segundos |
| --- | --- | --- | --- |
| plant em até 40 segundos | 1976 | 0,732 | 28,261 |
| plant após 40 segundos | 2460 | 0,667 | 62,964 |
| sem plant | 1940 | 0,068 | Sem dado |
| plant excluído | 212 | 0,958 | 52,722 |

A próxima tabela usa apenas plants válidos. A referência é a taxa de vitória do ataque nos plants com a mesma quantidade de atacantes e defensores vivos, calculada como na seção de defuse. A diferença subtrai essa referência do resultado observado.

| Tempo do plant | Plants | Taxa de vitória | Referência por jogadores vivos | Diferença da referência |
| --- | --- | --- | --- | --- |
| plant após 40 segundos | 2460 | 0,667 | 0,668 | -0,002 |
| plant em até 40 segundos | 1976 | 0,732 | 0,730 | 0,002 |

Plantar cedo e vencer podem ocorrer juntos sem que um cause o outro. A tabela não registra tentativas que falharam antes do plant. Comparar médias com a equipe atrás ou à frente no placar também não demonstra como cada equipe adapta seu jogo. Um round sem plant pode terminar em vitória ou derrota do ataque.

## 15. Posições no plant e no defuse

A distância mediana da defesa é o valor central das distâncias dos defensores até a spike no plant. Com quantidade par de defensores, usa-se a média dos dois valores centrais. A referência por vivos e seus limites de Wilson seguem a definição da seção de defuse.

| Distância mediana da defesa até a spike | Plants | Partidas | Taxa de defuse | Referência por jogadores vivos | Diferença da referência | Tempo mediano até plantar em segundos | Limite inferior de 95% | Limite superior de 95% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| até 20 m | 432 | 228 | 0,375 | 0,341 | 0,034 | 56,576 | 0,331 | 0,422 |
| 20 a 35 m | 1725 | 325 | 0,336 | 0,317 | 0,019 | 44,316 | 0,314 | 0,358 |
| 35 a 50 m | 1413 | 326 | 0,298 | 0,303 | -0,005 | 41,170 | 0,275 | 0,322 |
| 50 m+ | 866 | 304 | 0,216 | 0,263 | -0,047 | 42,342 | 0,190 | 0,245 |

Nos rounds com defuse, a tabela seguinte conta os atacantes ainda vivos no desarme e a distância do mais próximo. Distâncias são unidades do jogo, com conversão aproximada de 100 unidades por metro. Sem atacante vivo, a distância fica sem dado e o caso entra no grupo sem atacante a até 15 metros.

| Atacantes vivos no defuse | Defuses | Distância mediana até o atacante mais próximo em unidades | Defuses sem atacante a até 15 m |
| --- | --- | --- | --- |
| 0,000 | 1246 | Sem dado | 1,000 |
| 1,000 | 86 | 2301,591 | 0,698 |
| 2,000 | 12 | 1211,260 | 0,333 |
| 3,000 | 5 | 1485,260 | 0,400 |

Olhar para longe da spike não comprova vigiar uma entrada. A distância média até a spike também não mede a distância entre os aliados. Encontrar zero atacantes no defuse descreve o fim das lutas, mas não descarta a influência das posições anteriores. Diferenças pequenas nessas medidas não provam que o posicionamento seja irrelevante.

## Referências de situações parecidas

Na página da rodada, a referência mostra a taxa de vitória em situações observadas em outras partidas. Ela reúne casos com a mesma quantidade de vivos, fase do round, faixa de diferença de equipamento e faixa de tempo. Exige pelo menos 20 rounds de cinco partidas. Quando faltam casos, o valor fica indisponível. A ferramenta não atribui pontos nem crédito individual por mudanças nessa taxa.

A partida aberta na interface fica fora da referência. As outras partidas podem ser posteriores, portanto essa taxa é uma descrição retrospectiva. Ela não foi avaliada como probabilidade de vitória para jogos futuros. As faixas de incerteza usam reamostragem de partidas, ou seja, recalculam a taxa a partir de diferentes seleções das partidas disponíveis.

Os registros de posição existem em eventos e não cobrem todos os instantes do round. Depois do plant, o relógio conta o tempo desde a colocação da spike. A referência não iguala mapa, equipe ou geometria. Se os plants não permitem identificar os lados, a referência fica indisponível. O resultado final apenas informa quem venceu.

## Dados e alcance das conclusões

Os filtros de torneios, versões e qualidade recalculam as referências na interface. Este relatório usa a seleção padrão descrita no início e não muda com esses filtros. Dados ausentes, registros incomuns, versões misturadas e geometria não observada limitam as comparações. A conversão de unidades para metros é aproximada. Nenhum dado ausente foi inventado.

| Cobertura das mortes | Quantidade |
| --- | --- |
| Mortes registradas | 46708 |
| Mortes usadas na análise de combate | 46187 |
| Mortes fora da análise de combate | 521 |
| Com posição do autor do abate | 46123 |
| Com classificação de proximidade calculável | 46123 |
| Com arma inicial conhecida | 46173 |
