# Validação da análise pós-jogo

Conferência feita em 20 de outubro de 2026, sobre a reorganização do commit `8e7fd39`.

## Mudanças conferidas

A navegação reúne a partida inteira em Análise pós-jogo, com as visões Equipe, Jogadores e Lances. Os resumos têm bases de comparação próprias e abrem os rounds e eventos correspondentes. A participação em situações coletivas fica separada das ações individuais.

A navegação de eventos usa um botão para cada registro, com seleção destacada e estado separado por partida e round. O mapa não escreve nomes sobre os jogadores. Usa estrela para quem fez um abate e X para quem morreu naquele instante, incluindo eventos simultâneos. A legenda fica fora da imagem e a tabela preserva a identificação dos jogadores.

A troca de partida também reenvia os valores dos seletores ao navegador. Isso evita que uma equipe da partida anterior continue exibida ou que a escolha de um round deixe o mapa no round anterior.

Os dados originais e o relatório de conclusões não foram alterados nesta etapa.

## Verificações automáticas

- 73 testes passaram na execução padrão, incluindo testes de navegação com Streamlit. A descoberta encontra 74 testes e deixa a integração completa como execução separada.
- O domínio tem 18 testes de pós-jogo. Eles conferem oportunidades por padrão, autoria das trocas, rounds únicos, abertura simultânea, ressurreições, perda de vantagem entre registros, coordenadas ausentes e exclusão de eventos após a decisão.
- Os testes de mapa conferem a ausência de nomes, os destaques de autor e vítima, eventos simultâneos, ressurreição e posições ausentes.
- Quatro testes de navegação conferem os botões, o foco inicial, a escolha preservada, a separação entre partidas e rounds e a ausência de eventos.
- 50 cenários de integração passaram nas 11 seções, com o código estável durante toda a execução. A assinatura do aplicativo e módulos permaneceu `3d881e2de1a6c929a69d22a98cf11970b434da502636b137021217a4154b797b`.
- A integração percorre as três visões, troca de equipe e jogador, saltos de padrões para seus lances, oito eventos do round 8 de RUSH2_007, comparação opcional, troca para uma partida mais curta, filtros vazios e as regressões anteriores de isolamento e plant.
- A conferência no Chromium percorreu as três visões, trocou de partida, abriu o round 8 e alternou entre seus oito botões. Também abriu os detalhes e as associações históricas. Não houve exceção na tela nem erro de JavaScript. A página coube na largura móvel de 390 pixels.

## Dados e conclusões

A assinatura continua sendo `df71e403d1d939578ca48bb0dac73aa709a99ef6a7593af24576a1d2ee0ffcb9`, igual à do manifesto. Ele contém 340 JSONs, incluindo quatro arquivos de metadados.

A base completa tem 336 partidas, 6.618 rounds, 46.753 mortes, 411 jogadores e dois observadores exclusivos. A seleção padrão mantém 335 partidas, 6.588 rounds, 46.708 mortes registradas, 46.187 mortes usadas nas análises de posição e troca, e 4.436 plants válidos.

O documento CONCLUSOES.md continua com as 15 seções da revisão anterior. Os 756 valores numéricos de suas 25 tabelas originais haviam sido conferidos após a reescrita. Esta etapa não recalculou nem alterou esse documento.

## Reproduzir as verificações

```bash
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -v
VALORANT_RUN_APPTEST=1 PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -p test_app.py -v
.venv/bin/python -m valorant.data.quality
```

A integração precisa da base local em `data/`. Ela grava um relatório em `/tmp/valorant-app-validation.txt`, ou no caminho definido por `VALORANT_APP_REPORT`.

## Limites dos dados

As observações ajudam a localizar lances para rever. Elas não demonstram que uma pessoa causou a derrota ou que uma situação próxima no mapa permitiria atirar. Os registros mostram alguns instantes, sem trajetória contínua ou linha de tiro. A arma registrada é a inicial e o dano é agregado por round.

Há 127 mortes analisadas mais de 45 segundos após o plant sem um instante final de decisão observável. A qualidade mantém essa limitação. Os intervalos das comparações históricas também não resumem toda a incerteza de jogos entre as mesmas equipes ou rounds da mesma partida.
