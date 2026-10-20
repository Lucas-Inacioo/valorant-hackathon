# Como escrever os textos do projeto

O texto deve ajudar quem acompanha VALORANT a ler os dados. Use frases diretas, palavras conhecidas e uma ideia por parágrafo. Explique a medida perto do gráfico que a usa. Os termos do jogo podem continuar quando ajudam a reconhecer a situação.

## Referências usadas

A pesquisa por expressões associadas a textos de LLMs encontrou uma [lista autoral de Ana Paula Venturella Becker](https://pt.linkedin.com/pulse/palavras-que-o-chat-gpt-ama-voc%C3%AA-precisa-saber-sobre-ana-paula-nbzkf), publicada em 21 de novembro de 2025. Ela serviu para localizar clichês e excesso de formalidade. Uma palavra isolada não identifica a origem de um texto, e a lista não foi usada como detector de IA nem como medição de frequência dos modelos.

O [Manual de Comunicação do Senado](https://www12.senado.leg.br/manualdecomunicacao/estilos/palavras-mais-simples) orienta escolher palavras conhecidas, escrever na ordem direta e explicar termos técnicos. A [Trilha de Linguagem Simples da Prefeitura de São Paulo](https://linguagemsimples.prefeitura.sp.gov.br/trilha-linguagem-simples/) reúne materiais de revisão e um glossário para apoiar as trocas de vocabulário. As fontes foram consultadas em 20 de outubro de 2026.

## Trocas conforme o sentido

Não substitua palavras em todo o código de forma automática. Escolha a expressão que descreve a ação ou a medida.

| Quando aparecer | Prefira no texto do projeto |
| --- | --- |
| utilizar | usar |
| realizar uma análise | analisar |
| crucial, fundamental ou essencial sem motivo concreto | explicar por que algo importa ou retirar o adjetivo |
| robusto sem um teste que sustente a afirmação | informar qual teste foi feito e seu resultado |
| alavancar ou potencializar | dizer o que aumenta ou melhora |
| sinergia | descrever a ação conjunta das equipes ou jogadores |
| aprofundar, explorar ou desvendar usados como convite genérico | ver, comparar ou analisar o assunto específico |
| cabe ressaltar ou é importante notar | começar pela informação |
| além disso repetido em todo parágrafo | usar também, e ou uma nova frase quando a ligação for necessária |
| abordagem | método, regra, conta ou forma, conforme o caso |
| metodologia | método, quando significar um procedimento |
| otimizar | informar o que fica mais rápido, menor ou mais claro |
| insights | resultados, observações ou perguntas que os dados levantam |
| esperado por vivos | comparação por jogadores vivos e a definição do grupo usado |
| resíduo | diferença da referência, com a subtração explicada |
| controle pela equipe | diferença da média da equipe, quando houver apenas essa subtração |
| loadout | valor do equipamento no início do round |
| snapshot | registro de posições naquele instante |
| timestamp | instante ou tempo do evento |
| suporte insuficiente | faltam rounds ou partidas para comparar |
| proxy | medida aproximada, seguida do que ela observa |
| impacto quando há apenas comparação observada | diferença ou associação |
| default e execução rápida inferidos só pelo relógio | plant após 40 segundos e plant em até 40 segundos |

## Nomes que precisam de explicação perto do resultado

Uma comparação por jogadores vivos reúne casos com a mesma quantidade de aliados e adversários vivos. Ela pode usar vitória ou defuse, conforme o gráfico. Por isso, o texto deve dizer qual resultado está sendo comparado e quando os vivos foram contados.

A comparação com situações parecidas da página da rodada também considera fase, equipamento e tempo. Ela usa outras partidas e exige uma quantidade mínima de rounds e partidas. Essa definição é diferente da comparação que usa apenas os vivos.

Wilson é o nome do cálculo de intervalo para uma proporção. A interface deve dizer que a faixa representa incerteza estimada e que os rounds da mesma partida compartilham condições. Reamostragem por partida significa repetir a conta com diferentes seleções de partidas.

A taxa de acerto de previsão considera apenas palpites feitos. O erro entre esses palpites é um menos a taxa de acerto. Jogos sem palpite precisam aparecer separados, e a comparação com o histórico precisa usar os mesmos jogos.

## Pontuação e apresentação

Prefira pontos e conectivos a sequências com dois-pontos, ponto e vírgula ou travessão. Mantenha a pontuação que faz parte de código, URLs, horários e nomes oficiais. Use listas e tabelas quando elas ajudarem a comparar informações, sem transformar cada frase em um cartão ou destaque.

Os nomes de colunas internos ficam estáveis para não quebrar cálculos. Cabeçalhos apresentados ao leitor usam palavras completas. Nomes novos de variáveis e funções devem indicar a informação ou ação, como `first_death_time`, `plant_seconds` e `prediction_section`, em vez de abreviações soltas.
