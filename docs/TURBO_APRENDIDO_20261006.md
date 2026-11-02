# Estado da correcao experimental do turbo

O perfil azul automatico/save 3 usa `road_v6_outcome`, recompensa 11 e
`gae_lambda=0.995`, com gamma 0.999. A observacao continua com 61 features
e o espaco continua com dez acoes. Nao ha regra de horario/volta/velocidade
para gastar uma carga nem substituicao das acoes propostas pelo PPO.

Desde 12/10 a multa por imobilidade e -0,10 e uma nova melhor colocacao paga
+1,00 por posicao. Desde 14/10, cada posicao perdida custa -1,00.
O fluxo de treino/play continua igual, com retomada versionada do mesmo cerebro.
[Perda de colocacao](PERDA_COLOCACAO_20261014.md). [Detalhes e preflight](RECOMPENSAS_PARADO_ULTRAPASSAGEM_20261012.md).
As coletas e a migracao de objetivo descritas abaixo sao o historico anterior.

O registro de 10.240 passos do piloto `hermes-ppo_20260930_233053_573314`
mostrou 23 cargas consumidas, incluindo duas da corrida parcial final;
11 foram consumidas enquanto lap ainda era -1. Esse sentinela nao identifica
o GO: no preflight salvo, o carro se movimentou desde o passo 55 e somente
chegou a lap=0 no passo 101. A recompensa anterior descartava progresso,
impactos e superficie nesse trecho e na transicao -1 para 0.

A auditoria encontrou 5.209 unidades de progresso novo elegivel descartadas,
uma colisao e 39 passos fora da pista conhecidos. O piloto automatico anterior
tambem usava turbo cedo e completou 8/8 episodios; por isso consumir durante
lap=-1 nao pode ser tratado automaticamente como desperdicio.

O objetivo novo conta deltas modulares reais desde o reset, incluindo esse
trecho, sem inventar lap=0, memoria do GO ou distancia inicial percorrida.
Somente distancia nova em asfalto conhecido e sem impacto recebe credito;
recuar e recuperar nao paga de novo. Impactos e saídas da pista voltam a ser
contados antes da linha. A primeira publicacao de rank nao vira ultrapassagem.
Chegada continua exigindo resultado valido e lap==total_laps==3.
Limites tecnicos continuam sendo truncamentos, sem recompensa ficticia de chegada.

Nao ha premio por apertar turbo, multa por carga guardada, custo de reserva
por volta ou bonus de velocidade manual. As recompensas de progresso, posicao
e resultado sao os sinais para aprender seu valor. Uso cedo pode ser correto;
o teste deve medir beneficio na corrida, e nao somente espacamento das cargas.

Lambda maior aumenta a propagacao direta dos residuos TD. Para um efeito
81 decisoes depois, o coeficiente (gamma*lambda)^81 passa de aproximadamente
0.0145 para 0.6144. Isso nao e uma porcentagem de beneficio aprendido nem um
horizonte rigido: o critico, recompensas intermediarias e fronteiras do rollout
tambem contam. Maior lambda aumenta a variancia. Referencia:
[Schulman et al., Generalized Advantage Estimation](https://arxiv.org/abs/1506.02438).

Os logs agora medem, por carga, distancia liquida, distancia nova limpa,
frames observados, impactos, saídas da pista e se o boost foi observado ate
o fim ou cortado por encerramento. Sao resultados observados durante o turbo,
nao uma estimativa causal de quanto ele melhorou em relacao a nao usar turbo.

Validacoes offline preservadas em `runs/analysis/turbo_reward_20261002`:

- `evidence_summary.json`: auditoria dos registros existentes.
- `reward_replay.json`: recalculo dos 10.240 passos, com erro maximo zero na
  reproducao da recompensa antiga. Nos mesmos estados, o credito de progresso
  passa de 8.7544 para 13.3789; isso nao preve desempenho de politica nova.
- `actor_audit.json`: copia do ator real em memoria com diferenca maxima zero
  nas probabilidades, critico novo preservado, otimizador vazio e contador zero.
- `tests.txt`: 272 testes offline aprovados na implementacao inicial.
- `tests_package_20261006.txt`: verificacao final do codigo do pacote.

Modelos, saves e evidencias anteriores foram preservados. O perfil automatico
historico/save 1 continua v5; a versao anterior do azul esta no backup
`runs/maintenance/turbo_outcome_20261002`. A importacao para v6 e explicita
e limitada ao ator; ela nao e retomada de um critico antigo.

Ainda nao foi executado preflight real nem treino com v6. Os comandos para
o usuario executar estao em `LEIA_PRIMEIRO_OUTRO_PC.md`; o preflight e requisito
antes de qualquer treino. O problema de frenagens desnecessarias continua sem
correcao de comportamento comprovada. Estas mudancas nao garantem melhor
momento de turbo nem vitorias consistentes.
