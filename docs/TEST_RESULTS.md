> 28/09/2026: **258 testes offline passaram em 37,051 s**, incluindo preservacao de pesos/predicoes/Adam/contador na reducao de learning_rate e isolamento do comando de nitro nos diagnosticos. Log: `runs/analysis/manual_next_step_20260928/tests_refinement.log`. **Preflights reais aprovados**: `preflight_20260928_191822_971520.json` (manual base) e `preflight_20260928_191944_068653.json` (refinamento), 13 criterios cada. Comparacoes reais sem aprendizado e limites em [REFINAMENTO_MANUAL_20260928.md](REFINAMENTO_MANUAL_20260928.md).

> 27/09/2026: **PREFLIGHT OK no BizHawk real**, azul/manual/save 2. Os 13 criterios passaram, incluindo R/L, liberacao/limites e sinal bruto de conta-giro variavel. Recibo: `runs/preflight/preflight_20260927_151815_470372.json`. Savestates conferidos por SHA-256 e preservados. Treino manual novo de 500000 passos iniciado em `hermes-ppo_20260927_152129_971034`; isso ainda nao demonstra aprendizado ou vantagem sobre o automatico.

> Verificacao de 27/09/2026: **250 testes automatizados passaram** na .venv da v3.0 (51,625 s). Inclui 11 testes da integracao manual, as 30 combinacoes de botoes no Lua simulado, contrato/recusa de modelo antigo, 63 features, recompensa sem lucro por ciclos de velocidade e rejeicao de troca ausente no preflight simulado. Evidencia: `runs/analysis/manual_ppo_20260927_151023_954728/tests.txt` e `verification.json`. **Nao houve validacao nova no BizHawk real nem treinamento manual nesta verificacao.**

> 16/09/2026: perfil manual separado para azul/save 2, 63 features, 30 acoes, ponte 6 e shaping potencial de velocidade. Automatico e modelos antigos preservados. Novo preflight real pendente. [Implementacao e comandos](TREINO_MANUAL_PPO.md).

> Atualização de 15/09/2026 após regressão: perfil ativo **road_v5_race / recompensa 7**. Removidos os incentivos experimentais que favoreciam adiar turbo; sensor e observação de 61 entradas preservados. **207 testes offline passaram; preflight real e comparação sem aprendizado pendentes.** [Análise do vídeo, correção e próximos comandos](REGRESSAO_RITMO_TURBO_20260915.md). As instruções anteriores de treino longo são históricas e não são o próximo passo.

> Atualizacao de 15/09/2026: perfil ativo **road_v4_driving / recompensa 6**, para treino do zero. Custo contextual para soltar acelerador e novo criterio de uso util/reserva de turbo. **202 testes offline passaram; novo preflight real pendente por mudanca de contrato.** [Mudancas, evidencias e comando de 500 mil passos](TREINO_DO_ZERO_RITMO_TURBO.md). Avisos anteriores abaixo sao historicos.

> Atualizacao operacional de 14/09/2026: navegacao inspirada no piloto nativo P2 integrada; **61 features/schema 10, detector 3, ponte 5**. Identidade P2 por offsets e corredor com espacos livres. **Novo preflight real pendente**, antes de treino. Modelos de 47 entradas exigem migracao explicita do ator. [Implementacao, evidencias e comandos](NAVEGACAO_NATIVA.md). Avisos e contagens anteriores abaixo sao historicos.

> Revisão de 13/09/2026: replay real mostrou mudança do resultado após sua publicação. A ROM contém corte de aceleração com 10 finalistas; correspondência no episódio ainda depende de captura. **Próximo passo: diagnóstico nativo automático, não treino longo.** [Evidências e comando](ENCERRAMENTO_NATIVO.md). Instruções de treino e interpretações de término anteriores abaixo são históricas.

> Atualização do turbo: perfil ativo **road_v3_turbo / recompensa 5**, custo por carga real e desperdício fora da pista. Ator road_v2 reaproveitado somente por inicialização explícita; retomada comum incompatível é recusada. **153 testes offline passaram**; diagnóstico de término e novo preflight real pendentes. [Mudanças, evidências e comandos](TURBO_E_ENCERRAMENTO.md). Avisos anteriores abaixo são históricos.

> Atualizacao de 30/09/2026: piloto azul/manual refinado e avaliacao real concluidos. Modelo de 263.179 passos continua a referencia; no refinado, uma transicao lap 0→-1 foi reproduzida e salva sem contabilizar corrida. O benchmark registra o caso invalido e passa ao seguinte apos reset validado; o modo continuo faz isso com limite de tres recuperacoes em 10.000 passos. [Resultados completos](REFINAMENTO_MANUAL_20260928.md). Notas historicas abaixo nao indicam preflight pendente para este perfil.

