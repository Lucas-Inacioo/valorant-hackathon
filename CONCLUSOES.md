# Conclusões revisadas

Gerado em 20/10/2026 com `python analysis_report.py --output CONCLUSOES.md`. Assinatura dos dados/metadados: `df71e403d1d939578ca48bb0dac73aa709a99ef6a7593af24576a1d2ee0ffcb9`.

Base bruta local: **336 partidas, 6,618 rounds, 46,753 mortes, 411 participantes e 2 observadores exclusivos**. Base analítica padrão: **335 partidas e 6,588 rounds**. Uma partida com 24 rounds iniciais de tempo esgotado sem combate/plant é sinalizada e excluída por padrão, sem presumir sua causa. Os arquivos brutos não foram modificados.

No recorte padrão: 46,708 mortes brutas, 46,187 mortes táticas, 6,578 rounds com abridor definido e 4,436 plants válidos. A qualidade e as perdas por métrica estão em `data-manifest.json` e na seção Qualidade dos dados.

**Como interpretar.** Percentuais decimais nas tabelas são proporções (0,70 = 70%). Todos os resultados são observacionais. Associação, resíduo e sobreposição de intervalos não identificam efeito causal, equivalência nem ausência de mecanismos. Tabelas por morte ponderam cada round pelo número de eventos; contagens não equivalem a rounds independentes. Intervalos Wilson e aproximações normais são descritivos sob independência; o ranking de associações e as referências por estado usam reamostragem por partida. Comparações exploratórias não têm correção por multiplicidade. Não há limiar universal de 60 casos nem validação de uma política de decisão.

## 1. Abertura e troca temporal

A equipe com abertura definida vence 71.3% dos rounds nesta definição. Abertura exige abate adversário antes da decisão observável. Empates entre equipes no mesmo timestamp não recebem abridor: 3 rounds excluídos por esse motivo. Abates simultâneos da mesma equipe definem a equipe, mas não uma vítima/localização individual.

| lado_abriu | faixa | rounds | abriu_venceu | trocada |
| --- | --- | --- | --- | --- |
| ataque | 0-10 s | 905 | 0.767 | 0.154 |
| ataque | 10-20 s | 902 | 0.748 | 0.152 |
| ataque | 20-30 s | 493 | 0.769 | 0.159 |
| ataque | 30-45 s | 365 | 0.718 | 0.198 |
| ataque | 45-60 s | 197 | 0.782 | 0.132 |
| ataque | 60-80 s | 112 | 0.679 | 0.143 |
| ataque | 80+ s | 28 | 0.857 | 0.214 |
| defesa | 0-10 s | 1152 | 0.691 | 0.198 |
| defesa | 10-20 s | 1059 | 0.692 | 0.254 |
| defesa | 20-30 s | 531 | 0.653 | 0.245 |
| defesa | 30-45 s | 430 | 0.663 | 0.241 |
| defesa | 45-60 s | 217 | 0.668 | 0.302 |
| defesa | 60-80 s | 147 | 0.653 | 0.279 |
| defesa | 80+ s | 40 | 0.625 | 0.231 |

Troca temporal significa o autor do abate ser abatido pela equipe adversária em até cinco segundos. Inclui simultaneidade e não prova reação ao primeiro abate; mortes ambientais, friendly fire e eventos posteriores à decisão não são trocas.

Entre plants válidos, a condição sem mortes anteriores ao plant é avaliada sem exigir um abate favorável posterior:

| sem_morte_antes_plant | plants | vitoria_do_ataque |
| --- | --- | --- |
| False | 4038 | 0.698 |
| True | 398 | 0.671 |

## 2. Isolamento e distância dos aliados

| isolada | mortes | vitoria_da_vitima | troca_temporal |
| --- | --- | --- | --- |
| False | 2972 | 0.288 | 0.305 |
| True | 3565 | 0.287 | 0.114 |

O limite padrão é 1.000 unidades; a interface recalcula isolamento e contexto quando o limite muda. Sem aliado vivo, a distância fica indefinida. Igualdade aproximada das médias não demonstra irrelevância do posicionamento; os dados observam mortes, sem registrar todas as exposições bem-sucedidas.

