"""Gera as conclusões a partir dos dados locais, com uma função por assunto.

Execute ``python -m valorant.report --output CONCLUSOES.md`` na raiz do projeto.
Apenas o arquivo de saída é escrito. Os dados brutos são lidos sem alterações.
"""

import argparse
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from valorant.analysis.deaths import build_deaths_table, with_solo_flag
from valorant.analysis.economy import (
    after_previous_round,
    build_rounds_table,
    second_round_cycle,
    versus_full_buy,
    win_rate_by_loadout,
)
from valorant.analysis.fights import (
    build_fights_table,
    fight_class_summary,
    fight_coverage,
    save_effect,
    trade_possibility_summary,
)
from valorant.analysis.first_blood import first_blood_table, summary_by_map, win_rate_by_time
from valorant.analysis.plants import build_plants_table, summary_by_plant_time, summary_by_site
from valorant.analysis.prediction import (
    forecast_accuracy,
    in_match_accuracy,
    load_matches,
    match_pairs,
    team_features,
)
from valorant.analysis.round_style import build_round_styles, collapse_summary, style_summary
from valorant.analysis.setups import build_setups_table, defuse_by, retake_summary
from valorant.data.metadata import load_maps_by_url
from valorant.data.quality import data_signature, dataset_quality, eligible_match_ids
from valorant.paths import PROJECT_ROOT

# Os nomes dos dados ficam estáveis. Só os cabeçalhos apresentados ao leitor mudam.
COLUMN_LABELS = {
    "lado_abriu": "Lado que fez a abertura",
    "faixa": "Tempo da abertura",
    "rounds": "Rounds",
    "abriu_venceu": "Vitória de quem abriu",
    "trocada": "Troca em até 5 s",
    "sem_morte_antes_plant": "Sem morte anterior ao plant",
    "plants": "Plants",
    "vitoria_do_ataque": "Vitória do ataque",
    "isolada": "Sem aliado próximo",
    "mortes": "Mortes",
    "vitoria_da_vitima": "Vitória da equipe da vítima",
    "troca_temporal": "Troca em até 5 s",
    "contexto": "Posição dos aliados",
    "vitoria": "Taxa de vitória",
    "residuo_vivos": "Diferença da referência por vivos",
    "mapa": "Mapa",
    "ataque_abriu": "Abertura pelo ataque",
    "ataque_vence": "Vitória do ataque",
    "impacto_da_abertura": "Diferença de vitória do ataque conforme quem abriu",
    "impacto_ic95_baixo": "Limite inferior de 95%",
    "impacto_ic95_alto": "Limite superior de 95%",
    "metrica": "Medida",
    "partidas": "Partidas",
    "acerto": "Taxa de acerto",
    "ic_baixo": "Limite inferior de 95%",
    "ic_alto": "Limite superior de 95%",
    "abstencoes_ou_sem_referencia": "Jogos sem palpite ou referência",
    "base_mesmos_jogos": "Acerto do histórico nos mesmos jogos",
    "diferenca_pareada": "Diferença de acerto para o histórico",
    "diferenca_ic_baixo": "Limite inferior da diferença",
    "diferenca_ic_alto": "Limite superior da diferença",
    "protocolo": "Dados usados",
    "faixa_diferenca": "Diferença de equipamento entre equipes",
    "faixa_loadout": "Equipamento da equipe",
    "loadout_medio": "Valor médio do equipamento",
    "ganho_por_1k_a_mais": "Diferença de vitória por mil de equipamento",
    "anterior": "Resultado anterior",
    "esperado_pelo_dinheiro": "Referência pelo equipamento",
    "acima_do_esperado": "Diferença da referência",
    "diferenca_media": "Diferença média de equipamento",
    "metade": "Metade",
    "compra": "Faixa de equipamento",
    "ciclos_completos": "Ciclos completos",
    "ciclos_censurados": "Ciclos interrompidos pelo fim da partida",
    "disponiveis_round_3": "Ciclos com terceiro round",
    "disponiveis_round_4": "Ciclos com quarto round",
    "vitoria_round_2": "Vitória no segundo round",
    "vitoria_round_3": "Vitória no terceiro round",
    "vitoria_round_4": "Vitória no quarto round",
    "rounds_ganhos_2_a_4": "Vitórias médias do segundo ao quarto round",
    "faixa_tempo": "Tempo até plantar",
    "defuse": "Taxa de defuse",
    "esperado_pelos_vivos": "Referência por jogadores vivos",
    "segundos_plant": "Tempo mediano até plantar em segundos",
    "defuse_ic95_min": "Limite inferior de 95%",
    "defuse_ic95_max": "Limite superior de 95%",
    "site": "Local de plant",
    "count": "Defuses",
    "mean": "Média em segundos",
    "std": "Desvio padrão em segundos",
    "min": "Menor tempo",
    "25%": "Um quarto dos casos até",
    "50%": "Metade dos casos até",
    "75%": "Três quartos dos casos até",
    "max": "Maior tempo",
    "lado": "Lado",
    "acima_do_time": "Diferença da média da equipe",
    "ic95_baixo": "Limite inferior de 95%",
    "ic95_alto": "Limite superior de 95%",
    "troca_possivel": "Distância e direção do aliado",
    "venceu_round": "Vitória da equipe da vítima",
    "tres_em_10s": "Três mortes em 10 s",
    "tres_com_abate": "Três mortes com abate da própria equipe na janela",
    "colapsos": "Rounds com colapso",
    "venceu_sem_colapso": "Vitória sem colapso",
    "venceu_com_colapso": "Vitória com colapso",
    "inicio_mediano": "Início mediano em segundos",
    "classe_luta": "Adversários que causaram dano",
    "dist_killer": "Distância média até o autor em unidades",
    "sobreviventes": "Sobreviventes",
    "loadout": "Equipamento médio no round",
    "loadout_seguinte": "Equipamento médio no próximo round",
    "venceu_seguinte": "Vitória no próximo round",
    "estilo": "Tempo do plant",
    "venceu": "Taxa de vitória",
    "plant_mediano": "Tempo mediano até plantar em segundos",
    "esperado": "Referência por jogadores vivos",
    "residuo": "Diferença da referência",
    "faixa_defesa": "Distância mediana da defesa até a spike",
    "atacantes_vivos_no_defuse": "Atacantes vivos no defuse",
    "defuses": "Defuses",
    "mais_proximo_mediano": "Distância mediana até o atacante mais próximo em unidades",
    "ninguem_a_15_m": "Defuses sem atacante a até 15 m",
}

