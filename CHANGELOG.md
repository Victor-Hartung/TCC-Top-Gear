> 31/10/2026: criado o cérebro independente Hermes PPO 3 com retomada de ator, crítico, Adam e contador, checkpoints de atualizações completas, TensorBoard e play pelo carregador existente. Usa o contrato PPO atual sem importar nem sobrescrever Hermes PPO, Hermes PPO v2, Apolo ou Ares. Novo preflight real obrigatório antes do treino.

> 30/09/2026: refinamento manual de 26.624 passos terminou e foi avaliado sem treino. Nao superou a origem de 263.179 passos; quatro checkpoints intermediarios tampouco superaram. Anomalia lap 0→-1 reproduzida na semente 5110, com diagnostico preservado; benchmark registra caso invalido e `jogar_continuo.py` o recupera com limite. Nenhuma recompensa de chegada e atribuida ao caso. [Resultado](docs/REFINAMENTO_MANUAL_20260928.md).

> 28/09/2026: benchmark real com sementes registradas, diagnostico de primeira carga de nitro e novo perfil de refinamento manual. `--refine-from` permite apenas reduzir learning_rate; demais diferencas continuam recusadas. Recibos de preflight base/refinamento separados; pesos anteriores preservados. 258 testes e ambos preflights reais aprovados. [Detalhes](docs/REFINAMENTO_MANUAL_20260928.md).

> 27/09/2026: **PREFLIGHT OK no BizHawk real**, azul/manual/save 2. Os 13 criterios passaram, incluindo R/L, liberacao/limites e sinal bruto de conta-giro variavel. Recibo: `runs/preflight/preflight_20260927_151815_470372.json`. Savestates conferidos por SHA-256 e preservados. Treino manual novo de 500000 passos iniciado em `hermes-ppo_20260927_152129_971034`; isso ainda nao demonstra aprendizado ou vantagem sobre o automatico.

> 16/09/2026: perfil manual separado para azul/save 2, 63 features, 30 acoes, ponte 6 e shaping potencial de velocidade. Automatico e modelos antigos preservados. Novo preflight real pendente. [Implementacao e comandos](docs/TREINO_MANUAL_PPO.md).

> Atualização de 15/09/2026 após regressão: perfil ativo **road_v5_race / recompensa 7**. Removidos os incentivos experimentais que favoreciam adiar turbo; sensor e observação de 61 entradas preservados. **207 testes offline passaram; preflight real e comparação sem aprendizado pendentes.** [Análise do vídeo, correção e próximos comandos](docs/REGRESSAO_RITMO_TURBO_20260915.md). As instruções anteriores de treino longo são históricas e não são o próximo passo.

> Atualizacao de 15/09/2026: perfil ativo **road_v4_driving / recompensa 6**, para treino do zero. Custo contextual para soltar acelerador e novo criterio de uso util/reserva de turbo. **202 testes offline passaram; novo preflight real pendente por mudanca de contrato.** [Mudancas, evidencias e comando de 500 mil passos](docs/TREINO_DO_ZERO_RITMO_TURBO.md). Avisos anteriores abaixo sao historicos.

> Atualizacao operacional de 14/09/2026: navegacao inspirada no piloto nativo P2 integrada; **61 features/schema 10, detector 3, ponte 5**. Identidade P2 por offsets e corredor com espacos livres. **Novo preflight real pendente**, antes de treino. Modelos de 47 entradas exigem migracao explicita do ator. [Implementacao, evidencias e comandos](docs/NAVEGACAO_NATIVA.md). Avisos e contagens anteriores abaixo sao historicos.

> Revisão de 13/09/2026: replay real mostrou mudança do resultado após sua publicação. A ROM contém corte de aceleração com 10 finalistas; correspondência no episódio ainda depende de captura. **Próximo passo: diagnóstico nativo automático, não treino longo.** [Evidências e comando](docs/ENCERRAMENTO_NATIVO.md). Instruções de treino e interpretações de término anteriores abaixo são históricas.

