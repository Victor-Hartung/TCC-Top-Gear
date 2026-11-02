# Navegacao inspirada no controlador nativo de P2 — 14/09/2026

## Estado da integracao

Implementada na pasta operacional v3.0. Observacao **schema 10, 61 features**,
detector **3**, navegacao **1**, ponte **5**, protocolo **TGSTATE2/TGACT2**.
Continuam 10 acoes, quatro frames por decisao e reset automatico pelo slot 1.
O PPO continua escolhendo todos os botoes. Nao ha escrita em WRAM, alteracao
da ROM, acao imposta por um piloto auxiliar ou mudanca de recompensa nesta entrega.

Esta implementacao aproveita informacoes e margens da rotina nativa investigada
em [PILOTO_AUTOMATICO_P2.md](PILOTO_AUTOMATICO_P2.md). Ela fornece candidatos
de trajetoria ao PPO; nao reproduz bit a bit o controlador de P2 nem garante
desvios sem colisao. Compensacao nativa de curva, suavizacao da direcao e estados
especiais de combustivel/recuperacao nao foram copiados. As features de curva
anteriores continuam disponiveis; a leitura adicional de curva a 128 unidades
fica no diagnostico, sem substituir a fisica do jogo.

**Novo PREFLIGHT real pendente.** Os testes offline e a releitura de capturas
antigas abaixo nao sao uma nova validacao no BizHawk. O recibo anterior permanece
preservado e sera recusado pelo novo contrato/codigo antes de abrir treino.

## Sensor e corredor

- P2 recebe identidade logica reservada **1**, derivada dos offsets dinamicos
  em WRAM 0x0204/0x0206. Seu ID bruto nao identifica o jogador: nas capturas,
  ambos os registros de jogador podem ter ID zero. P1 nunca entra como adversario.
- A identidade exige offsets distintos, alinhados a 18 bytes e dentro dos 20
  registros, alem de coincidencia de lateral/progresso dos registros com as
  globais P1/P2. Quando falha, a mascara informa indisponibilidade; nao se inventa
  um carro ou uma velocidade. Uma amostra invalida tambem invalida sua derivada.
- `detector_samples` conserva o pacote historico de 58 inteiros para os IDs
  2..19. `navigation_samples` acrescenta 14 inteiros por frame, sincronizados:
  frame, offsets P1/P2, progresso/lateral do registro P1, globais P2,
  progresso/lateral do registro P2, word de corredor atual, word a 128 unidades,
  curva a 128 unidades, word 0x1EF3 e word 0x1F04.
- O detector combina os 18 registros tradicionais com P2 quando identificavel.
  As tres regioes antigas ainda selecionam o maior risco; P2 tambem recebe
  features proprias para nao desaparecer quando outro risco e selecionado.
- A tabela 0x7002 + 2*floor(progresso/32) fornece dois bytes assinados,
  multiplicados por 256. Sao **limites internos de trajetoria**, nao bordas
  fisicas comprovadas do asfalto. Usa-se a intersecao dos limites atuais e dos
  limites a 128 unidades de progresso.
- Todos os carros proximos participam do bloqueio dos intervalos laterais,
  independentemente dos tres selecionados. Margem lateral 5120; janela
  longitudinal de -100 a 512; previsao limitada a 30 frames, quando a derivada
  e valida. O movimento lateral absoluto do outro carro determina a varredura,
  para nao confundir o movimento de P1 com o movimento do adversario.
- Intervalos bloqueados sao unidos antes de calcular o espaco livre a esquerda
  e a direita. O alvo candidato fica no centro do intervalo livre mais proximo,
  com desempate a esquerda. Uma travessia por um carro atualmente ao lado e
  recusada. Sem candidato, `target_valid=0`; isso nao significa caminho livre.
- O alvo nao tem garantia dinamica: nao estima toda a capacidade de esterco,
  pode mudar quando outros carros entram no horizonte e nao substitui a leitura
  real de superficie em 0x0727. Obstaculos especificos e autoria do impacto
  continuam sem identificacao comprovada.

As primeiras 47 posicoes da observacao mantem nomes e escalas; a semantica do
sensor agora inclui P2. As 14 novas features, nesta ordem, sao:

```text
navigation_valid, p2_present, p2_gap, p2_lateral,
p2_long_velocity, p2_lateral_velocity, p2_prediction_valid, p2_risk,
corridor_low_delta, corridor_high_delta, left_free_width, right_free_width,
target_delta, target_valid
```

`navigation` nos registros por passo inclui limites brutos/decodificados,
offsets, carros bloqueadores, intervalos e alvo. O TensorBoard acrescenta
`navigation/navigation_valid`, `target_valid`, `p2_present`,
`blocked_car_count` e `target_distance_raw` sob o grupo `navigation`.
Esses graficos medem disponibilidade e orientacao do sensor, nao sucesso de desvio.

