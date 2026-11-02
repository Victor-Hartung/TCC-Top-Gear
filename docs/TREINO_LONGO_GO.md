> Revisao atual:47features/schema9,detector2,ponte4. Corrigida associacao entre carro e risco.136 testes offline passaram; repetir preflight real apos esta correcao. [Evidencias e procedimento](REVISAO_DETECTOR_20260912.md).

> Versao operacional atual: detector integrado experimental,47features/schema8,ponte4.134 testes offline passaram; novo preflight real pendente. Veja [contrato e comandos](INTEGRACAO_DETECTOR.md). Instrucoes anteriores abaixo sao historico e nao autorizam retomar modelos de26features.

# Experimento prolongado a partir do GO

Preparado em12/09/2026 a pedido do usuario. Preflight e modelo foram conferidos;
nenhum treinamento foi iniciado automaticamente durante a preparacao.

Modelo inicial: hermes-ppo_20260912_105450_854879/final_10240_steps.zip.
204800 passos adicionais (100 rollouts de2048), total previsto215040.
Checkpoint periodico a cada20480 adicionais, salvo depois da atualizacao no inicio
do proximo rollout. O ultimo bloco e salvo no arquivo final. Modelo inicial e
registros anteriores preservados; cada execucao cria nova pasta.

```powershell
.\scripts\treino_longo_go.ps1 -Passos 204800 -CheckpointCada 20480
```

Execute na raiz da v3.0, depois abra/reinicie somente lua/Top Gear (USA).lua.
Se o BizHawk estiver fechado, abra depois do servidor Python estar aguardando:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Mantenha nucleo e slot1 do preflight. Nao execute diagnostico_contexto simultaneamente.
O treino confere cada reset contra o preflight. Nao operar savestates durante o treino.
Passos arbitrarios sao arredondados para cima ate completar rollout de2048.
O parametro altera passos adicionais, nao o total historico do modelo.
Executar este launcher novamente parte SEMPRE do checkpoint inicial de10240;
para retomar um treino interrompido, usar --resume com seu checkpoint compativel.
Ctrl+C solicita salvamento de interrupcao; fechamento forcado pode perder o bloco atual.

## Curvas

Em outro terminal na raiz:

```powershell
.\.venv\Scripts\python.exe -m tensorboard.main --logdir .\runs --host 127.0.0.1 --port 6006
```

Abra http://127.0.0.1:6006. Observe rollout/ep_rew_mean, rollout/ep_len_mean,
race/completion_rate, race/win_rate e train/approx_kl. race/current_offtrack_fraction
representa o episodio em andamento; nao confundir com media por episodio.
monitor.csv e episodes.jsonl guardam metricas dos episodios concluidos para a curva
por episodio. steps.jsonl preserva transicoes completas. A curva desta continuacao
comeca com contador10240; wins/episodes locais recomecam nesta execucao.

## Interpretacao

Observacao schema7 com26features,10acoes e recompensa v4/road_v2 mantidas.
Detectores experimentais de proximidade lateral/traseira NAO estao integrados.
Adversarios ainda mascarados antes de lap=0. Mais passos nao resolvem ausencia de
informacao ou comprovam que o agente aprendeu a evitar impactos.
Nao houve avaliacao deterministica bem-sucedida do modelo inicial deste contrato;
trata-se de experimento exploratorio, nao comparacao causal controlada.
Depois do treino, comparar checkpoints inicial/intermediarios/final por avaliacao
sem aprendizado, mesmo save e referencia de aceleracao. Melhora de recompensa
sozinha nao comprova conclusao de tres voltas nem primeiro lugar. Uma seed e um
save nao demonstram generalizacao. Nenhuma nova memoria foi promovida a validada.
