"""Nomes de exibição comuns a tabelas e gráficos.

As análises mantêm suas colunas de trabalho. A interface aplica nomes e formatos
apenas na cópia apresentada, para não alterar agrupamentos ou cálculos.
"""

import numpy as np
import pandas as pd
import streamlit as st

FIELD_LABELS = {
    "match_id": "Identificador da partida",
    "puuid": "Identificador do jogador",
    "round": "Round",
    "rounds": "Rounds",
    "partidas": "Partidas",
    "jogador": "Jogador",
    "time": "Equipe",
    "nome_time": "Equipe",
    "time_vitima": "Equipe da vítima",
    "nome_killer": "Equipe de quem fez o abate",
    "mapa": "Mapa",
    "site": "Site",
    "mapa_site": "Mapa e site",
    "torneio": "Torneio",
    "arquivo": "Arquivo",
    "inicio": "Início em São Paulo",
    "duracao_min": "Duração em minutos",
    "versao": "Versão do jogo",
    "rounds_blue": "Rounds da Blue",
    "rounds_red": "Rounds da Red",
    "kills": "Abates",
    "deaths": "Mortes",
    "assists": "Assistências",
    "score": "Pontuação do jogo",
    "kd": "Abates por morte",
    "agente": "Agente",
    "score_por_round": "Pontuação média por round",
    "funcao": "Função do agente",
    "lado": "Lado",
    "contexto": "Posição em relação aos aliados",
    "territorio": "Ocupação da região nos primeiros confrontos",
    "fase": "Momento do round",
    "trocada": "Morte trocada em até 5 s",
    "isolada": "Morte longe dos aliados",
    "mortes": "Mortes",
    "venceu_round": "Vitórias da equipe da vítima",
    "vitoria_da_vitima": "Vitórias da equipe da vítima",
    "fracao_trocadas": "Mortes trocadas em até 5 s",
    "fracao_isoladas": "Mortes longe dos aliados",
    "segundos": "Segundos desde o início do round",
    "faixa": "Faixa de tempo",
    "faixa_tempo": "Faixa de tempo",
    "situacao": "Aliados e adversários vivos",
    "esperado_pelos_vivos": "Comparação por jogadores vivos",
    "esperado_por_vivos": "Comparação por jogadores vivos",
    "esperado_pelo_dinheiro": "Comparação por equipamento inicial",
    "acima_do_esperado": "Diferença para a comparação",
    "custo_isolamento": "Diferença entre isoladas e acompanhadas",
    "esperado_pela_equipe": "Vitórias da equipe nesta partida",
    "acima_da_equipe": "Diferença para as vitórias da equipe",
    "acima_dos_vivos": "Diferença para a comparação",
    "defuse": "Plants desarmados",
    "defusada": "Spike desarmada",
    "plants": "Plants",
    "segundos_plant": "Segundos até o plant",
    "atacantes_vivos": "Atacantes vivos",
    "defensores_vivos": "Defensores vivos",
    "atacantes_no_site": "Atacantes perto da spike",
    "fracao_olhar_oposto_spike": "Atacantes olhando para longe da spike",
    "faixa_defesa": "Distância da defesa até a spike",
    "faixa_loadout": "Valor do equipamento inicial",
    "faixa_diferenca": "Diferença de equipamento inicial",
    "loadout": "Valor do equipamento inicial",
    "loadout_time": "Equipamento inicial da equipe",
    "loadout_adversario": "Equipamento inicial do adversário",
    "vitoria": "Rounds vencidos",
    "venceu": "Rounds vencidos",
    "anterior": "Resultado do round anterior",
    "derrotas": "Derrotas seguidas antes do round",
    "estilo": "Tempo do plant",
    "colapsos": "Rounds com três perdas em até 10 s",
    "venceu_com_colapso": "Vitórias com três perdas em até 10 s",
    "venceu_sem_colapso": "Vitórias sem três perdas em até 10 s",
    "regiao_colapso": "Região das perdas",
    "pre_plant": "Perdas antes do plant",
    "contato": "Tempo do primeiro abate",
    "vitoria_ataque": "Rounds vencidos no ataque",
    "rounds_ataque": "Rounds de ataque",
    "execução rápida": "Plant até 40 s",
    "default": "Plant depois de 40 s",
    "plant excluído": "Plant fora da análise",
    "aberturas": "Primeiros abates",
    "ataque_venceu": "Vitórias do ataque",
    "abriu_venceu": "Vitórias de quem fez o primeiro abate",
    "lado_abriu": "Lado que fez o primeiro abate",
    "time_abriu": "Equipe que fez o primeiro abate",
    "ataque_abriu": "Primeiros abates do ataque",
    "ataque_vence": "Vitórias do ataque",
    "ataque_vence_se_abre": "Vitórias do ataque quando faz o primeiro abate",
    "ataque_vence_se_defesa_abre": "Vitórias do ataque quando a defesa faz o primeiro abate",
    "impacto_da_abertura": "Diferença de vitórias conforme o primeiro abate",
    "ic95": "Intervalo de 95%",
    "ic95_baixo": "Limite inferior do intervalo de 95%",
    "ic95_alto": "Limite superior do intervalo de 95%",
    "impacto_ic95_baixo": "Limite inferior da diferença",
    "impacto_ic95_alto": "Limite superior da diferença",
    "mediana": "Tempo mediano",
    "media": "Tempo médio",
    "desvio_padrao": "Variação em torno da média",
    "p10": "Tempo com 10% dos casos abaixo",
    "p25": "Tempo com 25% dos casos abaixo",
    "p75": "Tempo com 75% dos casos abaixo",
    "p90": "Tempo com 90% dos casos abaixo",
    "fator": "Ocorrência",
    "descricao": "O que aconteceu",
    "unidade": "Unidade contada",
    "diferenca": "Diferença observada",
    "n_com": "Casos com a ocorrência",
    "n_sem": "Casos sem a ocorrência",
    "com": "Vitórias com a condição",
    "sem": "Vitórias sem a condição",
    "vitoria_com": "Vitórias com a ocorrência",
    "vitoria_sem": "Vitórias sem a ocorrência",
    "taxa_com": "Vitórias com a ocorrência",
    "taxa_sem": "Vitórias sem a ocorrência",
    "ic_baixo": "Limite inferior do intervalo de 95%",
    "ic_alto": "Limite superior do intervalo de 95%",
    "evento": "Evento",
    "tipo": "Tipo de evento",
    "estado": "Situação",
    "observacao": "Observação",
    "antes_ataque": "Vitórias em situações como antes do evento",
    "depois_ataque": "Vitórias em situações como depois do evento",
    "n_antes": "Rounds usados antes do evento",
    "n_depois": "Rounds usados depois do evento",
    "partidas_antes": "Partidas usadas antes do evento",
    "partidas_depois": "Partidas usadas depois do evento",
    "campo": "Campo no arquivo",
    "tipos": "Tipos de dado",
    "ocorrencias": "Ocorrências",
    "distintos": "Valores diferentes",
    "mais_frequentes": "Valores mais frequentes",
    "arma_vitima": "Arma inicial da vítima",
    "distancia": "Distância em unidades do jogo",
    "faixa_distancia": "Distância em unidades do jogo",
    "dano_no_killer": "Dano no autor do abate durante o round",
    "classe_luta": "Dano recebido durante o round",
    "troca_possivel": "Proximidade e direção do aliado",
    "acerto": "Acertos",
    "acuracia": "Taxa de acerto",
    "medida": "Medida usada",
    "criterio": "Regra usada",
    "empates": "Empates sem palpite",
    "cobertura": "Jogos com palpite",
    "vitoria_round_2": "Vitórias no round após o pistol",
    "vitoria_round_3": "Vitórias no segundo round do ciclo",
    "vitoria_round_4": "Vitórias no terceiro round do ciclo",
    "soma_vitorias": "Vitórias somadas no ciclo",
    "parte_do_ataque": "Mortes do ataque entre as mortes após o plant",
    "mortes_pos_plant": "Mortes após o plant",
    "equipe": "Equipe",
    "x": "Coordenada X",
    "y": "Coordenada Y",
}