## 3. Contexto dos aliados e ocupação territorial

O antigo rótulo flanco foi substituído por separado do grupo: nenhum aliado próximo e pelo menos dois aliados na mesma grande região. Não identifica rota de flanqueamento nem garante que os aliados estejam próximos entre si. Território usa o primeiro instante de abate válido até 20 segundos, um snapshot por round incluindo vítimas; não são posições iniciais de todos os rounds.

| contexto | mortes | vitoria | residuo_vivos |
| --- | --- | --- | --- |
| em grupo | 3252 | 0.438 | 0.009 |
| isolado | 8464 | 0.360 | 0.000 |
| separado do grupo | 1214 | 0.376 | -0.026 |

O resíduo continua descritivo. A ocupação de uma região não identifica se uma morte individual foi hold ou push, e não estima o risco de avançar.

## 4. Diferenças entre mapas

| mapa | rounds | ataque_abriu | ataque_vence | impacto_da_abertura | impacto_ic95_baixo | impacto_ic95_alto |
| --- | --- | --- | --- | --- | --- | --- |
| Ascent | 1670 | 0.416 | 0.472 | 0.440 | 0.397 | 0.484 |
| Jam | 1652 | 0.487 | 0.531 | 0.441 | 0.398 | 0.484 |
| Triad | 1399 | 0.460 | 0.538 | 0.410 | 0.362 | 0.457 |
| Bonsai | 703 | 0.474 | 0.538 | 0.439 | 0.373 | 0.505 |
| Juliett | 478 | 0.450 | 0.519 | 0.435 | 0.355 | 0.515 |
| Infinity | 260 | 0.500 | 0.608 | 0.385 | 0.276 | 0.494 |
| Plummet | 224 | 0.388 | 0.496 | 0.411 | 0.291 | 0.532 |
| Foxtrot | 92 | 0.533 | 0.609 | 0.401 | 0.216 | 0.585 |
| Pitt | 60 | 0.350 | 0.350 | 0.560 | 0.336 | 0.784 |
| Canyon | 40 | 0.600 | 0.550 | 0.396 | 0.105 | 0.687 |

Amostras e participantes diferem entre mapas e builds. Intervalos sobrepostos não demonstram equivalência; mapas pouco observados exigem leitura proporcional à incerteza. Região é o callout 2D mais próximo, sem geometria de colisão.

## 5. Pós-plant

Troca temporal se associa à vitória posterior em diversas situações de vivos. Controlar pelos vivos não demonstra que a proximidade só importe por permitir troca, nem identifica mediação causal. A troca é uma ação posterior à morte que também altera o número de vivos. Os gráficos detalhados estão em Trocas e isolamento e mostram quando o recorte não tem suporte.

## 6. Associação pós-jogo e previsão temporal

Dentro da partida já observada, taxas de combate descrevem o resultado; isso não é uma previsão antes do jogo.

| metrica | partidas | acerto | ic_baixo | ic_alto | abstencoes_ou_sem_referencia |
| --- | --- | --- | --- | --- | --- |
| abertura | 313 | 0.764 | 0.713 | 0.807 | 22 |
| troca | 334 | 0.778 | 0.731 | 0.820 | 1 |
| troca_1a_morte | 326 | 0.629 | 0.575 | 0.679 | 9 |
| plant_limpo | 195 | 0.605 | 0.535 | 0.671 | 140 |
| flanco_defesa | 311 | 0.476 | 0.421 | 0.531 | 24 |
| isolada | 334 | 0.485 | 0.432 | 0.538 | 1 |
| combinada (todas) | 322 | 0.708 | 0.656 | 0.755 | 13 |
| combinada (abertura + troca) | 335 | 0.824 | 0.779 | 0.861 | 0 |

Avaliação retrospectiva em outras partidas, inclusive posteriores:

