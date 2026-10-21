# Validação do aplicativo

Conferência feita em 20 de outubro de 2026, sobre a reorganização do commit `8e7fd39`.

## Mudanças conferidas

A navegação reúne a partida inteira em Análise pós-jogo, com as visões Equipe, Jogadores e Lances. Os resumos têm bases de comparação próprias e abrem os rounds e eventos correspondentes. A participação em situações coletivas fica separada das ações individuais.

A navegação de eventos usa um botão para cada registro, com seleção destacada e estado separado por partida e round. O mapa não escreve nomes sobre os jogadores. Usa estrela para quem fez um abate e X para quem morreu naquele instante, incluindo eventos simultâneos. A legenda fica fora da imagem e a tabela preserva a identificação dos jogadores.

A troca de partida também reenvia os valores dos seletores ao navegador. Isso evita que uma equipe da partida anterior continue exibida ou que a escolha de um round deixe o mapa no round anterior.

Os botões Ocorrência anterior e Próxima ocorrência percorrem todos os casos do filtro, com contador e troca automática de round e evento. As pontas da sequência ficam desabilitadas. O botão de voltar restaura a visão de origem, o jogador e o round de consulta. Essa origem deixa de valer ao mudar de partida ou equipe.

Os dados originais e o relatório de conclusões não foram alterados nesta etapa.

## Verificações automáticas

- 80 testes passaram na execução padrão, incluindo testes de navegação com Streamlit. A descoberta encontra 81 testes e deixa a integração completa como execução separada.
- O domínio tem 18 testes de pós-jogo. Eles conferem oportunidades por padrão, autoria das trocas, rounds únicos, abertura simultânea, ressurreições, perda de vantagem entre registros, coordenadas ausentes e exclusão de eventos após a decisão.
- Os testes de mapa conferem a ausência de nomes, os destaques de autor e vítima, eventos simultâneos, ressurreição e posições ausentes.
- Quatro testes de navegação conferem os botões, o foco inicial, a escolha preservada, a separação entre partidas e rounds e a ausência de eventos.
- Sete testes de ocorrências conferem a sequência entre rounds, filtros preservados, múltiplas observações no mesmo evento, escolhas manuais de evento, seleção vazia ou com um único caso e retorno à equipe ou ao jogador de origem.
- 55 cenários de integração passaram nas 11 seções, com o código estável durante toda a execução. A assinatura do aplicativo e módulos permaneceu `dba5f92dab4f7a28afbf5b3563151e503bbdba2250b241fe5b76b66eec2867d0`.
- A integração percorre as três visões, troca de equipe e jogador, saltos de padrões para seus lances, oito eventos do round 8 de RUSH2_007, comparação opcional, troca para uma partida mais curta, filtros vazios e as regressões anteriores de isolamento e plant.
- A conferência no Chromium percorreu as três visões, trocou de partida, abriu o round 8 e alternou entre seus oito botões. Também abriu os detalhes e as associações históricas. Não houve exceção na tela nem erro de JavaScript. A página coube na largura móvel de 390 pixels.
- A nova conferência no Chromium percorreu as nove mortes longe do apoio de stockão, nos rounds 1, 2, 7, 9, 13, 16, 18, 19 e 10, com os rounds perdidos primeiro. Conferiu o retorno ao mesmo jogador após mudar o filtro e o retorno à equipe com o round de consulta preservado. Não houve erro de JavaScript e a página continuou sem rolagem horizontal em 390 pixels.

## Dados e conclusões

A assinatura continua sendo `df71e403d1d939578ca48bb0dac73aa709a99ef6a7593af24576a1d2ee0ffcb9`, igual à do manifesto. Ele contém 340 JSONs, incluindo quatro arquivos de metadados.

A base completa tem 336 partidas, 6.618 rounds, 46.753 mortes, 411 jogadores e dois observadores exclusivos. A seleção padrão mantém 335 partidas, 6.588 rounds, 46.708 mortes registradas, 46.187 mortes usadas nas análises de posição e troca, e 4.436 plants válidos.

O documento CONCLUSOES.md continua com as 15 seções da revisão anterior. Os 756 valores numéricos de suas 25 tabelas originais haviam sido conferidos após a reescrita. Esta etapa não recalculou nem alterou esse documento.

## Reproduzir as verificações

A inclusão dos cruzamentos no dashboard passou por 98 testes na execução padrão, com 99 descobertos e a integração completa separada. As verificações novas cobrem os denominadores de troca, rounds únicos, a exigência de vantagem observada, resultados ausentes, o cálculo da referência por vivos no recorte e a restauração dos filtros ao voltar de um exemplo. O Chromium conferiu os painéis de contexto, um exemplo de round vencido no evento correto, o retorno ao torneio selecionado e a largura móvel de 390 pixels, sem erros de JavaScript, inclusive na porta 8501. A integração completa aprovou 66 cenários, incluindo os valores da seleção padrão e os contextos filtrados por torneio. O código permaneceu estável, com assinatura `8628fa75bec89f2943264ed3647afe94a22139230b5863cda4361a7abb7b02b6`. Os critérios e resultados estão em `docs/DASHBOARD.md`.

A inclusão do Dashboard da pesquisa foi conferida com 91 testes aprovados na execução padrão, com 92 descobertos e a integração completa separada. Os 60 cenários de integração passaram com o código estável, cuja assinatura foi `a853f23878264670876188e1af86864922f051d29526f31ac29d0bf43580681a`. A integração inclui o mínimo de partidas, a seleção de torneio, as duas referências de desempenho e o acesso do ranking à partida e equipe corretas.

No Chromium, o dashboard mostrou os números esperados, aplicou os filtros, tratou o ranking vazio e exportou as 59 equipes do recorte padrão. O acesso à análise pós-jogo abriu a equipe escolhida. Não houve erro de JavaScript e a largura móvel de 390 pixels não teve rolagem horizontal. Os resultados e limites estatísticos estão em `docs/DASHBOARD.md`.

Após adicionar o botão Selecionar equipe aleatória, a execução padrão manteve os 80 testes aprovados. Uma conferência específica com AppTest verificou o sorteio entre partidas filtradas, a visão Equipe, a limpeza de lances anteriores e o envio dos valores dos seletores ao navegador. Também verificou três sorteios em um filtro com uma única partida, alternando as equipes, e o filtro vazio sem erro. Os 55 cenários completos descritos acima correspondem à versão anterior à adição desse botão.

```bash
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -v
VALORANT_RUN_APPTEST=1 PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -p test_app.py -v
.venv/bin/python -m valorant.data.quality
```

A integração precisa da base local em `data/`. Ela grava um relatório em `/tmp/valorant-app-validation.txt`, ou no caminho definido por `VALORANT_APP_REPORT`.

## Limites dos dados

As observações ajudam a localizar lances para rever. Elas não demonstram que uma pessoa causou a derrota ou que uma situação próxima no mapa permitiria atirar. Os registros mostram alguns instantes, sem trajetória contínua ou linha de tiro. A arma registrada é a inicial e o dano é agregado por round.

Há 127 mortes analisadas mais de 45 segundos após o plant sem um instante final de decisão observável. A qualidade mantém essa limitação. Os intervalos das comparações históricas também não resumem toda a incerteza de jogos entre as mesmas equipes ou rounds da mesma partida.