FIELD_LABELS.update(
    {
        "metrica": "Medida usada",
        "base_mesmos_jogos": "Acerto do histórico nos mesmos jogos",
        "diferenca_pareada": "Diferença de acerto no mesmo conjunto de jogos",
        "diferenca_ic_baixo": "Limite inferior da diferença de acerto",
        "diferenca_ic_alto": "Limite superior da diferença de acerto",
        "abstencoes_ou_sem_referencia": "Jogos sem palpite ou sem histórico",
        "taxa_vitoria": "Partidas vencidas",
        "perfil": "Perfil combinado",
        "time_vencedor": "Equipe vencedora",
        "lado_vencedor": "Lado vencedor",
        "resultado": "Fim do round",
        "cerimonia": "Destaque registrado pelo jogo",
        "spike_plantada": "Spike plantada",
        "callout": "Região do mapa",
        "mediana_segundos": "Tempo mediano em segundos",
    }
)

VALUE_LABELS = {
    "?": "sem informação",
    "default": "plant depois de 40 s",
    "execução rápida": "plant até 40 s",
    "plant excluído": "plant fora da análise",
    "flanco": "separado do grupo",
    "Eliminated": "equipe eliminada",
    "Bomb defused": "spike desarmada",
    "Bomb detonated": "spike explodiu",
    "Round timer expired": "tempo esgotado",
    "kill": "abate",
    "defuse": "desarme",
    "trade": "troca em até 5 s",
    "troca_1a_morte": "trocas após a primeira morte",
    "plant_limpo": "plant sem abate entre adversários antes",
    "flanco_defesa": "morte da defesa separada do grupo",
    "isolada": "morte sem aliado próximo",
    "histórico (jogos elegíveis; empates abstêm)": "histórico de vitórias com palpite definido",
    "retrospectivo fora da partida": "outras partidas, anteriores ou posteriores",
    "somente anteriores": "somente partidas anteriores",
    "Attacker": "ataque",
    "Defender": "defesa",
}

