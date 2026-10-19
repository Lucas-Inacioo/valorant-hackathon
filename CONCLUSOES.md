# Conclusões até agora

Base: 336 partidas, 6.618 rounds, 46.753 mortes, 413 jogadores. Toda taxa vem só dos JSONs do desafio. O metadado de mapa (imagem, constantes de conversão e nomes de região) vem da valorant-api.com e serve só para desenhar e nomear.

## 1. O que decide um round é quem abre e se a morte é trocada

- Quem faz a primeira kill vence 71% dos rounds. Ataque abrindo vence 75%, defesa abrindo vence 69%. A defesa abre mais (54% a 58% dos rounds em toda faixa de tempo), mas converte menos.
- Primeira morte trocada (o killer morre em até 5 s) dá 45% de vitória para o time da vítima. Sem troca, 25%.
- O tempo da primeira morte quase não muda o peso. Ataque abrindo vence entre 72% e 79% em todas as faixas de 0 a 80 s. A mediana fica entre 13 e 17 s do round 1 ao 20. O que varia no fim da partida é a cauda (p90), não o round típico.
- Primeira morte depois do plant: feita pelo ataque dá 85% (212 rounds), feita pela defesa dá 53% (187 rounds). Plant sem morte já é round quase ganho.

## 2. Isolamento sozinho não prevê nada. O que ele faz é tirar o trade

- Primeira morte isolada (aliado mais próximo além de 1000 unidades) ou acompanhada: 28,7% de vitória para o time da vítima nos dois casos.
- A chance de trade cai com a distância: 41% com aliado a até 500 unidades, 4% acima de 3000.
- Morte isolada sem trade custa menos que morte acompanhada sem trade (26% contra 22%). Aliado perto que não troca costuma ser duelo perdido em desvantagem local.
- Por lado: atacante isolado não custa mais (vitória do round entre 36% e 41% em toda faixa de distância). Defensor isolado acima de 3000 unidades cai para 24%, e defensores de rounds perdidos morrem bem mais isolados (média 2041 contra 1725).

## 3. Na defesa, flanco é o que custa. Avançar não é

- Defesa antes do plant, pela posição dos aliados vivos na hora da morte: em grupo 44% de vitória, isolado com time espalhado 39%, flanco (nenhum aliado perto e o time inteiro junto em outra área) 27%, com só 13% de trade.
- Morrer em território do adversário (região onde 35% ou menos das posições do começo do round são do seu lado) não custa mais: 37% contra 38% em território próprio.
- No Sunset, Mid Top é território de defesa (79% das posições iniciais são de defensores). As 102 mortes de defensor ali, com 27% de vitória, são holds de meio perdidos, não pushes. Perder o controle do meio custa o round.

## 4. Entre mapas, o prêmio da abertura é igual. O que muda é quanto o ataque consegue abrir

- Impacto da abertura do ataque (vitória do ataque quando ele abre menos quando a defesa abre) fica entre 0,39 e 0,44 em todo mapa com 200 ou mais rounds, com intervalos sobrepostos. Pearl mostra 0,56, mas com 60 rounds o intervalo vai de 0,34 a 0,78.
- Taxa de abertura do ataque difere de verdade entre Ascent (42%, intervalo 39% a 44%) e Lotus (49%, 46% a 51%). Ascent é mapa de defesa (ataque vence 47%), Lotus e Haven são levemente de ataque (53% a 54%).
- No Haven o lado C rende (C Site 80% de vitória ao abrir ali, C Link 87%) e abrir dentro do B Site rende só 60%.

## 5. Pós-plant, só o trade sobrevive ao controle por vivos

- Observação bruta: a defesa vence o round pós-plant com aliados mais perto (mediana 924 contra 1167) e muito mais trocas (60% contra 18%). O ataque mantém a mesma distância de aliado e vence com mais trocas (41% contra 16%) e inimigo mais longe (1555 contra 1361).
- Controlando pela situação (aliados e inimigos vivos na hora da morte), a troca segue grande nos dois lados. Defesa 2v2 vai de 26% para 69%, 3v3 de 33% para 60%. Ataque 1v2 vai de 24% para 60%, 3v4 de 33% para 62%, 4v5 de 41% para 64%.
- As distâncias somem. Defesa em situação equilibrada, por faixa de distância ao aliado: 41%, 44%, 46%, 43%, 40%, 35%. Ataque em situação equilibrada, por distância ao inimigo: entre 70% e 75% em toda faixa.
- Leitura: as distâncias eram proxy de quantos estavam vivos. Proximidade importa só porque permite o trade (44% de troca a até 500 unidades, 9% acima de 3000).

