# Experimento: carro azul, cambio automatico, save 3

Este perfil deriva de `config/game_profile.ini` da v3.0. Mantem a recompensa
`road_v5_race`, as 61 features, as 10 acoes, quatro frames por decisao e os
mesmos controles Type A (X/Y/A). Apenas seleciona o save 3 e exige a identidade
do carro azul e sinais de transmissao automatica nos campos brutos ja
investigados. Nao altera o perfil automatico anterior, o perfil manual, os
modelos, nem os registros de treino.

O usuario salvou o azul automatico no slot 3 em 30/09/2026. O arquivo tinha
112786 bytes e SHA-256
`3700606dffdc27c3cd2a368d8e622ca3c4bd15830b27827c28f49ef196630e72`
imediatamente apos o salvamento. O antigo azul manual do slot 3 tambem existe
em `runs/maintenance/rolling_sustained_20260916_163126/blue_manual_slot3.State`.
O backup do slot 2 manual foi preservado em
`runs/maintenance/blue_auto_20260930/manual_slot2_before_blue_auto.State`.

As leituras `0x1EE8` (offset de tabela do carro), `0x1F7A` e `0x1F7C`
(mascaras de troca) vieram do diagnostico de transmissao existente. Offset 48
identificou o azul no modo manual; as mascaras 0/0 apareceram nos registros
automaticos anteriores. Isso ainda nao prova por si so o modo do novo save.
O preflight real de 30/09/2026 confirmou estas leituras em cinco resets,
controles causais, 61 observacoes, detector e corredor. O recibo individual e
`runs/preflight/preflight_20260930_232901_807315.json` e o status e
`PREFLIGHT OK`. Isto valida a integracao neste save, nao o desempenho da IA.

Na pasta raiz do projeto, iniciar o servidor:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_azul_automatico.ps1 -Modo Preflight
```

Com o BizHawk aberto na ROM correta, abrir **somente**
`lua/Top Gear Azul Automatico (USA).lua` na Lua Console e escolher
`config/game_profile_blue_auto.ini` quando solicitado. O teste escreve um
relatorio individual em `runs/preflight` e um recibo separado
`runs/preflight/latest_blue_auto.json`. Falha de identidade ou de controle
nao libera treino.

Com `PREFLIGHT OK`, um piloto novo de 10.240 passos pode ser executado:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_azul_automatico.ps1 -Modo Treinar -Passos 10240
```

O piloto do zero foi executado em 30/09/2026 em
`runs/hermes-ppo_20260930_233053_573314`. Concluiu 10.240 passos sem erro,
sem recuperacoes e preservou o modelo final em
`models/hermes-ppo_20260930_233053_573314/final_10240_steps.zip`.
Houve sete episodios, todos encerrados sem completar a corrida, todos em 19o.
O progresso final variou de 8.492 a 10.726 de 22.528 unidades da primeira
volta; o tempo fora da pista foi de 72,8% a 90,1%, com 3 a 14 impactos.
As tres cargas de turbo foram gastas em todos os episodios, uma ou duas antes
da largada. Esta amostra verifica a integracao, mas nao demonstra aprendizado
competitivo e nao justifica treino longo do zero sem comparacao.

Existe uma migracao **explicita so do ator** do modelo automatico compativel
de 61 observacoes/10 acoes:
`models/hermes-ppo_20260915_031924_155890/final_10240_steps.zip`.
O ator descende da linhagem automatica anterior, mas seu contrato e de save 1
e recompensa `road_v3_turbo`. Para o azul/save 3/recompensa `road_v5_race`,
o critico, os momentos Adam e o contador sao novos. A validacao recusa
qualquer outra mudanca de acoes, observacoes, sensores, configuracao ou PPO.
Isto e um experimento comparativo, nao uma garantia de melhora nem uma retomada
do treino antigo. Antes dele, repita o preflight do codigo atual.

Com o novo `PREFLIGHT OK`, execute no VS Code um piloto de mesma duracao:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_azul_automatico.ps1 -Modo Treinar -Passos 10240 -ImportarAtor '.\models\hermes-ppo_20260915_031924_155890\final_10240_steps.zip'
```

O script salva modelos e registros em novas pastas. Compare episodios e,
idealmente, uma avaliacao sem treino antes de escolher um treino longo.

Em 30/09/2026 o termo de recompensa `manual_speed_potential` foi removido
tambem do ramo manual. O azul automatico ja nao o recebia; portanto a
recompensa azul `road_v5_race` nao mudou. A versao das configuracoes manuais
passou a 2 para recusar retomada silenciosa de modelos manuais anteriores.
Como `env_topgear.py` mudou, um novo preflight real sera necessario antes do
proximo treino. O usuario executara os comandos de preflight e treino no VS Code.