RATE_COLUMNS = {
    "base_mesmos_jogos",
    "diferenca_pareada",
    "diferenca_ic_baixo",
    "diferenca_ic_alto",
    "taxa_vitoria",
    "vitoria",
    "venceu",
    "venceu_round",
    "vitoria_da_vitima",
    "fracao_trocadas",
    "fracao_isoladas",
    "esperado_pelos_vivos",
    "esperado_por_vivos",
    "esperado_pelo_dinheiro",
    "acima_do_esperado",
    "esperado_pela_equipe",
    "acima_da_equipe",
    "acima_dos_vivos",
    "custo_isolamento",
    "defuse",
    "colapsos",
    "venceu_com_colapso",
    "venceu_sem_colapso",
    "pre_plant",
    "vitoria_ataque",
    "execução rápida",
    "default",
    "abriu_venceu",
    "ataque_venceu",
    "ataque_abriu",
    "ataque_vence",
    "ataque_vence_se_abre",
    "ataque_vence_se_defesa_abre",
    "impacto_da_abertura",
    "ic95_baixo",
    "ic95_alto",
    "impacto_ic95_baixo",
    "impacto_ic95_alto",
    "vitoria_com",
    "vitoria_sem",
    "taxa_com",
    "taxa_sem",
    "com",
    "sem",
    "ic_baixo",
    "ic_alto",
    "antes_ataque",
    "depois_ataque",
    "acerto",
    "acuracia",
    "cobertura",
    "parte_do_ataque",
    "vitoria_round_2",
    "vitoria_round_3",
    "vitoria_round_4",
}

FIELD_LABELS.update(
    {
        "residuo_vivos": "Diferença para a comparação por vivos",
        "acima_do_time": "Diferença para os outros rounds da equipe",
        "acima_dos_vivos": "Diferença para a comparação por vivos",
        "custo_solo": "Diferença entre mortes isoladas e acompanhadas",
        "categoria_vitima": "Tipo da arma inicial da vítima",
        "dist_mediana": "Distância mediana do autor do abate em unidades",
        "dist_killer": "Distância mediana do autor do abate em unidades",
        "duelo_longo": "Mortes a partir de 2500 unidades",
        "mortes_arma_curta": "Mortes com submetralhadora ou escopeta inicial",
        "em_duelo_longo": "Mortes a partir de 2500 unidades",
        "mortes_sniper": "Mortes com fuzil de precisão inicial",
        "em_duelo_curto": "Mortes até 1000 unidades",
        "sem_dano_no_autor": "Mortes sem dano no autor durante o round",
        "multiplas_fontes_dano_round": "Casos com dano de mais de um adversário no round",
        "loadout_vitima": "Valor do equipamento inicial da vítima",
        "mais_caro_do_time": "Maior valor de equipamento da equipe",
        "loadout_seguinte": "Valor médio do equipamento no próximo round",
        "venceu_seguinte": "Vitórias no próximo round",
        "sobreviventes": "Jogadores vivos ao fim do round",
        "rounds_ganhos_2_a_4": "Vitórias médias nos três rounds do ciclo",
        "ciclos_censurados": "Ciclos interrompidos pelo fim da partida",
        "ciclos_completos": "Ciclos com os três rounds observados",
        "disponiveis_round_3": "Ciclos com segundo round observado",
        "disponiveis_round_4": "Ciclos com terceiro round observado",
        "ganho_por_1k_a_mais": "Diferença de vitórias por mil créditos a mais",
        "loadout_medio": "Valor médio do equipamento inicial",
        "diferenca_media": "Diferença média de equipamento inicial",
        "atacantes_vivos_no_defuse": "Atacantes vivos no desarme",
        "defuses": "Desarmes",
        "mais_proximo_mediano": "Distância mediana do atacante mais próximo em unidades",
        "ninguem_a_15_m": "Desarmes sem atacante em até 1500 unidades",
        "count": "Registros",
        "mean": "Média",
        "std": "Desvio padrão",
        "min": "Menor valor",
        "max": "Maior valor",
    }
)
RATE_COLUMNS.update(
    {
        "trocada",
        "isolada",
        "residuo_vivos",
        "acima_do_time",
        "custo_solo",
        "duelo_longo",
        "em_duelo_longo",
        "em_duelo_curto",
        "sem_dano_no_autor",
        "multiplas_fontes_dano_round",
        "troca_possivel",
        "venceu_seguinte",
        "ganho_por_1k_a_mais",
        "ninguem_a_15_m",
    }
)

