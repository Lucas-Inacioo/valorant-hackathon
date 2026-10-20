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

## 10. Metade das trocas possíveis não acontece

Troca possível (fights.py): no instante da morte, um aliado vivo a até 20 m do killer com o olhar a até 45 graus dele. viewRadians é atan2(dy, dx) nas coordenadas de jogo, calibrado nas kills com erro mediano de 0,3 grau.

- Com um aliado em condição de trocar, a troca sai 47% das vezes no ataque e 43% na defesa. Com aliado em alcance mas olhando para outro lado, 24% e 22%. Sem aliado em alcance, 11% e 9%.
- O round acompanha. Vitória do time da vítima de 44%, 35% e 27% no ataque, e 41%, 30% e 23% na defesa, nas três condições.
- Em 30% das mortes do ataque e 27% da defesa a troca era possível, e em 53% a 57% dessas ela não foi feita. É o erro de execução mais frequente e mais barato de mostrar a um time: a posição estava certa e o olhar também.
- Em 57% a 62% das mortes não havia ninguém em alcance. Esse é o erro de setup, e é onde a isolação (seção 2) de fato pesa.

## 11. Colapso: um em cada cinco rounds acaba em 10 segundos

Colapso (round_style.py): três mortes do mesmo time em 10 s sem nenhuma kill do time nessa janela.

- 23% dos rounds de ataque e 20% dos de defesa têm colapso. Com colapso o time vence 8% no ataque e 6% na defesa. Sem, 66% e 59%. Três mortes em 10 s com alguma kill no meio (uma luta de site normal) acontece em 36% a 39% dos rounds e não é o problema.
- O colapso começa em mediana aos 36 s no ataque e 42 s na defesa, ou seja, no momento da execução ou do retake, não na abertura.
- Por mapa, o ataque colapsa mais no Pearl (42%, 60 rounds), Sunset (26%) e Ascent (25%), e a defesa mais no Haven (23%) e Abyss (23%).
- Por time a taxa vai de 15% a 26% dos rounds. É a métrica coletiva mais direta da base: nenhum colapso depende de mira, todos dependem de onde os três estavam.

## 12. Distância, arma e reação

- Rifle morre a 16 m em mediana e 20% das mortes são a 25 m ou mais. SMG morre a 13 m e 12% a 25 m ou mais. Shotgun a 10 m, com 47% até 10 m. Sniper a 18 m, mas 21% das mortes de sniper são a até 10 m. No agregado os jogadores respeitam o alcance da arma. A tabela por jogador na aba Lutas mostra quem não respeita.
- 44% das mortes são sem reação (a vítima não feriu o killer), 35% em foco (dois ou mais inimigos feriram a vítima) e 21% em duelo. Morrer em duelo deixa o round em 39% no ataque e 32% na defesa. Morrer sem reação, 32% e 26%. Foco é trocado menos (23% contra 28%), porque quem foca está junto.

## 13. Peso econômico da morte e o save

- Na defesa, quando o único jogador mais caro do time morre primeiro (605 rounds), o time vence 23% contra 25%, e descontada a taxa do time fica 5 pontos abaixo do normal da primeira morte (menos 25 contra menos 20). No ataque não há diferença.
- Operator morrendo primeiro na defesa (165 rounds): trocado só 7%, contra 16% das outras primeiras mortes. A vitória bruta é maior (31%) porque time com Operator é time com dinheiro, mas descontada a taxa do time é 2 pontos pior. No ataque são 45 casos, poucos para ler.
- Save: num round perdido fora do fim de metade, cada sobrevivente vale cerca de 1.200 créditos no loadout do round seguinte (16,4k com zero sobreviventes, 17,5k com um, 18,8k com dois, 20,1k com três). A vitória do round seguinte fica em 37% a 38% até dois sobreviventes e sobe para 57% com três, em 37 rounds. O save paga em dinheiro, e só vira round quando o time inteiro sobra.
- Caçar quem guarda: cada sobrevivente vale cerca de 1,2 mil no round seguinte para quem perdeu e cerca de 0,5 mil para quem venceu, porque o vencedor recebe o bônus e recompra. Um atacante morto depois do plant em round vencido custa 431 no loadout seguinte e nada na vitória seguinte. Trocar um atacante por um defensor que estava guardando custa menos da metade do que nega. A caça só deixaria de valer a pena se o caçador morresse quase três vezes para cada abate. Nas lutas depois do plant em rounds vencidos pelo ataque, os atacantes são 24% a 44% das mortes conforme a situação no plant, com 5v1 no pior caso (44%), provavelmente porque cinco pessoas procurando viram cinco alvos. A conta fecha em toda situação. Os arquivos não dizem quem iniciou a luta, então é a soma dos dois lados da conta, não uma comparação entre caçar e não caçar.

