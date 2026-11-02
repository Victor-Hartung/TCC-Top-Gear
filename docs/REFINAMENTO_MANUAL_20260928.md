# Refinamento manual — 28/09/2026

## Resultado que motivou a mudanca

A comparacao real de dez corridas por modelo, usando as mesmas sementes de
amostragem (5101–5110), favoreceu o checkpoint de 263.179 passos:

| Modelo | Tres voltas | Posicao media entre chegadas | Impactos medios |
|---|---:|---:|---:|
| Candidato 263.179 | 9/10 | 8,56 | 6,5 |
| Final 500.652 | 5/10 | 9,00 | 5,7 |
| Candidato, primeiro nitro adiado ate velocidade bruta 3000 | 9/10 | 9,00 | 8,2 |

O candidato foi melhor em sete dos dez pares; o final foi melhor em tres.
Prioridade da comparacao: completar, colocacao (ou progresso se incompleto),
depois quantidade de passos. Sao dez sementes sobre o mesmo save, nao dez pistas
ou estados iniciais independentes. A selecao e uma referencia local para o
proximo experimento; nao e promocao formal a modelo que vence consistentemente.

O nitro adiado produziu 2º em uma corrida deterministica, contra 4º do uso
original. Entretanto, no conjunto probabilistico piorou seis dos dez pares.
Por isso **nao foi instalado como regra de pilotagem nem transformado em nova
penalidade**. Os limiares 1500, 3000 e 6000 eram velocidades RAM experimentais,
nao RPM, km/h ou deteccao do GO. O teste retirava somente A antes da primeira
carga; mantinha acelerador e comando de marcha. Nenhum desses testes treinou.

Na corrida deterministica original, pedidos de nitro ja apareciam no passo 1,
mas o jogo conservava tres cargas e turbo inativo ate o passo 53. No passo 54,
a carga caiu para duas e a velocidade passou de zero para 175. Portanto,
"velocidade zero antes da ativacao" nao prova desperdicio: neste caso o consumo
coincidiu com o inicio do ganho de velocidade. Isso nao identifica sozinho o GO.
Sequencia: [nitro_launch_evidence.json](../runs/analysis/manual_next_step_20260928/nitro_launch_evidence.json).

Evidencias completas: [comparacao consolidada](../runs/analysis/manual_next_step_20260928/comparison_summary.json),
[corridas originais](../runs/analysis/manual_next_step_20260928/comparison/results.json),
[validacao do nitro](../runs/analysis/manual_next_step_20260928/nitro_validation/results.json).

## Alteracao aplicada

Novo perfil `config/game_profile_manual_refine.ini`: igual ao manual original
nos contratos de observacao, acoes, recompensa, sensores, carro azul e save 2;
somente `ppo.learning_rate` muda de 0.0003 para **0.0001**. O nome descritivo do
perfil tambem muda. O perfil manual original continua disponivel e intacto.

O argumento `--refine-from` importa o checkpoint conservando pesos do ator e do
critico, momentos do Adam e contador. Atualiza a taxa nos grupos do otimizador e
no schedule. Comeca um rollout e episodio novos. **Nao e treino do zero, nem
mudanca na recompensa do turbo ou do cambio.** A taxa menor e uma hipotese de
refinamento para avaliar; nao ha garantia de que resolva a regressao.

A excecao de contrato permite estritamente reduzir learning_rate no contrato
manual conhecido. Mudancas em gamma, reward, acoes, sensores, frequencia, save
ou observacao continuam recusadas. `--resume` normal continua exigindo contrato
identico. Nao foi criada conversao silenciosa para modelos antigos.

O benchmark permite comparar o checkpoint de origem no ambiente de refinamento
somente com a opcao explicita `allow_learning_rate_difference` no plano. Isso
autoriza inferencia com os mesmos sensores/acoes/recompensa; nao autoriza
retomada comum incompatível.

## Testes e preflight

- 258 testes offline passaram em 37,051 segundos. Incluem preservacao dos pesos,
  predicoes, momentos Adam e contador ao reduzir a taxa. O teste PPO usa um
  ambiente simulado e nao e prova de pilotagem.
- Apos a correcao da leitura sentinela no avaliador e no modo somente jogar,
  **260 testes offline passaram**. O caso invalido seguido de uma corrida valida
  foi executado no BizHawk real; a avaliacao saiu com o primeiro caso sem
  posicao e o segundo concluido em 4º.
- Preflight manual base **real aprovado**, 13 criterios:
  `runs/preflight/preflight_20260928_191822_971520.json`.
- Preflight de refinamento **real aprovado**, 13 criterios:
  `runs/preflight/preflight_20260928_191944_068653.json`.
- Recibos separados: `latest_manual.json` e `latest_manual_refine.json`.
- Velocidade de exibicao 400% nos lancadores locais desta analise. A referencia
  final reproduziu os mesmos 1.255 passos, todas as acoes e todos os valores
  comparados de frame/velocidade/lateral/volta/rank/nitro/marcha/giro/impactos.
  O repeat continua em quatro frames; nao foram saltados frames do protocolo.

## Piloto controlado e avaliacao final