| metrica | partidas | acerto | ic_baixo | ic_alto | abstencoes_ou_sem_referencia | base_mesmos_jogos | diferenca_pareada | diferenca_ic_baixo | diferenca_ic_alto | protocolo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abertura | 281 | 0.591 | 0.532 | 0.647 | 54 | 0.552 | 0.039 | -0.036 | 0.110 | retrospectivo fora da partida |
| troca | 281 | 0.566 | 0.507 | 0.623 | 54 | 0.552 | 0.014 | -0.057 | 0.085 | retrospectivo fora da partida |
| troca_1a_morte | 281 | 0.591 | 0.532 | 0.647 | 54 | 0.552 | 0.039 | -0.043 | 0.125 | retrospectivo fora da partida |
| plant_limpo | 275 | 0.556 | 0.497 | 0.614 | 60 | 0.556 | 0.000 | -0.080 | 0.076 | retrospectivo fora da partida |
| flanco_defesa | 281 | 0.530 | 0.472 | 0.588 | 54 | 0.552 | -0.021 | -0.110 | 0.060 | retrospectivo fora da partida |
| isolada | 281 | 0.509 | 0.451 | 0.567 | 54 | 0.552 | -0.043 | -0.132 | 0.039 | retrospectivo fora da partida |
| combinada (todas) | 281 | 0.641 | 0.583 | 0.694 | 54 | 0.552 | 0.089 | 0.018 | 0.160 | retrospectivo fora da partida |
| combinada (abertura + troca) | 281 | 0.605 | 0.547 | 0.660 | 54 | 0.552 | 0.053 | -0.011 | 0.117 | retrospectivo fora da partida |
| histórico (jogos elegíveis; empates abstêm) | 281 | 0.552 | 0.493 | 0.609 | 54 | — | — | — | — | retrospectivo fora da partida |

Previsão usando somente partidas anteriores e escalas estimadas no passado:

| metrica | partidas | acerto | ic_baixo | ic_alto | abstencoes_ou_sem_referencia | base_mesmos_jogos | diferenca_pareada | diferenca_ic_baixo | diferenca_ic_alto | protocolo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| abertura | 175 | 0.606 | 0.532 | 0.675 | 160 | 0.657 | -0.051 | -0.137 | 0.034 | somente anteriores |
| troca | 175 | 0.669 | 0.596 | 0.734 | 160 | 0.657 | 0.011 | -0.074 | 0.091 | somente anteriores |
| troca_1a_morte | 175 | 0.560 | 0.486 | 0.631 | 160 | 0.657 | -0.097 | -0.200 | 0.006 | somente anteriores |
| plant_limpo | 170 | 0.541 | 0.466 | 0.614 | 165 | 0.665 | -0.124 | -0.224 | -0.029 | somente anteriores |
| flanco_defesa | 175 | 0.531 | 0.458 | 0.604 | 160 | 0.657 | -0.126 | -0.217 | -0.029 | somente anteriores |
| isolada | 175 | 0.509 | 0.435 | 0.582 | 160 | 0.657 | -0.149 | -0.263 | -0.040 | somente anteriores |
| combinada (todas) | 175 | 0.617 | 0.543 | 0.686 | 160 | 0.657 | -0.040 | -0.131 | 0.051 | somente anteriores |
| combinada (abertura + troca) | 175 | 0.640 | 0.567 | 0.707 | 160 | 0.657 | -0.017 | -0.097 | 0.057 | somente anteriores |
| histórico (jogos elegíveis; empates abstêm) | 175 | 0.657 | 0.584 | 0.723 | 160 | — | — | — | — | somente anteriores |

Cada modelo é comparado ao histórico nos mesmos jogos com referências identificáveis. Empates são abstensões, com denominadores explícitos. A diferença pareada e seu intervalo são exploratórios; jogos compartilham equipes e não formam uma amostra independente. Não há evidência para tratar as métricas como um oráculo ou contribuição causal. Rankings Spearman descrevem o mesmo campeonato observado.

CEUB Octopus e CEUB Octopus Vulgaris foram mantidos separados: não têm jogadores em comum nesta base. Nomes parecidos não autorizam fundir elencos.

## 7. Equipamento, sequência de resultados e ciclo após pistol

