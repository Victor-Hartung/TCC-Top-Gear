> 27/09/2026: **PREFLIGHT OK no BizHawk real**, azul/manual/save 2. Os 13 criterios passaram, incluindo R/L, liberacao/limites e sinal bruto de conta-giro variavel. Recibo: `runs/preflight/preflight_20260927_151815_470372.json`. Savestates conferidos por SHA-256 e preservados. Treino manual novo de 500000 passos iniciado em `hermes-ppo_20260927_152129_971034`; isso ainda nao demonstra aprendizado ou vantagem sobre o automatico.

# PPO com cambio manual — azul, save 2

> Atualizacao de 30/09/2026: o termo de recompensa manual descrito abaixo foi removido do codigo atual. Este texto preserva a configuracao e as evidencias historicas. O contrato manual atual mudou; checkpoints manuais anteriores nao podem ser retomados diretamente. O perfil azul automatico nunca usou aquele termo.

Implementacao de 16/09/2026. Calibracoes comparativas de quarta/quinta encerradas
por orientacao do usuario. Nenhuma quinta ou faixa ideal e imposta ao agente.
Nao ha validacao real desta nova ponte ainda; os ensaios anteriores comprovam os
comandos manuais, mas nao substituem o preflight do contrato novo.

## Memoria e evidencias

- WRAM 0x1E72, u16: marcha bruta 0..4, HUD GEAR 1..5. Confirmada por pulsos R/L
  e capturas do painel, incluindo o azul em cambio_manual_20260915_201647_5718_0.
- WRAM 0x1E5E, s16: entrada bruta do desenho do conta-giro. A ROM calcula o campo
  em 05:D2E7–05:D309 a partir de velocidade/marcha; a rotina 00:D3CF le esse
  campo para desenhar a barra. Esta e evidencia estatica da ROM e leitura nas
  coletas existentes, nao calibracao de RPM fisicos ou de troca ideal no vermelho.
- WRAM 0x1EE8=48 identifica a tabela do azul observado; 0x1F7A=16 e 0x1F7C=32
  sao as mascaras de R/L observadas no manual Type A. Conferidas apos cada reset
  e passo, antes de aceitar a transicao. Nao se escreve diretamente na RAM.

Fontes preservadas: runs/analysis/transmission_20260915/rom_excerpts.txt,
memory_candidates.json, blue_hud_review_20260915_231928_220312.json e as
coletas/imagens em runs/diagnostics. ROM SHA-1 f686806c676a4b087a3627babbe3555d3704e3b1.

## Aprendizado e recompensa

O PPO recebe 63 features: as 61 anteriores, o conta-giro bruto dividido por
32768 e o ultimo comando de cambio (0 manter, +1 subir, -1 reduzir).
A marcha e a velocidade ja faziam parte das 61. Nenhuma escala fisica de RPM
foi inventada; dados brutos ficam nos logs para investigacao.

As 30 acoes combinam as dez acoes atuais com manter, R ou L. IDs 0..9 mantem;
10..19 sobem; 20..29 reduzem. Aceleracao, direcao e turbo continuam disponiveis
durante a troca. Cada comando dura quatro frames reais. Repetir R ou L mantem o
botao; o agente deve libera-lo com uma acao sem esse botao antes de nova troca.
O ultimo comando na observacao torna essa condicao visivel ao PPO.

A recompensa road_v5_race continua premiando progresso novo no asfalto e chegada
valida, e penalizando impacto, fora da pista, tempo e encerramento incompleto.
O perfil manual acrescenta shaping potencial de velocidade:

    Phi(s) = 0.5 * max(velocidade_bruta, 0) / 16384
    adicional = gamma * Phi(proximo) - Phi(anterior)

No terminal verdadeiro, Phi(proximo)=0; truncamento conserva o potencial para o
bootstrap de valor do PPO. Usa-se o mesmo gamma do PPO (0.999). Isso fornece sinal
mais imediato do efeito de acelerar/trocar, mantendo o objetivo de corrida.
Frear e recuperar a mesma velocidade nao da lucro descontado de shaping; perdas
por impacto tambem nao sao ocultadas. Nao se paga simplesmente por trocar,
pressionar acelerador ou encher o conta-giro. Trocas precoces/tardias prejudiciais
reduzem o ganho de velocidade/progresso; o ponto util deve ser aprendido.
Nao ha garantia de aprender o melhor ponto ou vencer em 500 mil passos.

No TensorBoard: manual/gear, manual/gear_changed, manual/shift_command,
manual/engine_gauge_raw, manual/speed_delta e reward_components/manual_speed_potential.
Nos steps.jsonl: comando completo, acao base, marcha anterior/atual, giro bruto,
variacao de velocidade e componentes de recompensa. Cada corrida tambem conserva
os indicadores de chegada, colocacao, impactos e progresso.

## Contratos e preservacao

Automatico permanece com config/game_profile.ini, slot 1, 61 features/schema 10,
10 acoes/schema 2 e ponte 5. Manual usa config/game_profile_manual.ini, slot 2,
63 features/schema 11, 30 acoes/schema 3 e ponte 6. TGSTATE2/TGACT2 continuam.
O perfil manual usa PPO novo; arquivos e saves anteriores permanecem intactos.
Retomada somente de modelo manual com contrato identico. Nao houve copia do ator
antigo para fingir que ele conhece as novas acoes. Nenhuma alteracao do save 1/2/3.
Backups dos fontes anteriores ficam em runs/maintenance/manual_ppo_20260916_164623.

## Proximo passo: preflight da integracao

Feche o BizHawk antigo antes de abrir a instancia com socket. No primeiro terminal:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_manual.ps1 -Modo Preflight
```

No segundo terminal:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Abra a ROM Top Gear (USA). Na Lua Console, execute somente
`lua/Top Gear Manual (USA).lua`. Quando solicitado, selecione
`config/game_profile_manual.ini` desta pasta v3.0. O reset usa automaticamente o
save 2 azul manual; nao e necessario dirigir. O preflight verifica os cinco
controles basicos, reset deterministico, detector, as leituras manuais e
subida/reducao/liberacao/limites. Ele nao mede qual marcha ganha uma disputa.
O recibo novo e runs/preflight/latest_manual.json; historico individual preservado.

## Treino depois de PREFLIGHT OK

Se houver erro no preflight, investigar o JSON antes de treinar. Com PREFLIGHT OK:
pare o script Lua, feche o BizHawk e execute no primeiro terminal:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_manual.ps1 -Modo Treinar -Passos 500000
```

Abra novamente o BizHawk pelo mesmo comando do segundo terminal, ROM e Lua manual.
Ajuste -Passos conforme desejar. PPO completa blocos de 2048; 500000 pode concluir
em 501760. Ctrl+C interrompe e preserva checkpoint. Para retomar um checkpoint
manual compativel, acrescente -Retomar "caminho absoluto do modelo.zip";
Passos indica quantidade adicional. Sem -Retomar, inicia outra rede nova.
ExecutionPolicy Bypass vale apenas para o processo deste comando.

Validacao offline e seus resultados constam em TEST_RESULTS.md. Nao iniciar
outros scripts de treino/avaliacao simultaneamente na porta 55355.

Verificacao de 27/09/2026: 250 testes offline passaram (51,625 s); resultado e
hashes dos fontes em runs/analysis/manual_ppo_20260927_151023_954728.
Preflight manual real continua pendente.
