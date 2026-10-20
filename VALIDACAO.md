# Validação das correções — 20/10/2026

Base de código anterior: `0e5189611353c622cf197f8e6f3b5accd4f038c7`. Os JSONs e metadados locais foram preservados; a assinatura e os hashes estão em `data-manifest.json`.

## Regressões automáticas

- **45 testes unitários aprovados**, em dados, eventos, economia/previsão, referências e figuras. A descoberta encontrou 46 testes: a integração com corpus é optativa e foi executada separadamente.
- **38 cenários AppTest aprovados, zero falhas**, percorrendo as 12 seções, as duas visualizações da ferramenta, seleções vazias de torneios/versões, três Rush no pós-plant, os quatro recortes sem células e o slider em 500/3.000 unidades.
- O código de `app.py` permaneceu idêntico entre início e fim desse AppTest: SHA256 `79dcebf385762203db40def83973c19270dbe1cc55eb1d854328bf7694b1a226`.
- A varredura de **336 partidas, 6.618 rounds e 52.755 eventos** não encontrou exceção nem vivos fora de 0–5 nas referências por evento. Valores sem suporte ficaram indisponíveis.
- `pip check` não encontrou dependências quebradas; `git diff --check` não encontrou erros de whitespace.

Comandos de reprodução:

```bash
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -v
VALORANT_RUN_APPTEST=1 PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/valorant-mpl .venv/bin/python -B -m unittest discover -s tests -p test_app.py -v
.venv/bin/python data_quality.py
.venv/bin/python analysis_report.py --output CONCLUSOES.md
```

## Conferência do corpus

Inventário completo: 336 partidas, 6.618 rounds, 46.753 mortes, 411 participantes e dois observadores exclusivos. O manifesto identifica 340 JSONs, incluindo quatro arquivos de metadados.

Recorte analítico padrão: 335 partidas, 6.588 rounds, 46.708 mortes brutas, **46.187 mortes táticas e 4.436 plants válidos**. A partida sinalizada permanece disponível por inclusão explícita; não foi atribuída uma causa não observada.

As classes de dano, referências por vivos, coortes econômicas e conclusões foram regeneradas após a revisão. As 57 resoluções, incluindo mudanças de interpretação, estão em `CORRECOES.md`.

## Limites da validação

Passar nos testes não demonstra causalidade, calibração prospectiva, completude contra o Drive remoto ou disponibilidade de linha de tiro/intenção tática. Há 127 mortes táticas mais de 45 segundos após plant sem uma decisão final observável; a qualidade contabiliza essa limitação em vez de inventar um timestamp. Intervalos exploratórios e resultados agregados não eliminam seleção, confusão ou comparações múltiplas.