| faixa_diferenca | rounds | vitoria |
| --- | --- | --- |
| ≤ -10k | 1923 | 0.175 |
| (-10k, -5k] | 958 | 0.341 |
| (-5k, -2k] | 1526 | 0.458 |
| (-2k, 2k] | 4399 | 0.500 |
| (2k, 5k] | 1501 | 0.544 |
| (5k, 10k] | 957 | 0.662 |
| > 10k | 1912 | 0.824 |

Contra adversário com equipamento acima de 20 mil, apenas rounds normais:

| faixa_loadout | rounds | vitoria | loadout_medio | ganho_por_1k_a_mais |
| --- | --- | --- | --- | --- |
| até 4k | 12 | 0.000 | 3075.000 | — |
| (4k, 8k] | 306 | 0.157 | 6676.144 | 0.044 |
| (8k, 12k] | 838 | 0.212 | 9882.757 | 0.017 |
| (12k, 16k] | 511 | 0.303 | 14040.313 | 0.022 |
| (16k, 20k] | 1028 | 0.427 | 18390.175 | 0.029 |
| > 20k | 4780 | 0.500 | 23024.592 | 0.016 |

Referência econômica após resultado anterior, ajustada somente em rounds normais da amostra selecionada:

| anterior | rounds | vitoria | esperado_pelo_dinheiro | acima_do_esperado | diferenca_media |
| --- | --- | --- | --- | --- | --- |
| perdeu | 4793 | 0.407 | 0.414 | -0.007 | -4398.154 |
| perdeu round fácil (clutch ou thrifty do adversário) | 396 | 0.394 | 0.397 | -0.003 | -5538.636 |
| venceu | 5189 | 0.594 | 0.588 | 0.007 | 4485.190 |

Resíduos pequenos não demonstram ausência de abalo nem que dinheiro explique inteiramente momentum. Seleção por placar final também depende dos resultados. Loadout não é gasto, dinheiro disponível ou valor causal de comprar mais.

Ciclos separados por metade: taxas e soma na mesma coorte completa; disponibilidade e censura aparecem separadamente.

| metade | compra | rounds | ciclos_completos | ciclos_censurados | disponiveis_round_3 | disponiveis_round_4 | vitoria_round_2 | vitoria_round_3 | vitoria_round_4 | rounds_ganhos_2_a_4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| primeira | eco (até 4k) | 305 | 305 | 0 | 305 | 305 | 0.092 | 0.577 | 0.377 | 1.046 |
| primeira | leve (4-8k) | 23 | 23 | 0 | 23 | 23 | 0.174 | 0.435 | 0.391 | 1.000 |
| primeira | force (> 8k) | 7 | 7 | 0 | 7 | 7 | 0.571 | 0.714 | 0.714 | 2.000 |
| segunda | eco (até 4k) | 232 | 228 | 4 | 232 | 228 | 0.118 | 0.680 | 0.364 | 1.162 |
| segunda | leve (4-8k) | 32 | 29 | 3 | 31 | 29 | 0.138 | 0.724 | 0.276 | 1.138 |
| segunda | force (> 8k) | 56 | 35 | 21 | 46 | 35 | 0.543 | 0.743 | 0.543 | 1.829 |

Ciclos completos continuam selecionados pelo fato de a partida ter durado o horizonte. Esta descrição não identifica o retorno de escolher force/eco. A taxa prévia usa apenas rounds anteriores ao pistol, quando disponíveis.

## 8. Plants válidos, sites e defuse

Há 4,436 plants válidos, 1,349 defuses e taxa 30.4%. Plants após eliminação/sem defensores ou em rounds encerrados pelo tempo ficam fora das taxas táticas, com motivos preservados na qualidade.