> Atualização de 12/09/2026: recuperação limitada da regressão de lap, diagnósticos completos e médias de 100 episódios no TensorBoard. **143 testes offline passaram** na .venv Windows/Python 3.11.9; novo preflight real pendente após alteração do ambiente. Contrato preservado: 47 features/schema 9, detector 2, ponte 4. [Análise do treino e comandos de retomada](REVISAO_TREINO_369308.md). Os avisos anteriores abaixo são históricos.

> Revisao atual:47features/schema9,detector2,ponte4. Corrigida associacao entre carro e risco.136 testes offline passaram; repetir preflight real apos esta correcao. [Evidencias e procedimento](REVISAO_DETECTOR_20260912.md).

> Versao operacional atual: detector integrado experimental,47features/schema8,ponte4.134 testes offline passaram; novo preflight real pendente. Veja [contrato e comandos](INTEGRACAO_DETECTOR.md). Instrucoes anteriores abaixo sao historico e nao autorizam retomar modelos de26features.

> Atualizacao local 11/09/2026: suporte experimental a save na contagem regressiva, observacao schema 7 (26 features), recompensa v4 e reset sem avancar frames. Ver [largada e proximo teste](LARGADA_CONTAGEM.md). 116 testes offline passaram; novo preflight real pendente. Historico abaixo preservado.

# Resultados de validação da v3.0

Revisão iniciada em 2026-09-09; conferência da distribuição concluída em 2026-09-10. Resultados locais, separados da execução real no emulador.

## 1. Suite automatizada

Comando executado na cópia de trabalho:

```text
audit_v3/test_env/bin/python -m unittest discover -s TCC-TopGear-RL_v3.0/tests -v
```

Resultado: **104 testes, 3,758 segundos, OK, nenhuma falha ou teste ignorado**. A saída integral está em `tests_unittest.log`.

Cobertura executada:

- Leitura de configuração, ROM/perfil, tipos e limites das observações, aliases de término, superfície desconhecida, turbo e curva.
- Recompensa de chegada válida e encerramento incompleto; colisões; retomada de progresso/rank; ciclos e replay das trajetórias reais disponíveis.
- Sockets TCP locais com pares simulados: framing fragmentado/agregado, tamanho inválido, dados corrompidos, UTF-8, timeout total, ACK/episódio/frame incorretos, erro Lua e proibição de repetir ação incerta.
- Script Lua principal executado em Lua 5.4 por Lupa, com APIs BizHawk simuladas: reset, quatro frames, botões, turbo, impactos por frame, erro de slot, sequência/episódio inválidos e encerramento.
- Sintaxe dos scripts Lua incluídos. Isso não verifica a existência das APIs na instalação Windows do usuário.
- PPO/SB3 real em CPU, sobre transições sintéticas: 64 decisões com parâmetros reduzidos para teste, alteração dos pesos, múltiplos resets automáticos, checkpoint, carga e mais 16 decisões de retomada. Esse teste não mede pilotagem nem usa a configuração de coleta longa para alegar aprendizado.
- Registro do estado terminal antes do auto-reset; callback real e checkpoint após atualização; rejeição de modelo antigo sem contrato, contrato divergente e arquivo adulterado.
- Preflight simulado, preservação do relatório parcial de falha, invalidação de aprovação anterior e alteração do save/código crítico.
- Promoção que recusa repetições do mesmo estado inicial como 20 situações distintas.
- Diagnóstico de contexto: dump truncado, offsets e ordem dos frames; candidato de memória não é promovido automaticamente a temporizador validado.

## 2. Ambiente de teste e dependências

Linux x86-64, Python **3.12.14**, NumPy 2.0.2, Gymnasium 1.3.0, Stable-Baselines3 2.9.0, PyTorch 2.8.0+cpu, TensorBoard 2.20.0, Lupa 2.6 / Lua 5.4. Versões completas: `TEST_ENVIRONMENT.json`.

O ambiente local reutiliza bibliotecas já disponíveis no runtime de auditoria. `pip check` retornou **No broken requirements found**. Os módulos do projeto foram importados e executados nesse ambiente. A instalação nova do usuário é especificada para **Windows x64 / Python 3.11**, com `.venv` dentro da v3.

**Não foi concluída uma instalação limpa Windows/Python 3.11 aqui.** A tentativa adicional de instalação/resolução do zero foi limitada pela rede e por wheels ausentes no cache local. Não se declara esse procedimento aprovado apenas porque o ambiente existente funcionou. No computador do usuário, executar instalação, `pip check`, `verify_install.py --manifest` e a suite conforme `README.md`.

## 3. Evidências reais reprocessadas

`audit_evidence.py` recalcula os arquivos efetivamente incluídos em `archive/evidence`, sem modificar as entradas. Resultado congelado: `EVIDENCE_RESULTS.json`.

