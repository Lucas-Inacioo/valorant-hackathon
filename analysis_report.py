"""Regenera as conclusões com a amostra elegível e as definições atuais.

Somente a saída explicitamente solicitada é escrita. Os JSONs são preservados.
"""
import argparse
from datetime import datetime
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from agent_roles import first_death_by_role, role_share
from data_quality import data_signature, dataset_quality, eligible_match_ids
from economy import after_previous_round, build_rounds_table, pistol_by_side, second_round_cycle, versus_full_buy, win_rate_by_loadout
from fights import build_fights_table, fight_class_summary, fight_coverage, save_effect, trade_possibility_summary
from first_blood import first_blood_table, summary_by_map, win_rate_by_time
from plants import build_plants_table, summary_by_plant_time, summary_by_site
from predict import forecast_accuracy, in_match_accuracy, load_matches, match_pairs, team_features, tournament_ranking
from round_style import build_round_styles, collapse_summary, style_summary
from setups import build_setups_table, defuse_by, retake_summary
from solo_deaths import build_deaths_table, with_solo_flag


def markdown_table(table, limit=None):
    """Render simples, sem dependência opcional tabulate."""
    if table.empty:
        return "Sem amostra suficiente."
    frame = table.reset_index() if table.index.name or isinstance(table.index, pd.MultiIndex) else table.copy()
    if limit:
        frame = frame.head(limit)
    def cell(value):
        if pd.isna(value):
            return "—"
        if isinstance(value, (float,)):
            return f"{value:.3f}"
        return str(value).replace("|", "/").replace("\n", " ")
    headers = list(map(str, frame.columns))
    rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    rows += ["| " + " | ".join(cell(value) for value in row) + " |" for row in frame.itertuples(index=False, name=None)]
    return "\n".join(rows)