| faixa_tempo | plants | partidas | defuse | esperado_pelos_vivos | acima_do_esperado | segundos_plant | defuse_ic95_min | defuse_ic95_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0-20 s | 218 | 142 | 0.271 | 0.281 | -0.010 | 18.084 | 0.216 | 0.333 |
| 20-40 s | 1758 | 332 | 0.267 | 0.268 | -0.001 | 29.338 | 0.247 | 0.289 |
| 40-60 s | 1103 | 311 | 0.271 | 0.287 | -0.016 | 49.140 | 0.246 | 0.298 |
| 60-80 s | 850 | 295 | 0.336 | 0.330 | 0.007 | 68.953 | 0.306 | 0.369 |
| 80-100 s | 507 | 228 | 0.464 | 0.432 | 0.032 | 88.325 | 0.421 | 0.507 |

| mapa | site | plants | defuse | esperado_pelos_vivos | acima_do_esperado |
| --- | --- | --- | --- | --- | --- |
| Ascent | A | 479 | 0.311 | 0.295 | 0.016 |
| Ascent | B | 517 | 0.288 | 0.312 | -0.023 |
| Bonsai | A | 235 | 0.277 | 0.312 | -0.035 |
| Bonsai | B | 224 | 0.232 | 0.293 | -0.061 |
| Canyon | A | 15 | 0.200 | 0.357 | -0.157 |
| Canyon | B | 13 | 0.231 | 0.233 | -0.002 |
| Foxtrot | A | 31 | 0.258 | 0.340 | -0.082 |
| Foxtrot | B | 31 | 0.226 | 0.297 | -0.071 |
| Infinity | A | 90 | 0.244 | 0.302 | -0.057 |
| Infinity | B | 110 | 0.318 | 0.324 | -0.006 |
| Jam | A | 453 | 0.291 | 0.274 | 0.018 |
| Jam | B | 215 | 0.330 | 0.307 | 0.024 |
| Jam | C | 537 | 0.363 | 0.330 | 0.033 |
| Juliett | A | 145 | 0.234 | 0.259 | -0.024 |
| Juliett | B | 171 | 0.368 | 0.325 | 0.044 |
| Pitt | A | 18 | 0.278 | 0.394 | -0.116 |
| Pitt | B | 17 | 0.588 | 0.365 | 0.223 |
| Plummet | A | 89 | 0.360 | 0.326 | 0.034 |
| Plummet | B | 79 | 0.405 | 0.347 | 0.058 |
| Triad | A | 385 | 0.281 | 0.293 | -0.012 |
| Triad | B | 142 | 0.394 | 0.361 | 0.033 |
| Triad | C | 440 | 0.268 | 0.279 | -0.011 |

O ajuste pelos vivos é referência observacional, sem controlar toda a situação. Uma célula mais ou menos desarmada que a referência não recebe um custo causal. Tempo até o defuse, nos casos observados:

| count | mean | std | min | 25% | 50% | 75% | max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1349.000 | 29.799 | 8.302 | 8.446 | 23.750 | 30.563 | 36.505 | 44.999 |

A distribuição não sustenta dizer que quase todos os defuses ocorrem no limite de 45 segundos.

## 9. Função do agente

| funcao | escalações | primeira morte no ataque | primeira morte na defesa |
| --- | --- | --- | --- |
| duelista | 0.361 | 0.523 | 0.464 |
| iniciador | 0.214 | 0.114 | 0.168 |
| controlador | 0.237 | 0.166 | 0.188 |
| sentinela | 0.187 | 0.197 | 0.181 |

| lado | funcao | rounds | trocada | vitoria_da_vitima | acima_do_time | ic95_baixo | ic95_alto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ataque | duelista | 1853 | 0.280 | 0.317 | -0.152 | 0.297 | 0.339 |
| ataque | iniciador | 403 | 0.310 | 0.342 | -0.115 | 0.298 | 0.390 |
| ataque | controlador | 587 | 0.172 | 0.342 | -0.131 | 0.305 | 0.382 |
| ataque | sentinela | 699 | 0.134 | 0.305 | -0.170 | 0.272 | 0.340 |
| defesa | duelista | 1390 | 0.174 | 0.245 | -0.226 | 0.223 | 0.268 |
| defesa | iniciador | 503 | 0.167 | 0.249 | -0.209 | 0.213 | 0.288 |
| defesa | controlador | 562 | 0.157 | 0.258 | -0.208 | 0.224 | 0.296 |
| defesa | sentinela | 541 | 0.111 | 0.237 | -0.219 | 0.203 | 0.274 |