## 6. As métricas explicam a partida, mas preveem pouco

Protocolo sem vazamento (predict.py): nenhuma métrica usa resultado. O lado de cada round vem do time que planta a spike na metade (bate 100% com winningTeamRole), não há contagem de rounds, placar nem ordem, e o rótulo é só teams[].won. Os times são identificados pelo nome do arquivo.

- Dentro da partida, com os rounds embaralhados: o time com mais trocas venceu 79% das partidas, o que abriu mais venceu 76%, e os dois juntos acertam 82%. O acaso, com rótulos embaralhados, chega a 54% no percentil 95. Isolamento sozinho acerta 47%, ou seja, nada.
- Previsão de verdade, com o perfil de cada time calculado só nas outras partidas dele no campeonato (pelo menos duas para cada lado): a combinada acerta entre 61% e 64% de 297 partidas, contra 56% de simplesmente olhar a taxa de vitória do time nas outras partidas.
- Só com partidas anteriores no tempo: 62% a 63% de 213 partidas, e aí a taxa de vitória anterior chega a 65%. As métricas não superam o histórico de resultados.
- Ranking por campeonato (perfil combinado contra taxa de vitória, times com 3 ou mais partidas): Spearman 0,23 no Rush Esquenta, 0,50 no Esquenta 2, 0,97 no Inclusivo e 0,69 no Univavá. O time com 100% de vitórias fica em primeiro no perfil em dois dos quatro campeonatos.
- Leitura: abertura e troca descrevem o resultado quase por construção, por isso explicam tão bem. Mas a capacidade de abrir e trocar flutua de partida para partida, e com 2 a 9 partidas por time no campeonato o perfil prevê em torno de 62%. Serve como diagnóstico do que aconteceu, não como oráculo.
- Cuidado nos nomes: ceub_octopus e ceub_octopus_vulgaris aparecem como times distintos no Univavá, e há variações do tipo inatel, inatel_gray, inatel_dois.

## 7. Dinheiro compra round, e momentum é só dinheiro

- A diferença de loadout entre os times é o que importa, não o valor absoluto. Com diferença de até 2k a vitória é 50%. Com 5k a 10k a mais, 66%. Com mais de 10k, 82%. Entre menos 8k e mais 8k a inclinação é de cerca de 2 pontos de vitória por 1.000 créditos de diferença.
- Contra compra cheia (adversário com 20k+): eco de 4-8k vence 16%, 8-12k vence 21%, 12-16k vence 30%, 16-20k vence 43%, compra cheia vence 50%. O salto que mais rende é de 12-16k para 16-20k (13 pontos por cerca de 4k). De 16-20k para 20k+ são 7 pontos.
- Perder um round não abala. Depois de uma derrota o time vence 40,6% dos rounds normais, e o esperado pelo dinheiro era 40,8%. Depois de perder um round fácil (clutch ou thrifty do adversário), 39,4% contra 39,0% esperado. Depois de vencer, 59,5% contra 59,3%. O efeito do round anterior é inteiramente a economia que ele deixa.
- Sequências de derrotas também não. Com 1 a 3 derrotas seguidas o time fica no esperado pelo dinheiro. Com 4 ou mais fica 6 pontos abaixo, mas só nas partidas desequilibradas (10 pontos abaixo); nas 104 partidas equilibradas o time em sequência de 4 ou mais fica 5 pontos acima do esperado. É time mais fraco, não abalo.
- Pistol: ataque vence 52%, defesa 48% (659 rounds cada).
- Round 2 do perdedor do pistol: eco (até 4k, 539 casos) vence 10% do round 2 e 61% do round 3, somando 1,09 rounds em 2 a 4. Force (8k+, 63 casos) vence 40% do round 2, 58% do round 3 e 57% do round 4, somando 1,55. Sugestivo a favor do force, com três ressalvas: 63 casos, só dá para forçar quem saiu do pistol com dinheiro (pistol disputado), e quem força é time mais fraco no resto da partida (29% de vitória do round 5 em diante contra 44% de quem faz eco), o que torna o resultado mais notável, não menos. Por lado, o force funciona no ataque (52% do round 2, 44 casos) e não na defesa (14%, 14 casos).
- Bônus do vencedor do pistol: vence 86% do round 2 e só 39% do round 3, quando o eco do adversário vira compra cheia.

## 8. Defuse: quem está vivo no plant decide, a posição ajusta