O piloto solicitou **25.000 passos adicionais**; PPO concluiu 26.624 por blocos,
atingindo o contador 289.803. Houve 19 episodios de treino, 17 chegadas em tres
voltas, nenhuma vitoria e nenhuma recuperacao de telemetria. Esses episodios
usaram uma politica que mudava durante o treino e nao selecionam um modelo.
Origem: `training_candidate_263179_steps.zip` do treino de 27/09.
Execucao: `runs/hermes-ppo_20260928_192047_301988`.

Com pesos congelados no BizHawk real, na mesma pista e savestate:

| Modelo | Corrida deterministica | Chegadas em corridas variadas | Posicao media das chegadas | Impactos medios |
|---|---:|---:|---:|---:|
| Origem 263.179 | 4º, 6 impactos | 9/10 | 8,56 | 6,5 |
| Refinado 289.803 | 7º, 20 impactos | 9/9 validas; 1 invalida | 8,89 | 7,33 |

As nove sementes validas do refinado empataram a comparacao por pares: tres
melhoras, tres pioras e tres empates. A decima semente (5110) nao e corrida
perdida nem chegada: no passo 84, lap passou de 0 para -1, sem resultado, ao
mesmo tempo em que a contagem dos adversarios caiu de 18 para 0. A repeticao
do mesmo teste reproduziu a falha no mesmo passo. O avaliador agora salva o
pacote recusado e marca `invalid_telemetry`, sem inventar volta, posicao ou
recompensa. O treinador ja possuia recuperacao limitada para essa excecao;
o modo `jogar_continuo.py` agora tambem recarrega o save, com limite de tres
tentativas em 10.000 passos e diagnostico salvo. O erro persistente continua
fatal. A causa exata do pulso de RAM ainda nao foi provada.

Os checkpoints intermediarios de 271.371, 279.563 e 287.755 passos ficaram,
respectivamente, em 10º, 8º e 8º na avaliacao deterministica. O candidato
interno de 279.428 ficou em 8º. Nenhum superou o 4º da origem. O refinamento
permanece preservado como experimento, **sem promocao a modelo recomendado**.
A referencia medida continua sendo o checkpoint de 263.179 passos. Nao ha
evidencia para continuar 500.000 passos a partir do refinado.

O refinado acelerou mais nas nove corridas validas, mas isso nao se traduziu
em melhor posicao. Na corrida deterministica fez 567 mudancas de marcha contra
378 da origem, sofreu mais impactos e usou as tres cargas de nitro. O teste
anterior de bloquear inversoes de marcha e o de adiar o primeiro nitro pioraram
outros resultados; nenhum foi instalado. O proximo experimento deve medir
perda de velocidade e escolhas de marcha/nitro em contextos comparaveis antes
de mudar a recompensa e repetir preflight e piloto curto para qualquer novo
contrato. A amostra usa um so save e sementes que variam as acoes, nao o
trafego inicial; nao prova desempenho geral.

Resumo auditavel: [refinement_comparison.json](../runs/analysis/manual_next_step_20260928/refinement_comparison.json).
Saidas completas: [avaliacao](../runs/analysis/manual_next_step_20260928/refinement_evaluation/results.json),
[repeticao da falha](../runs/analysis/manual_next_step_20260928/refined_seed_5110_retry/results.json),
[falha seguida de corrida valida](../runs/analysis/manual_next_step_20260928/invalid_then_valid/results.json),
[checkpoints](../runs/analysis/manual_next_step_20260928/refinement_checkpoints/results.json).
Nao houve aceleracao forcada, bloqueio de marcha ou bloqueio de nitro no piloto.

## Comandos no PowerShell

Os comandos abaixo servem para repetir uma etapa; nao execute outro processo
na porta 55355 enquanto uma execucao estiver em andamento.

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\refinar_manual.ps1 -Modo Preflight
```

Em outro terminal, abrir o emulador:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Abra a ROM, a Lua Console e `lua/Top Gear Manual (USA).lua`; selecione
**config/game_profile_manual_refine.ini** quando o script solicitar o perfil.
O reset carrega o save 2. Esse procedimento nao exige que voce dirija.

Para um novo piloto a partir da origem preservada, apos preflight:

**Esse comando e apenas para um novo experimento controlado; o piloto de
28/09 nao melhorou a referencia e nao recomenda prolongar treino agora.**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\refinar_manual.ps1 -Modo Treinar -Passos 25000
```

Para continuar um modelo que JA pertence ao perfil de refinamento, use
`-Retomar "caminho completo do checkpoint.zip"`; o programa recusa um contrato
diferente. Sem `-Retomar`, esse script parte do candidato de 263.179, conservando
seus pesos. O bypass de scripts vale somente para o processo desse comando.

O lancador automatico usado nesta investigacao esta em
`runs/analysis/manual_next_step_20260928/run_stage.py`. Enquanto o piloto estiver
rodando por esse lancador, este comando solicita encerramento normal e salva:

```powershell
New-Item -ItemType File -Path .\runs\analysis\manual_next_step_20260928\train\STOP -Force
```

Backups dos fontes anteriores: `runs/maintenance/manual_refinement_20260928_161445_211504`.
Modelos, saves, logs e evidencias anteriores foram preservados.
