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

## Para investigar como ferramenta para jogadores

- Mortes não trocadas por jogador, separando primeira morte do round, flanco e pós-plant.
- Mapa individual de mortes na defesa pintado pelo custo da região na base, calculado por mapa, lado e fase, destacando repetição em regiões caras.
- Taxa de abertura do time por mapa e por região, e conversão de abertura por jogador (quem abre, quem morre primeiro, quanto o time converte depois).
- Controle de meio por mapa como métrica de time, a partir das regiões onde morrer custa mais.

## Ressalvas

- 100 unidades por metro é suposição, não confirmada.
- Qualquer taxa com menos de 60 rounds é ruído. Os intervalos de 95% estão nas tabelas.
- Tudo é correlação. Regiões caras podem refletir quem vai para lá e o que o adversário fez antes, não só a posição.