- 4.653 rounds plantados, 29% defusados. Depois do plant o ataque vence por eliminação (2.773) ou detonação (522), e a defesa só por defuse (1.349).
- Vivos no momento do plant explicam quase tudo. Com 5 contra 5, 33% de defuse. Com 3 contra 3, 39%. Com 2 do ataque contra 3 da defesa, 76%. Com 4 do ataque contra 2, 2%. A taxa de defuse de cada posição deve ser lida contra esse esperado.
- Plant tardio é pior para o ataque. Plants entre 80 e 100 s são defusados 44%, contra 25% a 27% antes dos 60 s, e 3,5 pontos disso sobram acima do esperado pelos vivos.
- Por site, com o esperado descontado, os sites são parecidos. As diferenças brutas (Lotus C 36% contra A 27%, Haven B 38% contra C 25%, Sunset B 35% contra A 22%) vêm em boa parte de quantos chegam vivos ao plant em cada site.
- Dentro do site, o plant padrão (a célula de 400 unidades mais usada) é defusado um pouco menos que o esperado: Ascent A 24% contra 26%, Lotus A 19% contra 22%, Haven C 23% contra 26%. Posições fora do padrão são defusadas mais que o esperado, com volume menor: no Lotus C, uma célula com 48 plants dá 58% contra 41% esperado; no Ascent B, uma com 22 plants dá 45% contra 29%. O plant padrão é padrão por um motivo.
- O defuse, quando acontece, leva em mediana 30,6 s depois do plant, com quartis em 24 e 36 s, ou seja, quase sempre no limite dos 45 s.

## 9. A função do agente não muda o custo da primeira morte, muda quem morre e se alguém troca

Função (duelista, iniciador, controlador, sentinela) vem da lista pública de agentes, só para dar nome ao characterId. Acima do time é a vitória do round menos a taxa de rounds que o time da vítima venceu na partida, o que desconta a força do time e do adversário.

- Primeira morte no ataque: o time da vítima ainda vence 32% quando morre o duelista, 31% o sentinela, 34% o iniciador e 35% o controlador. Na defesa, 24%, 24%, 25% e 26%. Os intervalos de 95% se sobrepõem em todos os pares. Descontada a taxa do time, a primeira morte custa entre 11 e 16 pontos no ataque e entre 20 e 22 na defesa, qualquer que seja a função. O lado pesa mais que a função.
- Só primeiras mortes até 20 s: duelista e sentinela no ataque empatam em 29%. Controlador e iniciador ficam em 35%, com 230 a 350 rounds e intervalos que ainda encostam nos dos outros. Sugestivo, não conclusivo.
- Quem morre primeiro, isso sim muda. Duelistas são 36% das escalações e 52% das primeiras mortes no ataque, 46% na defesa. Iniciadores são 21% das escalações e 11% das primeiras mortes no ataque.
- Quem é trocado também muda. Primeira morte do duelista no ataque é trocada 28%, do iniciador 31%, do controlador 18%, do sentinela 14%. Sem troca, a vitória cai para 26% a 31% em qualquer função; com troca sobe para 45% a 53%. O que diferencia o duelista é morrer com o time atrás para trocar, não a morte custar menos.
- Qualquer morte, descontada a situação de vivos, fica dentro de 1 ponto do esperado em todas as funções, e o custo do isolamento fica entre menos 0,3 e mais 4,5 pontos, ou seja, nada que se separe do ruído. Trocar vale de 12 a 16 pontos em qualquer função.
- Por agente, as diferenças são de poucos pontos sobre 200 a 1.000 rounds (Phoenix 27% contra Jett 31% no total, Chamber 27% contra Cypher 32%) e misturam o agente com quem costuma escolhê-lo. Não dá para separar com estes dados.

## Para investigar como ferramenta para jogadores

- Mortes não trocadas por jogador, separando primeira morte do round, flanco e pós-plant.
- Por jogador, quantas vezes é a primeira morte do time e quantas delas são trocadas, comparado com o normal da função do agente dele.
- Mapa individual de mortes na defesa pintado pelo custo da região na base, calculado por mapa, lado e fase, destacando repetição em regiões caras.
- Taxa de abertura do time por mapa e por região, e conversão de abertura por jogador (quem abre, quem morre primeiro, quanto o time converte depois).
- Controle de meio por mapa como métrica de time, a partir das regiões onde morrer custa mais.
- Calculadora de compra: dado o loadout possível e o do adversário, a vitória esperada do round, e o custo de forçar no round 2 por lado.
- Mapa de plants do time: onde planta, quanto é defusado ali contra o esperado pelos vivos, e quais posições fora do padrão custaram rounds.

## Ressalvas

- 100 unidades por metro é suposição, não confirmada.
- Qualquer taxa com menos de 60 rounds é ruído. Os intervalos de 95% estão nas tabelas.
- Tudo é correlação. Regiões caras podem refletir quem vai para lá e o que o adversário fez antes, não só a posição.