## Modelo anterior e migracao

O treino `hermes-ppo_20260913_194800_198463` terminou normalmente com
102.400 passos adicionais e contador 112.640, sem recuperacoes ou rollout
descartado. Seu `final_112640_steps.zip` e metadados permanecem intactos.

`--resume` exige igualdade integral do contrato e recusa esse modelo de 47
entradas no ambiente de 61. A rota explicita `--initialize-policy-from` aceita
somente a expansao conhecida schema9/ponte4/detector2 para schema10/ponte5/detector3,
com o mesmo objetivo road_v3_turbo/recompensa5, ROM, pista, acoes, parametros e
prefixo de features. Mudancas adicionais nao sao liberadas por essa rota.

A importacao copia o ator, acrescenta 14 colunas zero a sua primeira camada e
inicia critico, otimizador e contador novos. A politica anterior e preservada
numericamente para as mesmas 47 entradas; na corrida, a inclusao de P2 pode
alterar essas entradas. Isso e inicializacao de um experimento novo, nao retomada
exata das 112.640 interacoes. Nao garante manter a mesma classificacao.

## Evidencia disponivel e reproducao offline

Em 83 snapshots completos de WRAM da coleta `contexto_20260912_084321_5525`,
o leitor Lua novo confirmou identidade e corredor em 83/83. P2 tinha ID bruto
zero em todos. Ele estava dentro do alcance do sensor em 28 snapshots.
As amostras sao espacadas; nao validam derivadas de quatro frames ou desvio.
Os relatorios ficam em `runs/analysis/native_navigation`, com hashes das fontes.

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe python\audit_native_navigation_snapshots.py
.\.venv\Scripts\python.exe python\check_navigation_migration.py --model "models\hermes-ppo_20260913_194800_198463\final_112640_steps.zip"
```

O ultimo comando testa a importacao em memoria usando 256 observacoes sinteticas,
com novas features variadas. Confere proximidade numerica das probabilidades,
critico intacto, contador zero, otimizador vazio e hash original preservado.
Nao chama `learn`, nao executa episodio e nao salva modelo.

## Proximo passo real

Feche a instancia antiga do BizHawk. Primeiro, no terminal do projeto:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\preflight_live.py
```

Enquanto o servidor aguarda, abra outro terminal e execute:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Abra a ROM oficial e, em **Tools > Lua Console**, somente:

```text
C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0\lua\Top Gear (USA).lua
```

`native_navigation.lua` e um modulo carregado pelo principal: nao o execute
separadamente. Se houver seletor de perfil, escolha `config/game_profile.ini`
da mesma pasta. O script carrega o slot 1 automaticamente.

O preflight verifica controles/reset e, adicionalmente, identidade/corredor em
cada frame e presenca de previsao P2. Falhas ficam no JSON; devem ser investigadas
antes de treino. Um PREFLIGHT OK confirma essas leituras apenas nas trajetorias
curtas do teste. Depois de revisar esse resultado, o piloto proposto e:

```powershell
.\.venv\Scripts\python.exe python\train_hermes_ppo.py --initialize-policy-from "models\hermes-ppo_20260913_194800_198463\final_112640_steps.zip" --timesteps 10240 --checkpoint-every 2048
```

O servidor do treino tambem deve iniciar antes de reiniciar o BizHawk com os
mesmos argumentos e abrir o Lua principal. Os resultados do piloto precisam ser
avaliados antes de aumentar `--timesteps`. Nenhum treino longo foi iniciado nesta entrega.

## Preservacao

Backup anterior a implementacao:
`runs/maintenance/native_navigation_20260913_221244`.
Modelos, logs, evidencias, savestate, ROM, configuracao de recompensa e barra
colorida de progresso foram preservados. Instrucoes e resultados antigos dos
outros documentos permanecem como historico; este documento descreve a integracao atual.

## Verificacao da integracao em 14/09/2026

192 testes automatizados passaram na .venv operacional (Python 3.11.9); baseline anterior: 161. Incluem pacote Lua, reset de historico, P2 com IDs brutos iguais, offsets variaveis, mascaras, corredor ocupado, aproximacao fora do raio publicado, coordenadas absolutas, PPO sintetico, migracao de pesos e recusa de contratos invalidos. Nao sao validacao nova no BizHawk.

Releitura final: `runs/analysis/native_navigation/snapshot_audit_20260914_193942_194603.json` (83/83 identidades e corredores coerentes). Migracao final: `runs/analysis/native_navigation/migration_audit_20260914_193945_003914.json` (cinco verificacoes passaram, modelo original preservado). Novo PREFLIGHT real pendente.