- ROM original: 524.288 bytes; SHA-1 `F686806C676A4B087A3627BABBE3555D3704E3B1`.
- Superfície: 3.600 frames contínuos, estados 0/1/2; 36 de 36 rótulos discretos coerentes nas duas coletas de offtrack. Não é medição da largura geométrica da pista.
- Turbo: dois ramos de 521 frames; o ramo X+A ativou turbo e consumiu uma carga. Isso não é teste automatizado de todas as condições de uso dos três nitros.
- Curva: índice da tabela corroborado por bytes/disassembly da ROM, 704 blocos aplicáveis a Las Vegas, 12 de 12 rótulos disponíveis de reta/esquerda coerentes. Não valida curvas para a direita em outras pistas.
- Vitória manual: 5.400 frames, transição lap 2→3 e final_rank −1→0 no frame 8730; velocidade máxima bruta 13677. Não há coluna de superfície nativa suficiente para calcular honestamente o reward completo proposto dessa corrida.
- Avaliação antiga: 304/304 ações BRAKE do modelo e 1.303 ações de aceleração fixa; retornos legados reconciliados, comparação de três perfis e três descontos, sensibilidade de 12 pares de penalidades. Isso não é um treino contrafactual novo.

Os primeiros CSVs de adversários citados na conversa não estão todos disponíveis como arquivos nesta sessão; documentos/relatos preservados não foram tratados como reexecução desses CSVs. O mapa de memória identifica essa diferença de evidência.

## 4. Limites da aprovação

Nenhuma instância real do BizHawk Windows foi executada nesta revisão. Não há recibo `preflight passed` fornecido artificialmente no pacote. Não houve treinamento longo ou demonstração de vitória da IA v3.

O teste real inicial está em `python/preflight_live.py`; seu relatório deve ser produzido no computador do usuário. Percepção física de carros em outra volta/atrás, objetos específicos, cronômetro e origem do impacto continuam pendentes. Ver `VALIDACAO_AO_VIVO.md` e `MAPA_MEMORIA.md`.

## 5. Integridade e distribuição

O inventário anterior às alterações conserva hashes dos 295 arquivos de código/dados relevantes nas árvores originais. A revisão ocorre somente na pasta nova. O pacote contém ROM, evidências e modelos históricos preservados em áreas separadas; não contém `.venv`, caches ou treino sintético apresentado como modelo real.

`MANIFEST.sha256` identifica cada arquivo distribuído, exceto o próprio manifesto. O ZIP final tem uma única pasta raiz, `TCC-TopGear-RL_v3.0`.

A distribuição foi extraída em uma pasta independente e testada novamente: **104 testes em 3,515 segundos, OK, sem falhas ou testes ignorados**. `tests_standalone.log` registra essa execução. `verify_install.py --manifest` aprovou imports, configuração e todos os hashes da distribuição extraída. O interpretador de teste continuou sendo o ambiente Linux descrito acima, não uma `.venv` Windows artificialmente incluída.

Nove comandos CLI responderam a `--help` com código zero, executados a partir de outro diretório: treino, avaliação, smoke, conexão, preflight, replay, auditoria, análise de contexto e promoção. Resultado: `cli_standalone.json`. Não foi preciso importar arquivos de nenhuma versão v2.

A análise de sintaxe Python aprovou **43 arquivos** de código/testes; os **12 scripts Lua** foram analisados pelo runtime Lua nos testes. Não foram encontrados caminhos absolutos da máquina de auditoria ou das pastas v2 no código operacional/configuração/scripts.

Os **295 arquivos originais inventariados mantiveram seus hashes**. Os oito ZIPs históricos incorporados passaram pela verificação CRC e pela busca de ambientes/caches indevidos. O ZIP final foi conferido quanto a CRC, nomes duplicados, caminho fora da raiz, arquivos excluídos e correspondência de todos os hashes do manifesto. Só relatórios/logs de verificação foram acrescentados após o teste da cópia extraída; o código operacional não mudou.

Verificação desta revisão: **160 testes offline passaram em 11,735 segundos**, sem falhas ou testes ignorados, na .venv Windows/Python 3.11.9 da v3.0. Registro: `runs/maintenance/native_finish_20260913_112516/test_results.json`. Captura nativa no BizHawk real pendente.

## Verificacao da integracao em 14/09/2026

192 testes automatizados passaram na .venv operacional (Python 3.11.9); baseline anterior: 161. Incluem pacote Lua, reset de historico, P2 com IDs brutos iguais, offsets variaveis, mascaras, corredor ocupado, aproximacao fora do raio publicado, coordenadas absolutas, PPO sintetico, migracao de pesos e recusa de contratos invalidos. Nao sao validacao nova no BizHawk.

Releitura final: `runs/analysis/native_navigation/snapshot_audit_20260914_193942_194603.json` (83/83 identidades e corredores coerentes). Migracao final: `runs/analysis/native_navigation/migration_audit_20260914_193945_003914.json` (cinco verificacoes passaram, modelo original preservado). Novo PREFLIGHT real pendente.