Escalações contam participantes, sem observadores. Primeira vítima por função exige identificação individual, excluindo simultaneidade. Sobreposição de intervalos não prova igualdade do custo; subtrair a taxa da equipe na mesma partida não controla independentemente força, lado, economia ou adversário.

## 10. Geometria e troca temporal

| lado | troca_possivel | mortes | trocada | venceu_round |
| --- | --- | --- | --- | --- |
| ataque | aliado em alcance olhando para outro lado | 3049 | 0.236 | 0.353 |
| ataque | proximidade e direção compatíveis | 7021 | 0.470 | 0.440 |
| ataque | sem aliado em alcance | 13159 | 0.104 | 0.266 |
| defesa | aliado em alcance olhando para outro lado | 2551 | 0.218 | 0.295 |
| defesa | proximidade e direção compatíveis | 6063 | 0.425 | 0.413 |
| defesa | sem aliado em alcance | 14280 | 0.089 | 0.229 |

A heurística testa distância 2D até 2.000 unidades e direção até 45 graus. Não verifica linha de tiro, parede, smoke, altura, cegueira, munição ou recarga. Não transforma ausência de troca em erro demonstrado do jogador. Direções ausentes permanecem desconhecidas.

## 11. Colapsos observados

| lado | rounds | tres_em_10s | tres_com_abate | colapsos | venceu_sem_colapso | venceu_com_colapso | inicio_mediano |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ataque | 6588 | 0.391 | 0.230 | 0.234 | 0.656 | 0.073 | 35.795 |
| defesa | 6588 | 0.348 | 0.197 | 0.198 | 0.586 | 0.055 | 41.608 |

O detector exige três vítimas distintas em abates adversários válidos. Janelas com abate no meio são contadas separadamente. Mortes por Bomb/ambiente e eventos após decisão não são colapso tático. Regiões diferentes geram múltiplas regiões, sem desempate alfabético. A definição temporal não demonstra que mira ou posicionamento causem todos os colapsos.

## 12. Arma inicial, distância e dano agregado

| lado | classe_luta | mortes | dist_killer | trocada | venceu_round |
| --- | --- | --- | --- | --- | --- |
| ataque | dano de múltiplos adversários no round | 8987 | 1595.160 | 0.216 | 0.331 |
| ataque | dano de um adversário no round | 14286 | 1670.709 | 0.241 | 0.330 |
| defesa | dano de múltiplos adversários no round | 8433 | 1572.670 | 0.191 | 0.296 |
| defesa | dano de um adversário no round | 14481 | 1588.678 | 0.193 | 0.279 |

As classes descrevem quantidade de adversários com dano registrado na vítima durante o round, sem afirmar foco simultâneo. Dano no autor também é agregado no round, sem identificar reação naquela vida. Assistência não é tratada como prova de dano; entradas repetidas são somadas. A arma da vítima é a do equipamento inicial, pois trocas/armas coletadas não são registradas. Distâncias apenas nas mortes não comprovam disciplina ou erro de alcance.

## 13. Equipamento da vítima, sobrevivência e continuidade econômica

| sobreviventes | rounds | loadout | loadout_seguinte | venceu_seguinte |
| --- | --- | --- | --- | --- |
| 0 | 5355 | 15087.946 | 16325.901 | 0.373 |
| 1 | 348 | 20067.816 | 17515.374 | 0.382 |
| 2 | 103 | 20463.592 | 18780.097 | 0.379 |
| 3 | 37 | 21870.270 | 20074.324 | 0.568 |
| 4 | 1 | 21900.000 | 24550.000 | 1.000 |

Sobreviventes vêm do último estado observável, incluindo retorno à vida. A continuidade exclui fins de metade e prorrogação. As médias não representam o preço causal de salvar alguém, pois equipamento inicial, bônus e força diferem. Caça não é identificada; selecionar só vitórias do ataque não permite afirmar que uma política de caçar compensa nem fixar uma razão de mortes/abates.

## 14. Estilo observado e placar

