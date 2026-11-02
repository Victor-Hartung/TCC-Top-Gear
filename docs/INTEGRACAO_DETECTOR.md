> Revisao atual:47features/schema9,detector2,ponte4. Corrigida associacao entre carro e risco.136 testes offline passaram; repetir preflight real apos esta correcao. [Evidencias e procedimento](REVISAO_DETECTOR_20260912.md).

# Integracao experimental do detector ao PPO — 12/09/2026

Codigo integrado, validacao BizHawk real pendente. Nenhum treino novo foi iniciado.
Apos o novo PREFLIGHT OK, executar piloto de4096passos e examinar estabilidade dos
novos campos antes do experimento longo. Os scripts nao substituem essa verificacao.

## Contrato

TGSTATE2/TGACT2 mantidos; bridge_revision=4, observation_schema=8,47features.
Acrescidas21features as26anteriores: para frente/tras/lado a lado, respectivamente,
presenca, gap normalizado pelo raio10% da pista, lateral/65536, velocidade relativa
longitudinal/100, lateral/4096, prediction_valid, risco maximo no grupo. Valores
limitados a[-1,1] para coordenadas/velocidades e[0,1] para mascaras/risco. Grupo
sem candidatos e zerado com present=0; risco vem do maximo do grupo, demais campos
do carro mais proximo em distancia longitudinal absoluta. IDs nao entram na rede.

Risco e max(0,1-tempo_de_entrada/30) quando a extrapolacao linear encontra
sobreposicao longitudinal e lateral. Nao e probabilidade calibrada nem colisao
inevitavel. Acoes10, PPO e recompensa v4/road_v2 mantidos. Aviso nao pune agente
nem move volante automaticamente. Reset continua fora das acoes.

Lua envia detector_samples em cada resposta, formato por amostra:
frame,player_progress,player_lateral,track_length,(id,progress,lateral)*18.
Quatro amostras consecutivas separadas por ponto-e-virgula, colhidas APOS cada
frame real de acao. Reset com zero frames extras fornece so uma amostra e nenhuma
velocidade anterior. Primeiro step fornece4frames e permite derivada sobre3frames.
Ordem por ID; IDs2..19 completos e unicos. Historico comeco/fim e posicao final
conferidos pelo Python. Sem novos enderecos: tabela0x0212, stride18, campos+0/+2/+7.
Leitura do detector inclui lap=-1; os sensores legados de adversarios continuam
mascarados nessa fase. Historicos e candidatos constam dos logs de treino/preflight.

Modelo antigo tem26entradas: nao pode retomar diretamente a rede de47entradas.
Modelos/metadados antigos preservados e recusados antes de carregar politica.
Preflight antigo tambem recusado por contrato/hashes novos. Nao editar JSONs antigos.

## Validacao executada

134 testes offline passaram, incluindo Lua real com APIs simuladas, pacotes
malformados, reset, dados antes de lap0 e PPO em transicoes sinteticas.
check_detector_parity.py comparou5capturas reais ja salvas:17675frames,128555
comparacoes de candidatos sem divergencia de validade/previsao/tempo de entrada
contra o detector offline anterior. Isso e replay, nao teste da ponte no BizHawk.
O script exige dado por frame mesmo que politica tome decisoes a cada4frames.

Preflight ampliado registra47observacoes, candidatos e features do detector,
confere quatro amostras por step, reset identico e existencia de previsao valida.
Nao comprova taxa de acerto fisica, identidade universal ou generalizacao.

## Proximo passo do usuario

Pare diagnostico_contexto e qualquer Lua antigo. Na raiz correta:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\preflight_live.py
```

Depois, se precisar abrir BizHawk, em outro terminal:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Abra ROM, mantenha o slot1 noGO e nucleoBSNESv115+ usados antes. Execute somente
lua/Top Gear (USA).lua ATUAL da mesma v3.0 no Lua Console. Se pedir perfil, selecione
config/game_profile.ini da mesma pasta. O preflight salva JSON novo; agente deve
examina-lo antes de recomendar treino.

Apos sucesso real e revisao, piloto:

```powershell
.\scripts\treino_detector.ps1 -Passos 4096
```

Modelo novo por padrao. Para treino longo apos revisar piloto:

```powershell
.\scripts\treino_longo_go.ps1 -Passos 204800 -CheckpointCada 20480 -Retomar "CAMINHO_DO_MODELO_COMPATIVEL_DO_PILOTO.zip"
```

O caminho acima e marcador, nao arquivo real. Substituir pelo checkpoint do piloto.
Sem -Retomar inicia modelo novo. Arquivos e pastas de cada execucao sao unicos.
204800 e quantidade adicional; outros numeros arredondam ao rollout2048.

## TensorBoard

Corrigida dependencia: setuptools80.9.0 fixado porque TensorBoard2.20 importa
pkg_resources (ausente em84.0.0). requirements/constraints atualizados, pip check OK.
Somente setuptools alterado na .venv. Comando testado por --help; nenhum servidor
permanente iniciado durante a integracao. Aviso deprecacao de pkg_resources nao
impede uso; TensorFlow nao e necessario para os logs PPO.

```powershell
.\.venv\Scripts\python.exe -m tensorboard.main --logdir .\runs --host 127.0.0.1 --port 6006
```

Abra http://127.0.0.1:6006. Compare recompensa, conclusao, progresso, offtrack e
checkpoints avaliados, sem chamar aumento de recompensa de vitoria comprovada.

## Preservacao

Backup de codigo/testes/config/scripts e manifesto em runs/maintenance/before_live_detector_*.
Capturas, videos, savestates, modelos e recibos originais nao foram reescritos.
Docs historicos permanecem com notas de versao. Curva de aprendizado sem detector
nao deve ser apresentada como comparacao controlada com nova rede de47features.