def build_report():
    ids = eligible_match_ids()
    quality = dataset_quality()
    selected_quality = dataset_quality(match_ids=ids)
    deaths = build_deaths_table(match_ids=ids)
    rounds = build_rounds_table(match_ids=ids)
    fights = build_fights_table(deaths, match_ids=ids)
    tactical = fights[fights["diagnostico_tatico"]].copy()
    first = first_blood_table(deaths)
    plants = build_plants_table(match_ids=ids)
    setups = build_setups_table(match_ids=ids)
    matches = load_matches(match_ids=ids)
    styles = build_round_styles(deaths, rounds, matches, match_ids=ids)
    features = team_features(deaths, matches)
    pairs = match_pairs(matches, features)
    now = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y")
    total, selected = quality["totals"], selected_quality["totals"]
    blocks = [
        "# Conclusões revisadas",
        f"Gerado em {now} com `python analysis_report.py --output CONCLUSOES.md`. Assinatura dos dados/metadados: `{data_signature()}`.",
        f"Base bruta local: **{total['matches']} partidas, {total['rounds']:,} rounds, {total['deaths']:,} mortes, {total['participants']} participantes e {total['observers']} observadores exclusivos**. Base analítica padrão: **{selected['matches']} partidas e {selected['rounds']:,} rounds**. Uma partida com 24 rounds iniciais de tempo esgotado sem combate/plant é sinalizada e excluída por padrão, sem presumir sua causa. Os arquivos brutos não foram modificados.",
        f"No recorte padrão: {len(deaths):,} mortes brutas, {len(tactical):,} mortes táticas, {len(first):,} rounds com abridor definido e {len(plants):,} plants válidos. A qualidade e as perdas por métrica estão em `data-manifest.json` e na seção Qualidade dos dados.",
        "**Como interpretar.** Percentuais decimais nas tabelas são proporções (0,70 = 70%). Todos os resultados são observacionais. Associação, resíduo e sobreposição de intervalos não identificam efeito causal, equivalência nem ausência de mecanismos. Tabelas por morte ponderam cada round pelo número de eventos; contagens não equivalem a rounds independentes. Intervalos Wilson e aproximações normais são descritivos sob independência; o ranking de associações e as referências por estado usam reamostragem por partida. Comparações exploratórias não têm correção por multiplicidade. Não há limiar universal de 60 casos nem validação de uma política de decisão.",
        "## 1. Abertura e troca temporal",
        f"A equipe com abertura definida vence {first['abriu_venceu'].mean():.1%} dos rounds nesta definição. Abertura exige abate adversário antes da decisão observável. Empates entre equipes no mesmo timestamp não recebem abridor: {first.attrs.get('rounds_abertura_ambigua', 0)} rounds excluídos por esse motivo. Abates simultâneos da mesma equipe definem a equipe, mas não uma vítima/localização individual.",
        markdown_table(win_rate_by_time(first)),
        "Troca temporal significa o autor do abate ser abatido pela equipe adversária em até cinco segundos. Inclui simultaneidade e não prova reação ao primeiro abate; mortes ambientais, friendly fire e eventos posteriores à decisão não são trocas.",
    ]
    # Compara o estado no plant sem condicionar em quem fará o próximo abate.
    first_death_time = deaths.groupby(["match_id", "round"])["segundos"].min().to_dict()
    plant_clean = plants.copy()
    plant_clean["sem_morte_antes_plant"] = [first_death_time.get((mid, number), math.inf) >= timestamp for mid, number, timestamp in zip(plant_clean["match_id"], plant_clean["round"], plant_clean["segundos_plant"])]
    blocks += ["Entre plants válidos, a condição sem mortes anteriores ao plant é avaliada sem exigir um abate favorável posterior:",
               markdown_table(plant_clean.groupby("sem_morte_antes_plant").agg(plants=("round", "size"), vitoria_do_ataque=("ataque_venceu", "mean"))),
               "## 2. Isolamento e distância dos aliados"]
    allied = with_solo_flag(deaths, 1000)
    opening = allied[allied["primeira_vitima_unica"]] if "primeira_vitima_unica" in allied else allied.iloc[:0]
    blocks += [markdown_table(opening.groupby("isolada").agg(mortes=("vitima", "size"), vitoria_da_vitima=("venceu_round", "mean"), troca_temporal=("trocada", "mean"))),
               "O limite padrão é 1.000 unidades; a interface recalcula isolamento e contexto quando o limite muda. Sem aliado vivo, a distância fica indefinida. Igualdade aproximada das médias não demonstra irrelevância do posicionamento; os dados observam mortes, sem registrar todas as exposições bem-sucedidas.",
               "## 3. Contexto dos aliados e ocupação territorial",
               "O antigo rótulo flanco foi substituído por separado do grupo: nenhum aliado próximo e pelo menos dois aliados na mesma grande região. Não identifica rota de flanqueamento nem garante que os aliados estejam próximos entre si. Território usa o primeiro instante de abate válido até 20 segundos, um snapshot por round incluindo vítimas; não são posições iniciais de todos os rounds."]
    pre = allied[(allied["lado"] == "defesa") & (allied["fase"] == "pré-plant")].copy()
    pre["contexto"] = pre["contexto"].replace({"flanco": "separado do grupo"})
    if not pre.empty:
        pre["residuo_vivos"] = pre["venceu_round"].astype(float) - pre.groupby(["aliados_vivos", "inimigos_vivos"])["venceu_round"].transform("mean")
    blocks += [markdown_table(pre.groupby("contexto").agg(mortes=("vitima", "size"), vitoria=("venceu_round", "mean"), residuo_vivos=("residuo_vivos", "mean"))),
               "O resíduo continua descritivo. A ocupação de uma região não identifica se uma morte individual foi hold ou push, e não estima o risco de avançar.",
               "## 4. Diferenças entre mapas",
               markdown_table(summary_by_map(first)[["rounds", "ataque_abriu", "ataque_vence", "impacto_da_abertura", "impacto_ic95_baixo", "impacto_ic95_alto"]]),
               "Amostras e participantes diferem entre mapas e builds. Intervalos sobrepostos não demonstram equivalência; mapas pouco observados exigem leitura proporcional à incerteza. Região é o callout 2D mais próximo, sem geometria de colisão.",
               "## 5. Pós-plant",
               "Troca temporal se associa à vitória posterior em diversas situações de vivos. Controlar pelos vivos não demonstra que a proximidade só importe por permitir troca, nem identifica mediação causal. A troca é uma ação posterior à morte que também altera o número de vivos. Os gráficos detalhados estão em Trocas e isolamento e mostram quando o recorte não tem suporte.",
               "## 6. Associação pós-jogo e previsão temporal",
               "Dentro da partida já observada, taxas de combate descrevem o resultado; isso não é uma previsão antes do jogo.",
               markdown_table(in_match_accuracy(pairs)),
               "Avaliação retrospectiva em outras partidas, inclusive posteriores:",
               markdown_table(forecast_accuracy(matches, features, only_previous=False)),
               "Previsão usando somente partidas anteriores e escalas estimadas no passado:",
               markdown_table(forecast_accuracy(matches, features, only_previous=True)),
               "Cada modelo é comparado ao histórico nos mesmos jogos com referências identificáveis. Empates são abstensões, com denominadores explícitos. A diferença pareada e seu intervalo são exploratórios; jogos compartilham equipes e não formam uma amostra independente. Não há evidência para tratar as métricas como um oráculo ou contribuição causal. Rankings Spearman descrevem o mesmo campeonato observado.",
               "CEUB Octopus e CEUB Octopus Vulgaris foram mantidos separados: não têm jogadores em comum nesta base. Nomes parecidos não autorizam fundir elencos.",
               "## 7. Equipamento, sequência de resultados e ciclo após pistol"]
    _, differences = win_rate_by_loadout(rounds)
    cycle, _ = second_round_cycle(rounds)
    blocks += [markdown_table(differences),
               "Contra adversário com equipamento acima de 20 mil, apenas rounds normais:",
               markdown_table(versus_full_buy(rounds)),
               "Referência econômica após resultado anterior, ajustada somente em rounds normais da amostra selecionada:",
               markdown_table(after_previous_round(rounds)),
               "Resíduos pequenos não demonstram ausência de abalo nem que dinheiro explique inteiramente momentum. Seleção por placar final também depende dos resultados. Loadout não é gasto, dinheiro disponível ou valor causal de comprar mais.",
               "Ciclos separados por metade: taxas e soma na mesma coorte completa; disponibilidade e censura aparecem separadamente.",
               markdown_table(cycle[["rounds", "ciclos_completos", "ciclos_censurados", "disponiveis_round_3", "disponiveis_round_4", "vitoria_round_2", "vitoria_round_3", "vitoria_round_4", "rounds_ganhos_2_a_4"]]),
               "Ciclos completos continuam selecionados pelo fato de a partida ter durado o horizonte. Esta descrição não identifica o retorno de escolher force/eco. A taxa prévia usa apenas rounds anteriores ao pistol, quando disponíveis.",
               "## 8. Plants válidos, sites e defuse",
               f"Há {len(plants):,} plants válidos, {int(plants['defusada'].sum()):,} defuses e taxa {plants['defusada'].mean():.1%}. Plants após eliminação/sem defensores ou em rounds encerrados pelo tempo ficam fora das taxas táticas, com motivos preservados na qualidade.",
               markdown_table(summary_by_plant_time(plants)),
               markdown_table(summary_by_site(plants)[["plants", "defuse", "esperado_pelos_vivos", "acima_do_esperado"]]),
               "O ajuste pelos vivos é referência observacional, sem controlar toda a situação. Uma célula mais ou menos desarmada que a referência não recebe um custo causal. Tempo até o defuse, nos casos observados:",
               markdown_table(plants.loc[plants["defusada"], ["segundos_ate_defuse"]].describe().T),
               "A distribuição não sustenta dizer que quase todos os defuses ocorrem no limite de 45 segundos.",
               "## 9. Função do agente",
               markdown_table(role_share(deaths)),
               markdown_table(first_death_by_role(deaths)),
               "Escalações contam participantes, sem observadores. Primeira vítima por função exige identificação individual, excluindo simultaneidade. Sobreposição de intervalos não prova igualdade do custo; subtrair a taxa da equipe na mesma partida não controla independentemente força, lado, economia ou adversário.",
               "## 10. Geometria e troca temporal",
               markdown_table(trade_possibility_summary(fights, ["lado"])),
               "A heurística testa distância 2D até 2.000 unidades e direção até 45 graus. Não verifica linha de tiro, parede, smoke, altura, cegueira, munição ou recarga. Não transforma ausência de troca em erro demonstrado do jogador. Direções ausentes permanecem desconhecidas.",
               "## 11. Colapsos observados",
               markdown_table(collapse_summary(styles, ["lado"])),
               "O detector exige três vítimas distintas em abates adversários válidos. Janelas com abate no meio são contadas separadamente. Mortes por Bomb/ambiente e eventos após decisão não são colapso tático. Regiões diferentes geram múltiplas regiões, sem desempate alfabético. A definição temporal não demonstra que mira ou posicionamento causem todos os colapsos.",
               "## 12. Arma inicial, distância e dano agregado",
               markdown_table(fight_class_summary(fights, ["lado"])),
               "As classes descrevem quantidade de adversários com dano registrado na vítima durante o round, sem afirmar foco simultâneo. Dano no autor também é agregado no round, sem identificar reação naquela vida. Assistência não é tratada como prova de dano; entradas repetidas são somadas. A arma da vítima é a do equipamento inicial, pois trocas/armas coletadas não são registradas. Distâncias apenas nas mortes não comprovam disciplina ou erro de alcance.",
               "## 13. Equipamento da vítima, sobrevivência e continuidade econômica",
               markdown_table(save_effect(rounds, fights)),
               "Sobreviventes vêm do último estado observável, incluindo retorno à vida. A continuidade exclui fins de metade e prorrogação. As médias não representam o preço causal de salvar alguém, pois equipamento inicial, bônus e força diferem. Caça não é identificada; selecionar só vitórias do ataque não permite afirmar que uma política de caçar compensa nem fixar uma razão de mortes/abates.",
               "## 14. Estilo observado e placar"]
    attack_style, _ = style_summary(styles)
    plant_comparison = plants.copy()
    plant_comparison["estilo"] = plant_comparison["segundos_plant"].map(lambda value: "execução rápida" if value <= 40 else "default")
    plant_comparison["esperado_ataque"] = plant_comparison["esperado_vitoria_vivos"]
    plant_comparison["residuo"] = plant_comparison["ataque_venceu"].astype(float) - plant_comparison["esperado_ataque"]
    blocks += [markdown_table(attack_style),
               "Comparação entre plants válidos, aplicando a mesma referência por vivos usada na análise de posição:",
               markdown_table(plant_comparison.groupby("estilo").agg(plants=("round", "size"), vitoria=("ataque_venceu", "mean"), esperado=("esperado_ataque", "mean"), residuo=("residuo", "mean"))),
               "Não se conclui que plantar rápido causa vitória. O timestamp do plant não registra intenção nem uma execução que falhou antes de plantar. Comparar médias agregadas atrás/na frente também não demonstra que nenhuma equipe adapte seu estilo. Sem plant é um desfecho observado, não derrota por definição. Plant excluído fica em categoria própria.",
               "## 15. Medidas de setup e estado no defuse",
               markdown_table(defuse_by(setups, "faixa_defesa")),
               markdown_table(retake_summary(setups)),
               "A mediana de distância usa a média dos dois valores centrais quando há quantidade par de defensores. Olhar contrário à spike não comprova vigiar entradas; raio médio até a spike não é dispersão entre aliados. O estado sem atacantes no defuse descreve o fim das lutas, sem excluir influência do setup anterior. Ausência de grande resíduo em proxies não demonstra irrelevância de posição.",
               "## Referências por estado e limites de uso",
               "A ferramenta foi convertida em contagens e referências empíricas, sem saldos de pontos ou crédito individual. A partida consultada é excluída da referência. Cada contexto mantém vivos, fase, faixa de diferença de equipamento e relógio; exige ao menos 20 rounds e cinco partidas. Falta de suporte permanece indisponível, sem fallback para uma população diferente. Os estados são observados em eventos; não representam todos os instantes possíveis de um round. O relógio pós-plant é tempo decorrido desde o plant. Mapa, equipe e geometria não são controlados por essa referência. Lados não identificados pela inferência baseada em plants ficam sem referência nessa ferramenta. O resultado final é factual e não pontuado. Excluir a partida consultada evita reutilizar seus resultados nessa referência, mas não é uma avaliação temporal: outras partidas podem ser posteriores. Não há teste de calibração ou erro probabilístico fora da amostra, e os valores não constituem probabilidades prospectivas calibradas.",
               "A seleção de torneios, versões e qualidade recalcula as referências analíticas. Este documento é um retrato da amostra padrão descrita acima; não muda quando alguém filtra a interface. Dados ausentes, anomalias, builds misturados, geometria não observada e conversão aproximada de 100 unidades por metro continuam limites declarados. Não foram coletados novos dados para inventar as variáveis ausentes.",
               "Cobertura de lutas no recorte: `" + str(fight_coverage(fights)) + "`."]
    return "\n\n".join(blocks) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report()
    args.output.write_text(report, encoding="utf-8")
    print(f"Conclusões geradas em {args.output}")


if __name__ == "__main__":
    main()