| estilo | rounds | venceu | plant_mediano |
| --- | --- | --- | --- |
| execução rápida | 1976 | 0.732 | 28.261 |
| default | 2460 | 0.667 | 62.964 |
| sem plant | 1940 | 0.068 | — |
| plant excluído | 212 | 0.958 | 52.722 |

Comparação entre plants válidos, aplicando a mesma referência por vivos usada na análise de posição:

| estilo | plants | vitoria | esperado | residuo |
| --- | --- | --- | --- | --- |
| default | 2460 | 0.667 | 0.668 | -0.002 |
| execução rápida | 1976 | 0.732 | 0.730 | 0.002 |

Não se conclui que plantar rápido causa vitória. O timestamp do plant não registra intenção nem uma execução que falhou antes de plantar. Comparar médias agregadas atrás/na frente também não demonstra que nenhuma equipe adapte seu estilo. Sem plant é um desfecho observado, não derrota por definição. Plant excluído fica em categoria própria.

## 15. Medidas de setup e estado no defuse

| faixa_defesa | plants | partidas | defuse | esperado_pelos_vivos | acima_do_esperado | segundos_plant | defuse_ic95_min | defuse_ic95_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| até 20 m | 432 | 228 | 0.375 | 0.341 | 0.034 | 56.576 | 0.331 | 0.422 |
| 20 a 35 m | 1725 | 325 | 0.336 | 0.317 | 0.019 | 44.316 | 0.314 | 0.358 |
| 35 a 50 m | 1413 | 326 | 0.298 | 0.303 | -0.005 | 41.170 | 0.275 | 0.322 |
| 50 m+ | 866 | 304 | 0.216 | 0.263 | -0.047 | 42.342 | 0.190 | 0.245 |

| atacantes_vivos_no_defuse | defuses | mais_proximo_mediano | ninguem_a_15_m |
| --- | --- | --- | --- |
| 0.000 | 1246 | — | 1.000 |
| 1.000 | 86 | 2301.591 | 0.698 |
| 2.000 | 12 | 1211.260 | 0.333 |
| 3.000 | 5 | 1485.260 | 0.400 |

A mediana de distância usa a média dos dois valores centrais quando há quantidade par de defensores. Olhar contrário à spike não comprova vigiar entradas; raio médio até a spike não é dispersão entre aliados. O estado sem atacantes no defuse descreve o fim das lutas, sem excluir influência do setup anterior. Ausência de grande resíduo em proxies não demonstra irrelevância de posição.

## Referências por estado e limites de uso

A ferramenta foi convertida em contagens e referências empíricas, sem saldos de pontos ou crédito individual. A partida consultada é excluída da referência. Cada contexto mantém vivos, fase, faixa de diferença de equipamento e relógio; exige ao menos 20 rounds e cinco partidas. Falta de suporte permanece indisponível, sem fallback para uma população diferente. Os estados são observados em eventos; não representam todos os instantes possíveis de um round. O relógio pós-plant é tempo decorrido desde o plant. Mapa, equipe e geometria não são controlados por essa referência. Lados não identificados pela inferência baseada em plants ficam sem referência nessa ferramenta. O resultado final é factual e não pontuado. Excluir a partida consultada evita reutilizar seus resultados nessa referência, mas não é uma avaliação temporal: outras partidas podem ser posteriores. Não há teste de calibração ou erro probabilístico fora da amostra, e os valores não constituem probabilidades prospectivas calibradas.

A seleção de torneios, versões e qualidade recalcula as referências analíticas. Este documento é um retrato da amostra padrão descrita acima; não muda quando alguém filtra a interface. Dados ausentes, anomalias, builds misturados, geometria não observada e conversão aproximada de 100 unidades por metro continuam limites declarados. Não foram coletados novos dados para inventar as variáveis ausentes.

Cobertura de lutas no recorte: `{'mortes_brutas': 46708, 'mortes_diagnostico': 46187, 'mortes_excluidas': 521, 'com_posicao_autor': 46123, 'com_proxy_geometrica': 46123, 'com_arma_inicial_conhecida': 46173}`.