> Atualização do turbo: perfil ativo **road_v3_turbo / recompensa 5**, custo por carga real e desperdício fora da pista. Ator road_v2 reaproveitado somente por inicialização explícita; retomada comum incompatível é recusada. **153 testes offline passaram**; diagnóstico de término e novo preflight real pendentes. [Mudanças, evidências e comandos](docs/TURBO_E_ENCERRAMENTO.md). Avisos anteriores abaixo são históricos.

> Atualização de 12/09/2026: recuperação limitada da regressão de lap, diagnósticos completos e médias de 100 episódios no TensorBoard. **143 testes offline passaram** na .venv Windows/Python 3.11.9; novo preflight real pendente após alteração do ambiente. Contrato preservado: 47 features/schema 9, detector 2, ponte 4. [Análise do treino e comandos de retomada](docs/REVISAO_TREINO_369308.md). Os avisos anteriores abaixo são históricos.

> Revisao atual:47features/schema9,detector2,ponte4. Corrigida associacao entre carro e risco.136 testes offline passaram; repetir preflight real apos esta correcao. [Evidencias e procedimento](docs/REVISAO_DETECTOR_20260912.md).

> Versao operacional atual: detector integrado experimental,47features/schema8,ponte4.134 testes offline passaram; novo preflight real pendente. Veja [contrato e comandos](docs/INTEGRACAO_DETECTOR.md). Instrucoes anteriores abaixo sao historico e nao autorizam retomar modelos de26features.

> Atualizacao local 11/09/2026: suporte experimental a save na contagem regressiva, observacao schema 7 (26 features), recompensa v4 e reset sem avancar frames. Ver [largada e proximo teste](docs/LARGADA_CONTAGEM.md). 116 testes offline passaram; novo preflight real pendente. Historico abaixo preservado.

# Changelog

## 3.0.0 — 2026-09-10

Base nova independente, derivada da v2.0.28 com correção de encerramento, avaliação e experimento road_v1 incorporados. Originais preservados em diretórios históricos; nenhuma dependência da `.venv` v2.

- Protocolo TG2 preservado, revisão da ponte3: perfil/ROM/domínio, deadline de mensagem, validação de sequências/inteiros, detecção de save carregado fora de reset e encerramento seguro de sessão incerta.
- Preservado avanço por `unpause`/`yield` e quatro frames; liberação explícita de botões, limite de ação e erros Lua de inicialização propagados quando possível.
- Semântica explícita `race_ended`/`race_completed`, auto-reset testado e corte artificial como truncamento no objetivo novo. Timeout não recebe bônus de chegada.
- Observação6:26features, velocidade assinada/16384, máscara de superfície desconhecida, derivada relativa por frame e máscara de identidade. Modelos de24features não carregam silenciosamente.
- Ações2: índices mantidos, proteção do turbo sem carga/já ativo.
- Reward3 `road_v2` experimental: máximo de progresso elegível, melhor rank, custo de parada/tempo, pesos de impacto/offtrack menores, penalidade de encerramento incompleto. Comparadores legados preservados e replay de dados reais.
- Gamma0,999 proposto para objetivo de chegada; demais parâmetros principais e MLP preservados; guarda target_kl0,03.
- Contratos/hashes de checkpoints, retomada em nova pasta, configuração congelada, logs por passo/episódio e promoção por avaliação independente.
- Preflight causal com cinco ramos e verificação de fingerprint do save no treino.
- Diagnóstico de contexto: WRAM completa, competidores e rótulos; candidatos traseiros/timer não entram automaticamente no treino.
- Saídas de diagnóstico não sobrescrevem coletas anteriores. Scripts e dados antigos permanecem auditáveis.
- Instalação com Python3.11/.venv local, dependências fixadas, testes de Lua/PPO/protocolo e relatório técnico.

**Ainda pendente:** validação da v3 no BizHawk do usuário; novas políticas treinadas; relógio nativo, causa de fim, obstáculos específicos, identificação de impacto e validação física traseira. Nenhuma vitória da IA é anunciada nesta versão.
