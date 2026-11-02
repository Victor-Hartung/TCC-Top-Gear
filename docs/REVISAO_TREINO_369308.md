# Revisão do treino interrompido e recuperação de coleta

Execução analisada: `hermes-ppo_20260912_175046_376997`. Revisão local em 12/09/2026.
Base exclusiva: v3.0 operacional, ponte 4, observação 9 com 47 features, detector 2,
10 ações, recompensa 4 / road_v2. Nenhuma versão anterior foi restaurada.

## Evidência examinada

Foram percorridos os 1.955.361.240 bytes de `steps.jsonl`: 365.212 passos aceitos
e 280 resets. O contador 369.308 inclui os 4.096 passos do piloto. Os 279 episódios
encerrados constam de `episodes.jsonl`; o episódio 280 foi interrompido após 56
ações aceitas. Os eventos do TensorBoard também foram exportados.

Artefatos reproduzíveis:

- [Análise JSON com hashes, janelas e contagens](../runs/analysis/hermes-ppo_20260912_175046_376997_20260913_014036_652110/analysis.json).
- [Curvas por episódio](../runs/analysis/hermes-ppo_20260912_175046_376997_20260913_014036_652110/curvas_treino.png).
- [Scalars originais do TensorBoard](../runs/analysis/hermes-ppo_20260912_175046_376997_20260913_014036_652110/tensorboard_scalars.json).
- [Código da análise](../python/analyze_training_run.py).

Os nomes dos artefatos usam UTC e podem ter data do dia seguinte à data local.
A primeira tentativa de gerar a figura terminou por ausência de matplotlib,
depois de salvar o JSON; foi preservada. A segunda análise terminou integralmente.
Matplotlib 3.10.8 e dependências de gráficos foram instalados na própria `.venv`;
as versões constam de `requirements-analysis.txt`. NumPy, Torch e SB3 foram mantidos.

## O que foi aprendido

| Medida | Primeiros 20 episódios | Últimos 20 episódios | Últimos 100 episódios |
|---|---:|---:|---:|
| Corridas completas | 0/20 | 11/20 | 79/100 |
| Vitórias | 0 | 0 | 1 |
| Recompensa média | 2,05 | 69,26 | 80,40 |
| Fora da pista, média por episódio | 27,13% | 1,35% | 0,91% |
| Impactos por episódio | 7,20 | 5,60 | 6,81 |
| Posição média entre chegadas completas | — | 6,36 | 5,62 |

No conjunto, 163/279 corridas completas (58,4%) e uma vitória. A vitória ocorreu
no episódio 249, contador global 330.439. O candidato salvo naquele momento é
`models/hermes-ppo_20260912_175046_376997/training_candidate_330439_steps.zip`.
Ele é candidato de treino, não modelo aprovado por avaliação independente.

Todas as chegadas completas tinham resultado válido e `lap == total_laps == 3`.
O progresso líquido estava entre 67.535 e 67.679 unidades, próximo de
`3 * 22.528 = 67.584`. Não houve bônus de chegada em encerramento incompleto.
Isso reforça a consistência da telemetria de chegada; não substitui avaliação
visual independente nem demonstra generalização para outros saves/pistas.

O desempenho não foi monotônico: episódios 221–260 completaram 40/40 corridas;
261–279 completaram 10/19. Nos últimos 20, incluindo o episódio 260, foram 11/20.
O gráfico de reward sozinho esconderia parte dessa queda.

A política não colapsou em BRAKE. Nos últimos 100 episódios predominam
LEFT_ACCELERATE (52.705 ações), TURBO_ACCELERATE (36.309) e RIGHT_ACCELERATE
(18.652). A ação de turbo também funciona como aceleração quando não há carga
ou já há turbo ativo; sua frequência não é a contagem de nitros consumidos.
Os impactos normalizados pelo progresso caíram de aproximadamente 8,78 para
1,96 por volta equivalente, comparando os primeiros e últimos 20 episódios.
O bit genérico continua sem identificar o responsável ou o objeto do impacto.

## Detector, sincronização e PPO

- Nenhum delta de frames incorreto nos passos registrados; todos os 280 resets
  tinham a mesma telemetria inicial.
- Replay explícito de 2.721 pacotes do detector: todos os resets, amostra a cada
  1.000 passos e janelas de impacto. Zero diferenças nos candidatos recalculados
  e zero violações de limites nas 21 features novas dessa amostra. Não foi
  recalculado todo o detector dos 365.212 passos.
- Houve aviso de algum candidato nos 32 frames anteriores a 1.930 das 2.085
  janelas de impacto. Isso é associação temporal, não recall: o bit não separa
  carros de obstáculos e não há rótulo independente para atribuir causa.
- TensorBoard tem 178 pontos de reward de coleta, terminando em 368.640 passos.
  `train/*` é publicado com atraso de uma coleta pelo fluxo de logs do SB3;
  não equivale a uma inspeção da última atualização após o dump.
- Checkpoint de falha: contrato, SHA-256 e ZIP válidos; PPO.load executado,
  pesos finitos, contador 369.308 e 1.800 épocas contabilizadas no modelo.
  Carregamento pelo novo treinador preservou exatamente os tensores da política.
- 668 passos aceitos pertenciam ao último bloco incompleto. Eles foram registrados,
  mas não receberam atualização PPO. Os pesos já atualizados foram preservados.

## Falha e correção

Últimos estados aceitos do episódio 280: frame 5.392, lap -1, progresso 22.254;
frame 5.396, lap 0, progresso 22.275. A chamada seguinte rejeitou uma volta negativa.
O pacote rejeitado não foi gravado pela versão anterior; a ação rejeitada e os
demais valores desse pacote não podem ser reconstruídos honestamente do log.

