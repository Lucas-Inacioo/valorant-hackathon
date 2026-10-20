# Validação da reorganização

Conferência feita em 20 de outubro de 2026, a partir das correções do commit `8641112`. Os dados e os metadados locais foram preservados.

## Código e interface

- 47 testes unitários passaram. A descoberta encontra 48 testes e deixa a integração completa como execução separada.
- 44 cenários de integração passaram nas 12 seções. Eles incluem as duas consultas de round, ressurreição no round 8 de RUSH2_007, troca para uma partida mais curta, sorteio, filtros vazios, três torneios no pós-plant e quatro seleções sem quadrados de plant suficientes.
- Os limites de isolamento de 500 e 3.000 unidades mudaram os grupos e conservaram as 40.207 mortes com aliado vivo usadas nessa comparação.
- Duas regressões de apresentação receberam testes próprios. Categorias ordenadas de tempo continuam formando rótulos de gráficos, e a tradução das tabelas preserva contagens enquanto formata taxas.
- A seção Economia também foi conferida em processo novo após os ajustes finais. O gráfico de sobreviventes inclui casos com cinco jogadores vivos.
- No Chromium, a visão geral, o plant e o round 8 com ressurreição abriram sem exceções nem erros de JavaScript. A tela de 390 pixels manteve largura de conteúdo de 390 pixels.
- Os comandos de metadados e de geração do relatório funcionam nos novos caminhos. `pip check` não encontrou dependências quebradas.

O teste completo de interface foi executado enquanto terminavam ajustes de apresentação. Por isso, seu relatório registra assinaturas de código diferentes no início e no fim. As verificações seguintes de gráficos, Economia e navegador usam o código final.

## Dados e conclusões

A assinatura continua sendo `df71e403d1d939578ca48bb0dac73aa709a99ef6a7593af24576a1d2ee0ffcb9`, igual à do manifesto. O manifesto contém 340 JSONs, incluindo quatro arquivos de metadados.

A base completa tem 336 partidas, 6.618 rounds, 46.753 mortes, 411 jogadores e dois observadores exclusivos. A seleção padrão mantém 335 partidas, 6.588 rounds, 46.708 mortes registradas, 46.187 mortes usadas nas análises de posição e troca, e 4.436 plants válidos.

O relatório foi gerado por `python -m valorant.report --output CONCLUSOES.md`. As 15 seções foram mantidas e os 756 valores numéricos das 25 tabelas anteriores foram conferidos após a reescrita. A tabela adicional de cobertura organiza informações que antes apareciam como um dicionário.

A revisão anterior também percorreu 52.755 eventos do corpus sem encontrar exceção ou quantidade de vivos fora de zero a cinco. A reorganização preserva essas regras de análise e seus testes.

## Reproduzir as verificações

```bash
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -v
VALORANT_RUN_APPTEST=1 PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -p test_app.py -v
.venv/bin/python -m valorant.data.quality
.venv/bin/python -m valorant.report --output CONCLUSOES.md
```

O teste de interface precisa da base local em `data/`. Ele grava um relatório em `/tmp/valorant-app-validation.txt`, ou no caminho definido por `VALORANT_APP_REPORT`.

## Limites dos dados

Os testes verificam o comportamento do código. Eles não demonstram o efeito de decisões individuais, a qualidade de previsões futuras ou a completude da pasta remota. Os registros também não mostram toda a linha de tiro ou a intenção dos jogadores.

Há 127 mortes analisadas mais de 45 segundos após o plant sem um instante final de decisão observável. A conferência mantém essa limitação em vez de inventar um horário. Jogos das mesmas equipes e rounds da mesma partida compartilham condições. Os intervalos mostrados não resumem toda a incerteza das comparações.