## 14. Estilo de round: quem planta rápido vence, e ninguém muda o estilo quando está atrás

Estilo (round_style.py): execução rápida com plant até 40 s, default com plant depois disso, sem plant quando o round acabou antes.

- Execução rápida vence 74% dos rounds (2.034), default 68% (2.619), sem plant 7% (1.885). Sem plant é derrota por construção, então o que compara estilo é rápida contra default.
- Atrás no placar, o ataque fica sem plant em 39% dos rounds. Na frente, em 20%. Entre os rounds plantados, a fração de execução rápida é 42% atrás e 45% na frente. O time que perde não muda o estilo, ele deixa de conseguir plantar.
- Contato cedo (primeira morte até 20 s) acontece em 61% dos rounds e quase não muda a vitória (ataque 51,5% com contato cedo contra 53,7% tarde).
- Os perfis por time variam de 23% a 48% de execução rápida, com vitória por estilo de 55% a 85%. Vira uma frase de identidade por time na aba Rounds do time.

## 15. Setup no plant e retake: a posição não importa, estar vivo importa

- Atacantes a até 15 m da spike no plant, aliados do planter olhando para fora do site e dispersão do ataque não mudam a taxa de defuse além do esperado pelos vivos (menos 1 a mais 3 pontos).
- A distância da defesa no plant muda pouco. Defesa a até 20 m da spike, 3 pontos acima do esperado. A 50 m ou mais, 3 pontos abaixo.
- 92% dos defuses (1.246 de 1.349) acontecem com nenhum atacante vivo. Com um atacante vivo (86 casos), ele estava em mediana a 23 m da spike, e em 70% dos casos a mais de 15 m. O retake é uma eliminação, não um defuse sob pressão. O pós-plant que perde não é um setup errado, é um ataque que morreu.

## Para investigar como ferramenta para jogadores

- Mortes não trocadas por jogador, separando primeira morte do round, flanco e pós-plant.
- Por jogador, quantas vezes é a primeira morte do time e quantas delas são trocadas, comparado com o normal da função do agente dele.
- Mapa individual de mortes na defesa pintado pelo custo da região na base, calculado por mapa, lado e fase, destacando repetição em regiões caras.
- Taxa de abertura do time por mapa e por região, e conversão de abertura por jogador (quem abre, quem morre primeiro, quanto o time converte depois).
- Controle de meio por mapa como métrica de time, a partir das regiões onde morrer custa mais.
- Calculadora de compra: dado o loadout possível e o do adversário, a vitória esperada do round, e o custo de forçar no round 2 por lado.
- Mapa de plants do time: onde planta, quanto é defusado ali contra o esperado pelos vivos, e quais posições fora do padrão custaram rounds.
- Trocas possíveis e não feitas por jogador e por dupla, com o minimapa do instante (quem estava em alcance olhando para o killer e não trocou).
- Colapsos do time por mapa e região, com o replay dos três instantes na aba Partida.

## Ressalvas

- 100 unidades por metro é suposição, não confirmada. Os 20 m da troca possível, os 15 m do site e as faixas de distância dependem dela.
- A arma da vítima é a da compra do round. Arma pega no chão não aparece.
- Qualquer taxa com menos de 60 rounds é ruído. Os intervalos de 95% estão nas tabelas.
- Tudo é correlação. Regiões caras podem refletir quem vai para lá e o que o adversário fez antes, não só a posição.