VALUE_LABELS = {
    "troca_1a_morte": "troca após a primeira morte",
    "plant_limpo": "plant sem abate adversário anterior",
    "flanco_defesa": "defensor separado do grupo",
    "isolada": "morte sem aliado próximo",
    "histórico (jogos elegíveis; empates abstêm)": "histórico de vitórias com palpite definido",
    "retrospectivo fora da partida": "outras partidas, anteriores ou posteriores",
    "somente anteriores": "somente partidas anteriores",
    "default": "plant após 40 segundos",
    "execução rápida": "plant em até 40 segundos",
}

COVERAGE_LABELS = {
    "mortes_brutas": "Mortes registradas",
    "mortes_diagnostico": "Mortes usadas na análise de combate",
    "mortes_excluidas": "Mortes fora da análise de combate",
    "com_posicao_autor": "Com posição do autor do abate",
    "com_proxy_geometrica": "Com classificação de proximidade calculável",
}


def format_count(value):
    return str(value)


def format_percent(value):
    return f"{value:.1%}".replace(".", ",")


@lru_cache(maxsize=1)
def map_display_names():
    return {
        url.rsplit("/", 1)[-1]: metadata["displayName"]
        for url, metadata in load_maps_by_url().items()
    }


def markdown_table(table, limit=None):
    """Escreve uma tabela com rótulos de leitura, sem depender de tabulate."""
    if table.empty:
        return "Sem dados suficientes para esta comparação."
    frame = (
        table.reset_index()
        if table.index.name or isinstance(table.index, pd.MultiIndex)
        else table.copy()
    )
    if limit:
        frame = frame.head(limit)
    if "mapa" in frame:
        frame["mapa"] = frame["mapa"].map(lambda name: map_display_names().get(name, name))

    def cell(value):
        if pd.isna(value):
            return "Sem dado"
        if isinstance(value, bool):
            return "Sim" if value else "Não"
        if isinstance(value, float):
            return f"{value:.3f}".replace(".", ",")
        text = VALUE_LABELS.get(str(value), str(value))
        return text.replace("|", "/").replace("\n", " ")

    headers = [COLUMN_LABELS.get(str(name), str(name).replace("_", " ")) for name in frame.columns]
    rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    rows += [
        "| " + " | ".join(cell(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join(rows)


@dataclass
class ReportData:
    """Tabelas compartilhadas pelas seções, calculadas uma vez por relatório."""

    quality: dict
    selected_quality: dict
    deaths: pd.DataFrame
    rounds: pd.DataFrame
    fights: pd.DataFrame
    openings: pd.DataFrame
    plants: pd.DataFrame
    setups: pd.DataFrame
    matches: pd.DataFrame
    styles: pd.DataFrame
    team_features: pd.DataFrame
    match_pairs: pd.DataFrame


def load_report_data():
    match_ids = eligible_match_ids()
    deaths = build_deaths_table(match_ids=match_ids)
    rounds = build_rounds_table(match_ids=match_ids)
    matches = load_matches(match_ids=match_ids)
    features = team_features(deaths, matches)
    return ReportData(
        quality=dataset_quality(),
        selected_quality=dataset_quality(match_ids=match_ids),
        deaths=deaths,
        rounds=rounds,
        fights=build_fights_table(deaths, match_ids=match_ids),
        openings=first_blood_table(deaths),
        plants=build_plants_table(match_ids=match_ids),
        setups=build_setups_table(match_ids=match_ids),
        matches=matches,
        styles=build_round_styles(deaths, rounds, matches, match_ids=match_ids),
        team_features=features,
        match_pairs=match_pairs(matches, features),
    )


def report_introduction(data):
    total, selected = data.quality["totals"], data.selected_quality["totals"]
    tactical_count = int(data.fights["diagnostico_tatico"].sum())
    generated_on = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y")
    return [
        "# O que os dados mostram",
        f"Relatório gerado em {generated_on} com `python -m valorant.report --output CONCLUSOES.md`.",
        f"A base local tem **{format_count(total['matches'])} partidas, {format_count(total['rounds'])} rounds, "
        f"{format_count(total['deaths'])} mortes e {format_count(total['participants'])} participantes**. "
        f"Há também {total['observers']} observadores que não jogaram. A análise usa por padrão "
        f"**{format_count(selected['matches'])} partidas e {format_count(selected['rounds'])} rounds**.",
        "Uma partida fica fora da análise padrão porque seus primeiros 24 rounds terminam por tempo, "
        "sem combate ou plant. O motivo desse registro é desconhecido. Os arquivos originais foram preservados.",
        f"Na seleção padrão, há {format_count(len(data.deaths))} mortes registradas, "
        f"{format_count(tactical_count)} mortes usadas na análise de combate, "
        f"{format_count(len(data.openings))} rounds com equipe de abertura definida e "
        f"{format_count(len(data.plants))} plants válidos. O arquivo `data-manifest.json` e a página "
        "Qualidade dos dados detalham as exclusões.",
        "As taxas nas tabelas vão de zero a um. Por exemplo, 0,700 corresponde a 70%. Uma diferença de "
        "0,050 corresponde a cinco pontos percentuais. As tabelas descrevem as partidas registradas e "
        "não mostram, por si só, o que causou uma vitória.",
        "Cada morte conta como uma observação nas tabelas por morte. Assim, um round com mais mortes "
        "pesa mais nessas tabelas. Os rounds da mesma partida também compartilham condições e não são "
        "observações independentes. As comparações servem para levantar perguntas. Não houve ajuste "
        "estatístico para o grande número de comparações feitas.",
        f"A assinatura dos dados e metadados é `{data_signature()}`.",
    ]


def opening_section(data):
    first_death_time = data.deaths.groupby(["match_id", "round"])["segundos"].min().to_dict()
    plants = data.plants.copy()
    plants["sem_morte_antes_plant"] = [
        first_death_time.get((match_id, round_number), math.inf) >= plant_seconds
        for match_id, round_number, plant_seconds in zip(
            plants["match_id"], plants["round"], plants["segundos_plant"]
        )
    ]
    return [
        "## 1. Abertura e troca de abates",
        "Abertura é o primeiro abate de um adversário antes do encerramento observável do round. "
        "Se as duas equipes abatem no mesmo instante, a abertura fica indefinida. Se só uma equipe "
        "faz abates simultâneos, sabemos quem abriu, mas não escolhemos uma vítima ou posição individual.",
        f"A equipe que faz a abertura vence {format_percent(data.openings['abriu_venceu'].mean())} dos rounds "
        f"com abertura definida. Ficaram fora dessa comparação "
        f"{data.openings.attrs.get('rounds_abertura_ambigua', 0)} rounds com abertura simultânea entre equipes.",
        "Troca em até cinco segundos ocorre quando a equipe da vítima abate o autor da morte nessa "
        "janela. Ela inclui abates simultâneos e, por isso, não comprova uma reação ao primeiro abate. "
        "Mortes por ambiente, fogo amigo ou após o encerramento observável ficam fora.",
        markdown_table(win_rate_by_time(data.openings)),
        "A tabela seguinte separa os plants válidos sem nenhuma morte anterior ao plant. A comparação "
        "não exige que o ataque consiga um abate depois do plant.",
        markdown_table(
            plants.groupby("sem_morte_antes_plant").agg(
                plants=("round", "size"), vitoria_do_ataque=("ataque_venceu", "mean")
            )
        ),
    ]


def isolation_section(data):
    deaths = with_solo_flag(data.deaths, 1000)
    first_victims = (
        deaths[deaths["primeira_vitima_unica"]]
        if "primeira_vitima_unica" in deaths
        else deaths.iloc[:0]
    )
    return [
        "## 2. Distância dos aliados",
        "Uma morte fica no grupo sem aliado próximo quando o aliado vivo mais próximo está a mais "
        "de 1000 unidades do jogo. A conversão aproximada é de dez metros, mas essa escala não foi "
        "validada nestes arquivos. Se não há aliado vivo, a distância fica sem valor. A tabela usa "
        "somente a primeira vítima identificada de cada round.",
        markdown_table(
            first_victims.groupby("isolada").agg(
                mortes=("vitima", "size"),
                vitoria_da_vitima=("venceu_round", "mean"),
                troca_temporal=("trocada", "mean"),
            )
        ),
        "O controle de distância na interface recalcula os grupos. Taxas de vitória próximas não "
        "provam que a posição seja irrelevante. A base registra as mortes e não todas as situações "
        "em que um jogador ficou exposto e sobreviveu.",
    ]


def allied_position_section(data):
    deaths = with_solo_flag(data.deaths, 1000)
    before_plant = deaths[(deaths["lado"] == "defesa") & (deaths["fase"] == "pré-plant")].copy()
    before_plant["contexto"] = before_plant["contexto"].replace({"flanco": "separado do grupo"})
    before_plant["residuo_vivos"] = before_plant["venceu_round"].astype(
        float
    ) - before_plant.groupby(["aliados_vivos", "inimigos_vivos"])["venceu_round"].transform("mean")
    return [
        "## 3. Posição dos aliados e regiões do mapa",
        "Em grupo significa que há um aliado dentro do limite de distância. Isolado significa que "
        "não há aliado próximo. O nome separado do grupo é usado quando, além dessa distância, "
        "pelo menos dois aliados estão na mesma grande região do mapa. Estar na mesma região não "
        "garante que esses aliados estejam próximos entre si. Essa classificação não identifica um flanco.",
        "A referência por vivos é a taxa de vitória nas mortes da defesa antes do plant com a mesma "
        "quantidade de aliados e adversários vivos. A diferença da referência subtrai essa taxa do "
        "resultado observado e depois calcula a média do grupo. Ela não compara situações iguais "
        "em todos os outros aspectos.",
        markdown_table(
            before_plant.groupby("contexto").agg(
                mortes=("vitima", "size"),
                vitoria=("venceu_round", "mean"),
                residuo_vivos=("residuo_vivos", "mean"),
            )
        ),
        "A ocupação das regiões usa as posições no primeiro abate válido ocorrido em até 20 segundos, "
        "incluindo a vítima. É um registro por round com esse evento, e não a posição inicial de "
        "todos os rounds. A região ocupada não diz se o jogador segurava uma posição ou avançava.",
    ]


def maps_section(data):
    summary = summary_by_map(data.openings)[
        [
            "rounds",
            "ataque_abriu",
            "ataque_vence",
            "impacto_da_abertura",
            "impacto_ic95_baixo",
            "impacto_ic95_alto",
        ]
    ].reset_index()
    return [
        "## 4. Diferenças entre mapas",
        "A diferença de abertura subtrai a taxa de vitória do ataque quando a defesa abre da taxa "
        "de vitória do ataque quando ele próprio abre. Os limites de 95% mostram a incerteza estimada por uma aproximação "
        "normal. Essa conta trata os rounds como independentes, embora rounds de uma partida "
        "compartilhem equipes e condições.",
        markdown_table(summary),
        "Os mapas têm quantidades diferentes de partidas, jogadores e versões do jogo. Por isso, "
        "a comparação exige cuidado, sobretudo nos mapas com menos rounds. Intervalos sobrepostos "
        "não provam que dois resultados sejam iguais. As regiões usam o nome do ponto conhecido "
        "mais próximo no mapa em duas dimensões, sem verificar paredes ou caminhos.",
    ]


def after_plant_section(data):
    return [
        "## 5. Combate depois do plant",
        "Pós-plant é o período entre plantar a spike e encerrar o round. Nas mortes desse período, "
        "a troca em até cinco segundos aparece junto de taxas de vitória diferentes em várias "
        "situações de jogadores vivos. Os gráficos estão na página Trocas e isolamento e indicam "
        "quando faltam dados para comparar.",
        "Separar os casos pela quantidade de vivos não revela por que a troca e a vitória aparecem "
        "juntas. A própria troca acontece depois da morte e muda o número de vivos. Portanto, essa "
        "comparação não mede quanto a proximidade ajudou por permitir a troca.",
    ]


def prediction_section(data):
    return [
        "## 6. Resultado observado e previsão de outras partidas",
        "A primeira tabela usa medidas da própria partida já encerrada. A taxa de acerto informa "
        "quantas vezes a equipe favorecida pela medida foi a vencedora. Ela descreve o jogo conhecido "
        "e não simula um palpite feito antes dele.",
        markdown_table(in_match_accuracy(data.match_pairs)),
        "A medida de plant sem abate adversário anterior conta plants válidos antes de qualquer "
        "abate entre adversários no round. Mortes por ambiente ou fogo amigo não impedem essa condição. "
        "Ela é diferente do grupo sem nenhuma morte anterior da seção de abertura.",
        "A segunda tabela usa outras partidas para formar o perfil de cada equipe. Elas podem ter "
        "ocorrido antes ou depois do jogo avaliado, então essa avaliação serve como comparação retrospectiva.",
        markdown_table(forecast_accuracy(data.matches, data.team_features, only_previous=False)),
        "A terceira tabela usa apenas jogos anteriores. A escala que combina as medidas também é "
        "calculada com dados do passado. Essa é a avaliação que respeita a ordem das partidas.",
        markdown_table(forecast_accuracy(data.matches, data.team_features, only_previous=True)),
        "O histórico escolhe a equipe com maior taxa de vitória nos jogos de referência. Cada medida "
        "é comparada com esse histórico nos mesmos jogos. Se há empate ou faltam dados, não há palpite. "
        "A coluna de jogos sem palpite ou referência mostra essas exclusões. O erro entre os palpites "
        "feitos é um menos a taxa de acerto. Esse erro não inclui os jogos sem palpite.",
        "A diferença de acerto é a média das diferenças entre os dois palpites em cada jogo avaliado. "
        "Os limites estimados ajudam a ver a incerteza, mas equipes se repetem entre partidas. "
        "Os intervalos das taxas usam Wilson, um cálculo para proporções que supõe observações "
        "independentes. Nenhuma dessas medidas demonstra contribuição causal de um jogador. "
        "As posições por correlação de Spearman descrevem a ordem das equipes no mesmo campeonato observado.",
        "CEUB Octopus e CEUB Octopus Vulgaris permanecem separados porque não compartilham jogadores "
        "nesta base. A semelhança dos nomes não basta para juntar os elencos.",
    ]


def economy_section(data):
    _, differences = win_rate_by_loadout(data.rounds)
    cycle, _ = second_round_cycle(data.rounds)
    return [
        "## 7. Equipamento e rounds após o pistol",
        "Valor do equipamento é a soma do equipamento registrado para a equipe no começo do round, "
        "também chamada de loadout nos dados. Esse valor não informa o gasto naquele round nem o "
        "dinheiro disponível. A primeira tabela compara a diferença de equipamento entre as equipes.",
        markdown_table(differences),
        "A tabela seguinte usa somente rounds normais contra adversários com mais de 20 mil de "
        "equipamento. A diferença por mil resume a mudança entre faixas vizinhas e não mede o efeito de comprar mais.",
        markdown_table(versus_full_buy(data.rounds)),
        "A referência pelo equipamento vem de uma curva calculada apenas com os rounds normais "
        "da seleção. A diferença da referência mostra quanto a taxa observada fica acima ou abaixo "
        "dessa curva depois de cada resultado anterior.",
        markdown_table(after_previous_round(data.rounds)),
        "Diferenças pequenas não provam que perder um round não abale a equipe ou que o dinheiro "
        "explique toda sequência de resultados. Separar partidas pelo placar final também usa "
        "informação que depende dos resultados.",
        "Pistol é o primeiro round de cada metade. Após perder o pistol, os ciclos acompanham o "
        "segundo, o terceiro e o quarto round da mesma metade. Eco, compra leve e force são faixas "
        "de equipamento registrado, e não decisões de compra confirmadas. As taxas e a soma de "
        "vitórias usam os mesmos ciclos completos. Os ciclos interrompidos pelo fim da partida "
        "aparecem em uma coluna separada.",
        markdown_table(
            cycle[
                [
                    "rounds",
                    "ciclos_completos",
                    "ciclos_censurados",
                    "disponiveis_round_3",
                    "disponiveis_round_4",
                    "vitoria_round_2",
                    "vitoria_round_3",
                    "vitoria_round_4",
                    "rounds_ganhos_2_a_4",
                ]
            ]
        ),
        "Os ciclos completos dependem de a partida ter durado até o quarto round da metade. "
        "Por isso, as médias não mostram o retorno de escolher force ou eco. Quando há taxa "
        "anterior ao pistol, ela usa somente rounds anteriores a ele.",
    ]


def plants_section(data):
    plants = data.plants
    defuse_times = plants.loc[plants["defusada"], ["segundos_ate_defuse"]].describe().T
    return [
        "## 8. Plant e defuse",
        "Plant é a colocação da spike e defuse é o seu desarme. Um plant é válido nesta análise "
        "quando ocorre antes do encerramento observável e ainda há defensores vivos. Registros "
        "de plant após eliminação ou em rounds encerrados pelo tempo ficam fora das taxas de combate. "
        "Os motivos de exclusão continuam na página de qualidade.",
        f"Há {format_count(len(plants))} plants válidos e {format_count(int(plants['defusada'].sum()))} "
        f"defuses. A taxa de defuse é {format_percent(plants['defusada'].mean())}.",
        "A referência por jogadores vivos é a taxa de defuse entre os plants com a mesma quantidade "
        "de atacantes e defensores vivos. Por exemplo, um plant com três atacantes e dois defensores "
        "é comparado com outros plants em 3 contra 2. A referência de uma linha é a média dessas "
        "taxas para os plants daquela linha. A diferença da referência subtrai esse valor da taxa observada.",
        "Os limites de 95% usam Wilson, um cálculo de incerteza para proporções. Ele trata os plants "
        "como independentes, embora vários venham da mesma partida. Aqui, os intervalos servem como descrição.",
        markdown_table(summary_by_plant_time(plants)),
        markdown_table(
            summary_by_site(plants)[
                ["plants", "defuse", "esperado_pelos_vivos", "acima_do_esperado"]
            ]
        ),
        "Essa referência considera os vivos, mas não toda a situação do round. Uma diferença entre "
        "locais não mede o efeito de escolher onde plantar. A tabela seguinte mostra o tempo entre "
        "plant e defuse apenas nos casos em que houve desarme.",
        markdown_table(defuse_times),
        "Os tempos observados não sustentam a afirmação de que quase todos os defuses acontecem "
        "perto do limite de 45 segundos.",
    ]


def geometry_section(data):
    return [
        "## 9. Distância e direção dos aliados nas trocas",
        "O teste procura um aliado a até 2000 unidades do jogo e verifica se sua direção está a "
        "até 45 graus da direção do autor do abate. Proximidade e direção compatíveis significam "
        "apenas que essas duas condições foram atendidas.",
        markdown_table(trade_possibility_summary(data.fights, ["lado"])),
        "A conta usa duas dimensões e não verifica linha de tiro, paredes, fumaça, altura, cegueira, "
        "munição ou recarga. Quando falta a direção, ela permanece desconhecida. A ausência de troca "
        "não demonstra erro de um jogador.",
    ]


def collapse_section(data):
    return [
        "## 10. Mortes em sequência",
        "Colapso é uma janela de até dez segundos com pelo menos três vítimas distintas da mesma "
        "equipe, mortas por adversários válidos, sem abate da própria equipe no intervalo. A tabela "
        "também mostra janelas com três mortes e algum abate da própria equipe. Mortes por spike "
        "ou ambiente e eventos após o encerramento observável ficam fora.",
        markdown_table(collapse_summary(data.styles, ["lado"])),
        "Se as mortes ocorrem em regiões diferentes, o registro indica múltiplas regiões. A "
        "sequência de mortes descreve o que aconteceu, mas não identifica se mira ou posição causou o colapso.",
    ]


def damage_section(data):
    return [
        "## 11. Dano registrado",
        "As categorias contam quantos adversários causaram dano à vítima durante o round inteiro. "
        "Dano de vários adversários não significa fogo simultâneo. O dano recebido pelo autor do "
        "abate também é somado no round e não identifica uma reação naquela vida.",
        markdown_table(fight_class_summary(data.fights, ["lado"])),
        "Assistência não conta como prova de dano, e registros repetidos de dano são somados. "
        "As distâncias nas mortes, sozinhas, não demonstram bom uso de alcance nem erro.",
    ]


def survival_section(data):
    return [
        "## 12. Sobrevivência e equipamento no round seguinte",
        "A tabela usa equipes que perderam o round. Sobrevivente é quem está vivo no último registro de posições disponível, incluindo quem "
        "voltou à vida. A comparação com o próximo round exclui transições no fim de uma metade "
        "e na prorrogação. Os valores de equipamento são os registrados no começo de cada round.",
        markdown_table(save_effect(data.rounds, data.fights)),
        "As médias não medem o valor de salvar um jogador. As equipes também diferem em equipamento "
        "inicial, bônus e força. Os dados não identificam a intenção de caçar adversários. Recortar "
        "apenas vitórias do ataque não mostra se essa escolha compensa nem qual troca de abates seria aceitável.",
    ]


def plant_timing_section(data):
    attack_style, _ = style_summary(data.styles)
    comparison = data.plants.copy()
    comparison["estilo"] = comparison["segundos_plant"].map(
        lambda seconds: "execução rápida" if seconds <= 40 else "default"
    )
    comparison["esperado_ataque"] = comparison["esperado_vitoria_vivos"]
    comparison["residuo"] = (
        comparison["ataque_venceu"].astype(float) - comparison["esperado_ataque"]
    )
    return [
        "## 13. Tempo do plant e resultado",
        "Os grupos usam o momento em que a spike foi plantada. Plant em até 40 segundos corresponde "
        "ao antigo nome execução rápida, e plant depois de 40 segundos corresponde ao antigo nome "
        "default. O relógio não revela a intenção da equipe. Sem plant e plant excluído têm grupos próprios.",
        markdown_table(attack_style),
        "A próxima tabela usa apenas plants válidos. A referência é a taxa de vitória do ataque "
        "nos plants com a mesma quantidade de atacantes e defensores vivos, calculada como na "
        "seção de defuse. A diferença subtrai essa referência do resultado observado.",
        markdown_table(
            comparison.groupby("estilo").agg(
                plants=("round", "size"),
                vitoria=("ataque_venceu", "mean"),
                esperado=("esperado_ataque", "mean"),
                residuo=("residuo", "mean"),
            )
        ),
        "Plantar cedo e vencer podem ocorrer juntos sem que um cause o outro. A tabela não registra "
        "tentativas que falharam antes do plant. Comparar médias com a equipe atrás ou à frente "
        "no placar também não demonstra como cada equipe adapta seu jogo. Um round sem plant "
        "pode terminar em vitória ou derrota do ataque.",
    ]


def setup_section(data):
    return [
        "## 14. Posições no plant e no defuse",
        "A distância mediana da defesa é o valor central das distâncias dos defensores até a spike "
        "no plant. Com quantidade par de defensores, usa-se a média dos dois valores centrais. "
        "A referência por vivos e seus limites de Wilson seguem a definição da seção de defuse.",
        markdown_table(defuse_by(data.setups, "faixa_defesa")),
        "Nos rounds com defuse, a tabela seguinte conta os atacantes ainda vivos no desarme e a "
        "distância do mais próximo. Distâncias são unidades do jogo, com conversão aproximada de "
        "100 unidades por metro. Sem atacante vivo, a distância fica sem dado e o caso entra "
        "no grupo sem atacante a até 15 metros.",
        markdown_table(retake_summary(data.setups)),
        "Olhar para longe da spike não comprova vigiar uma entrada. A distância média até a spike "
        "também não mede a distância entre os aliados. Encontrar zero atacantes no defuse descreve "
        "o fim das lutas, mas não descarta a influência das posições anteriores. Diferenças pequenas "
        "nessas medidas não provam que o posicionamento seja irrelevante.",
    ]


def reference_and_limits(data):
    coverage = pd.DataFrame(
        [
            {"Cobertura das mortes": COVERAGE_LABELS.get(key, key), "Quantidade": value}
            for key, value in fight_coverage(data.fights).items()
        ]
    )
    return [
        "## Referências de situações parecidas",
        "Na página da rodada, a referência mostra a taxa de vitória em situações observadas em "
        "outras partidas. Ela reúne casos com a mesma quantidade de vivos, fase do round, faixa "
        "de diferença de equipamento e faixa de tempo. Exige pelo menos 20 rounds de cinco "
        "partidas. Quando faltam casos, o valor fica indisponível. A ferramenta não atribui pontos "
        "nem crédito individual por mudanças nessa taxa.",
        "A partida aberta na interface fica fora da referência. As outras partidas podem ser "
        "posteriores, portanto essa taxa é uma descrição retrospectiva. Ela não foi avaliada "
        "como probabilidade de vitória para jogos futuros. As faixas de incerteza usam reamostragem "
        "de partidas, ou seja, recalculam a taxa a partir de diferentes seleções das partidas disponíveis.",
        "Os registros de posição existem em eventos e não cobrem todos os instantes do round. "
        "Depois do plant, o relógio conta o tempo desde a colocação da spike. A referência não "
        "iguala mapa, equipe ou geometria. Se os plants não permitem identificar os lados, a "
        "referência fica indisponível. O resultado final apenas informa quem venceu.",
        "## Dados e alcance das conclusões",
        "Os filtros de torneios, versões e qualidade recalculam as referências na interface. Este "
        "relatório usa a seleção padrão descrita no início e não muda com esses filtros. Dados "
        "ausentes, registros incomuns, versões misturadas e geometria não observada limitam as "
        "comparações. A conversão de unidades para metros é aproximada. Nenhum dado ausente foi inventado.",
        markdown_table(coverage),
    ]


REPORT_SECTIONS = (
    opening_section,
    isolation_section,
    allied_position_section,
    maps_section,
    after_plant_section,
    prediction_section,
    economy_section,
    plants_section,
    geometry_section,
    collapse_section,
    damage_section,
    survival_section,
    plant_timing_section,
    setup_section,
)


def build_report():
    data = load_report_data()
    blocks = report_introduction(data)
    for section in REPORT_SECTIONS:
        blocks.extend(section(data))
    blocks.extend(reference_and_limits(data))
    return "\n\n".join(blocks) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Arquivo Markdown de saída")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    output.write_text(build_report(), encoding="utf-8")
    print(f"Conclusões geradas em {output}")


if __name__ == "__main__":
    main()