Há outros pulsos no contador durante o treino: 66 transições 1→0, 18 de 2→1,
25 de 3→2 e uma de 1→3. O reward já usa progresso modular para não pagar por
pulsos de volta. A hipótese de um pulso análogo na largada é plausível, mas a
causa exata do -1 não foi comprovada. Não foram alterados endereços nem aplicada
uma correção artificial de lap.

Tratamento implementado:

1. `TopGearEnv` lança `LapSentinelRegression`, com ação, passo, estado anterior,
   estado rejeitado e campos do protocolo. Exige reset antes de qualquer novo step.
2. `RecordingEnv` salva o diagnóstico e descarrega os logs imediatamente.
3. `ResilientPPO`, somente no treino, descarta o bloco de coleta incompleto.
   A transição rejeitada não recebe recompensa, terminal falso ou bootstrap.
   Pesos e otimizador das atualizações anteriores permanecem intactos.
4. O reset usa a ponte e a mesma verificação do savestate aprovada no preflight.
   A coleta continua em um bloco vazio; a barra e o contador não recomeçam do zero.
5. Cada ocorrência fica em `runs/<nova execução>/recoveries/recovery_*.json`,
   inclusive falhas de reset. O TensorBoard recebe `recovery/count` e
   `recovery/discarded_rollout_steps`.
6. São permitidas até três recuperações em uma janela de 10.000 passos aceitos.
   A quarta indica problema recorrente e para com diagnóstico. ACK incorreto,
   timeout, conexão rompida, detector inválido, mudança de save e demais erros
   não são repetidos automaticamente.

Os passos aceitos de um bloco descartado continuam no contador e nos logs,
mas não no aprendizado. `status.json` distingue passos treinados nesta execução,
passos descartados e contador da última atualização. Essa mudança é recuperação
de uma anomalia, não prova de correção da origem do valor na memória.

Sensores, ações, recompensa e hiperparâmetros não mudaram; o contrato do modelo
continua compatível. O ambiente e o treinador mudaram: os hashes críticos incluem
os novos módulos, e o preflight anterior é corretamente recusado. Não foi editado
nenhum recibo para declarar aprovação real.

## Melhorias aplicadas e próximas comparações

Além da recuperação e dos diagnósticos, o TensorBoard agora registra médias dos
últimos 100 episódios para conclusão, vitória, fora da pista, impactos, progresso
e parada. A posição média considera apenas chegadas completas e usa 1 para primeiro.
As médias são baseadas nos episódios encerrados, não no ponto da pista em que
o painel foi atualizado. Não apagamos as séries antigas.

Prioridades recomendadas:

1. Comparar em avaliação sem aprendizado o checkpoint interrompido, o candidato
   da vitória e um checkpoint periódico anterior. A última política não deve ser
   declarada melhor só por ser a mais recente. Repetições determinísticas do mesmo
   save medem reprodução; não são condições independentes.
2. Concluir o orçamento em uma continuação com os mesmos pesos/configuração e
   observar as curvas esportivas. Uma experiência separada com taxa de aprendizado
   menor pode investigar a oscilação, mas estes dados não provam que essa seja a
   causa. Alterar PPO/reward exige contrato experimental próprio, sem adulterar
   os metadados do modelo atual.
3. Validar o efeito do detector sobre desvio com avaliações comparáveis e cenas
   rotuladas. A presença do sensor e a diminuição dos impactos não isolam sua
   contribuição causal. Evitar penalizar todo aviso como se fosse uma colisão.
4. Investigar estratégias de nitro e ultrapassagem usando eventos reais de
   ativação, velocidade e progresso. Não aumentar a penalidade genérica de impacto
   sem separar a origem; isso já favoreceu políticas paradas em evidências antigas.
5. Depois de estabilizar esta política, variar saves/sementes e manter cenários
   de avaliação separados. Timer, obstáculos específicos e autoria das colisões
   continuam limitações abertas; nenhuma memória nova foi inventada.

## Próximos comandos

Primeiro, repetir o teste curto real porque o ambiente mudou:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\preflight_live.py
```

Em outro terminal, depois que o servidor estiver aguardando, abrir o BizHawk
com a conexão nova e executar somente o Lua principal da mesma v3:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Lua: `lua/Top Gear (USA).lua`. Manter o slot 1 atual no GO. Não sobrescrever o save.
O preflight básico não força uma regressão de lap; a recuperação foi testada
com uma ponte simulada, e sua primeira ocorrência real permanecerá identificada
como tal nos novos diagnósticos.

Depois de PREFLIGHT OK, a retomada está preparada, sem partir do piloto:

```powershell
.\scripts\retomar_treino_detector.ps1
```

O padrão retoma `failed_369308_steps.zip` e coleta 137.216 passos adicionais
(67 blocos de 2.048). Sem novas recuperações, isso leva o contador a 506.524;
excluindo os 668 passos não treinados da falha anterior, completa o orçamento
arredondado original de 501.760 passos treinados adicionais ao piloto.
Pode editar `-Passos`, sempre adicionais. Uma nova execução exige nova conexão
do BizHawk ao servidor Python; os pesos/logs antigos ficam intactos.

Avaliação do checkpoint interrompido, separada do treinamento:

```powershell
.\.venv\Scripts\python.exe python\avaliar_modelo.py --model ".\models\hermes-ppo_20260912_175046_376997\failed_369308_steps.zip" --episodes 1 --require-preflight
```

As recomendações de avaliação não foram executadas no emulador nesta revisão.
Nenhum treinamento longo foi iniciado automaticamente.