FIELD_HELP = {
    "esperado_pelos_vivos": "Média das taxas de desarme para a quantidade de atacantes e defensores vivos em cada plant deste grupo.",
    "esperado_por_vivos": "Taxa de vitória observada com a mesma quantidade de aliados e adversários vivos.",
    "esperado_pelo_dinheiro": "Taxa de vitória de rounds normais com diferença parecida no valor do equipamento inicial.",
    "ic_baixo": "Início da faixa de incerteza. O método é explicado junto da análise.",
    "ic_alto": "Fim da faixa de incerteza. O método é explicado junto da análise.",
    "depois_ataque": "Taxa observada em outras partidas, na mesma situação após o evento. Exige pelo menos 20 rounds de 5 partidas.",
}


def field_label(value):
    """Traduz nomes conhecidos e torna legíveis os campos restantes."""
    if isinstance(value, tuple):
        return " ".join(str(field_label(part)) for part in value)
    if not isinstance(value, str):
        return value
    readable = value.replace("_", " ")
    return FIELD_LABELS.get(value, readable[:1].upper() + readable[1:])


def display_value(value):
    return VALUE_LABELS.get(value, value) if isinstance(value, str) else value


def readable_table(table):
    """Cria uma cópia com títulos legíveis, mantendo valores numéricos intactos."""
    result = table.copy()
    if isinstance(result, pd.Series):
        result = result.to_frame()
    result.columns = result.columns.map(field_label)
    result.columns.names = [field_label(name) for name in result.columns.names]
    if isinstance(result.index, pd.MultiIndex):
        result.index = pd.MultiIndex.from_tuples(
            [tuple(display_value(part) for part in row) for row in result.index],
            names=[field_label(name) for name in result.index.names],
        )
    else:
        result.index = result.index.map(display_value).rename(field_label(result.index.name))
    for column in result.columns:
        if not isinstance(result[column], pd.DataFrame) and (
            pd.api.types.is_string_dtype(result[column]) or result[column].dtype == object
        ):
            result[column] = result[column].map(display_value)
    return result


def number_step(values):
    """Passo que fixa as casas exibidas: inteiro para contagens e números grandes, duas casas para o resto."""
    finite = values[np.isfinite(values)] if len(values) else values
    if pd.api.types.is_integer_dtype(values) or finite.empty or (finite % 1 == 0).all() or finite.abs().max() >= 100:
        return 1
    return 0.01


def numbers_stored_as_objects(values):
    """Médias de colunas verdadeiro ou falso deslocadas saem como objeto, mesmo contendo só números."""
    present = values.dropna()
    return values.dtype == object and not present.empty and present.map(
        lambda value: isinstance(value, (int, float, np.number)) and not isinstance(value, (bool, np.bool_))
    ).all()


def display_table(table, *, container=st, column_config=None, percentage_columns=(), **kwargs):
    """Aplica rótulos e formatos sem transformar contagens em porcentagens."""
    config = {}
    # O Streamlit corta as casas do passo sem arredondar, então a cópia exibida já vai arredondada
    shown = table.copy()
    for column in table.columns:
        values = table[column]
        if not isinstance(values, pd.DataFrame) and numbers_stored_as_objects(values):
            values = values.astype(float)
            shown[column] = values
        parts = column if isinstance(column, tuple) else (column,)
        rate_key = next((part for part in parts if part in RATE_COLUMNS), None)
        is_fraction = rate_key is not None or column in percentage_columns
        if is_fraction and pd.api.types.is_float_dtype(values):
            # O passo de 0,001 fixa uma casa decimal na porcentagem, como 30,5%
            shown[column] = values.round(3)
            config[field_label(column)] = st.column_config.NumberColumn(
                format="percent", step=0.001, help=FIELD_HELP.get(rate_key)
            )
        elif pd.api.types.is_numeric_dtype(values) and not pd.api.types.is_bool_dtype(values):
            # O formato plain do Streamlit usa 20 casas e mostra 3565 como 3564.9999999999995
            step = number_step(values.astype(float))
            shown[column] = values.round(0 if step == 1 else 2)
            config[field_label(column)] = st.column_config.NumberColumn(
                format=None if step == 1 else "localized", step=step, help=FIELD_HELP.get(column)
            )
        elif column in FIELD_HELP:
            config[field_label(column)] = st.column_config.NumberColumn(help=FIELD_HELP[column])
    config.update({field_label(key): value for key, value in (column_config or {}).items()})
    return container.dataframe(readable_table(shown), column_config=config, **kwargs)
