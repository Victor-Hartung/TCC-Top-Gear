> Atualizacao operacional de 14/09/2026: navegacao inspirada no piloto nativo P2 integrada; **61 features/schema 10, detector 3, ponte 5**. Identidade P2 por offsets e corredor com espacos livres. **Novo preflight real pendente**, antes de treino. Modelos de 47 entradas exigem migracao explicita do ator. [Implementacao, evidencias e comandos](NAVEGACAO_NATIVA.md). Avisos e contagens anteriores abaixo sao historicos.

> Comparação real concluída em 13/09/2026: episódio 249 reproduziu a vitória (lap=3, resultado=0, primeiro na lista de chegada), enquanto episódio 270 confirmou o corte com 10 finalistas antes da chegada de P1. A regra atual separou corretamente esses dois casos. Não foi adicionado tempo artificial. **Próximo passo: preflight_live.py com o Lua principal para os arquivos atuais**, antes do piloto do novo objetivo de turbo. Os candidatos nativos adicionais continuam restritos ao diagnóstico. [Evidências](ENCERRAMENTO_NATIVO.md). Avisos de testes pendentes abaixo são históricos.

> Evidência real de 13/09/2026: `0x1EB0` chegou a 10 antes da publicação de resultado incompleto no episódio 270; o corte de aceleração correspondente também foi identificado na ROM. Validado nesse episódio, ainda fora da observação/recompensa. Chegada normal pendente de comparação. [Captura e limites](ENCERRAMENTO_NATIVO.md).

> Revisão de 13/09/2026: replay real mostrou mudança do resultado após sua publicação. A ROM contém corte de aceleração com 10 finalistas; correspondência no episódio ainda depende de captura. **Próximo passo: diagnóstico nativo automático, não treino longo.** [Evidências e comando](ENCERRAMENTO_NATIVO.md). Instruções de treino e interpretações de término anteriores abaixo são históricas.

> Revisao atual:47features/schema9,detector2,ponte4. Corrigida associacao entre carro e risco.136 testes offline passaram; repetir preflight real apos esta correcao. [Evidencias e procedimento](REVISAO_DETECTOR_20260912.md).

> Versao operacional atual: detector integrado experimental,47features/schema8,ponte4.134 testes offline passaram; novo preflight real pendente. Veja [contrato e comandos](INTEGRACAO_DETECTOR.md). Instrucoes anteriores abaixo sao historico e nao autorizam retomar modelos de26features.

> Atualizacao local 11/09/2026: suporte experimental a save na contagem regressiva, observacao schema 7 (26 features), recompensa v4 e reset sem avancar frames. Ver [largada e proximo teste](LARGADA_CONTAGEM.md). 116 testes offline passaram; novo preflight real pendente. Historico abaixo preservado.

# Mapa de memória e limites de evidência

ROM única: **F686806C676A4B087A3627BABBE3555D3704E3B1**. Domínio das linhas abaixo: **WRAM**, 131.072 bytes. Endereços são offsets no domínio, não offsets do arquivo da ROM. Para palavras de dois bytes, a ordem é **little-endian**. `s16`/`s8` significam inteiros com sinal em complemento de dois; `u16`/`u8`, sem sinal. Não escrever nestas memórias durante treino.

**Validado (escopo)** significa compatível com os registros e observações recebidos para Las Vegas e este layout, não provado para todos os carros, modalidades e pistas. **Candidato** significa endereço ou interpretação ainda parcial. **Desconhecido** significa que não há endereço operacional demonstrado. Testes com memória artificial não promovem um candidato a validado.

Evidências reproduzíveis: `EVIDENCE_RESULTS.json`, os arquivos originais em `archive/evidence`, os relatos transcritos na conversa e os relatórios anteriores em `docs/history`. As coletas antigas de adversários de 900 frames e de memória de 667 amostras não estão entre os anexos CSV atualmente acessíveis: suas conclusões permanecem evidência histórica relatada, não uma revalidação independente feita nesta entrega.

## Jogador e corrida

| Endereço | Leitura / faixa relevante | Interpretação e uso | Status e evidência / limitação |
|---|---|---|---|
| `0x1E5A` | `read_s16_le`, −32768..32767 | Movimento longitudinal P1; `speed`, observação e diagnóstico de parada | Validado como movimento; acelerador/freio e recuo de impacto observados. CSV da vitória atingiu 13677. Não chamar unidade de km/h. Escala neural 16384, não 6400. |
| `0x1E8A` | `read_s16_le` | Coordenada lateral P1; observação, deltas de adversários | Validado por comandos esquerda/direita e amostras de borda. Negativo/esquerda, positivo/direita no layout. Não é pixel de tela nem largura constante. |
| `0x1ED7` | `read_u16_le`, normalmente 0..22527 | Progresso P1 dentro da volta; deltas e distância longitudinal | Validado pelas voltas completas e wrap da vitória. Houve hipótese antiga incorreta começando em `0x1ED8`. |
| `0x1ED7` | `read_u8`, 0..255 | Campo legado `progress_fraction` | É o byte baixo da mesma palavra acima. Redundante; não constitui outra coordenada/fração independente. Não entra na rede nem no reward. Mantido no protocolo legado para auditoria. |
| `0x0046` | `read_u16_le`, reduzido módulo comprimento | Acumulador usado para consultar curva atual/futura | ROM: `LDA $46`, quatro LSR, máscara `FFFE`; tabela manual e mapa coerentes. Não assumir identidade exata com progresso P1 em todo frame. |
| `0x1E76` | `read_s16_le`, −1, 0..3 | Volta P1, base zero durante corrida | Validado: −1 antes da largada; 2→3 ao completar três voltas. Um transiente 0→1→0 foi relatado anteriormente; reward usa delta modular de progresso para não premiar o pulso. |
| `0x1E7A` | `read_u16_le`, saneado para −1 ou 0..19 | Classificação ao vivo: 0=1º, 19=20º | Validado por vitória e avaliações. Não confundir 19 com 19º. Pode ser sentinela nos menus. |
| `0x1F00` | `read_s16_le`, −1 ou 0..19 | Resultado publicado / corrida encerrada | **Também muda por tempo esgotado.** Vitória em frame 8730: −1→0 junto de lap 2→3. Timeout relatado: lap=0, final_rank=19. Sozinho não comprova chegada. |
| `0x1E56` | `read_u16_le`, 3 no perfil | Total de voltas | Validado neste cenário, não em todas as modalidades. |
| `0x0200` | `read_u16_le`, 22528 no perfil | Comprimento da volta para módulo | Validado em séries e mapa; não representa metros. V3 recusa pista com comprimento diferente e também confere a assinatura da curva. |
| `0x1EF5` | byte baixo, bit `0x80`; rotina legada lê word e mascara o mesmo bit | Pulso/nível de impacto; contador por bordas em cada frame | Contatos e obstáculos foram relatados; seis bordas no CSV da vitória. Causa, direção, responsável e ID do outro carro **não estão comprovados**. Não é detector preventivo. |
| `0x0727` | `read_u8`: 0/1/2 | Fora esquerda / asfalto / fora direita | 36/36 amostras rotuladas; 3600 frames com 487/2665/448 ocorrências. Usuário confirmou overlay. `255` foi observado após cacto: classificado conservadoramente fora, com `surface_unknown=1`; lado por histórico é inferência. |
| `0x0A67` | `read_u8` | Cópia/buffer relacionado à superfície | **Não usar como sinônimo instantâneo** de 0727: 51 divergências entre esses dois endereços na coleta. Relatório antigo contou 131 divergências contra conjunto maior de buffers. Não são a mesma comparação. |
| `0x1E62` | `read_u16_le`, 0..65535 | Quantidade bruta associada a combustível | Papel sustentado por ROM e decréscimo observado; entra normalizado como bruto. Unidade do HUD, zero e evento de falta de combustível não foram validados isoladamente. Sem término inventado por esse campo. |
| `0x1E6C` | `read_u16_le` | Cargas/status do turbo | Validado no teste controlado: ramo X preserva 3; X+A ativa bit15 nos frames relativos 162..481 e termina em 2. Cargas disponíveis = low2 menos 1 durante ativação, se low2>0; demais bits mudam durante a animação. O relato de uso das três cargas não substitui uma série causal individual de cada carga. |
| `0x1E72` | `read_u16_le` | Índice de marcha | Na coleta manual do carro vermelho em 15/09/2026, oito PNGs sincronizados confirmam bruto 0..4 = GEAR 1..5; R sobe e L reduz. Evidência `cambio_manual_20260915_192807_26181_0_hud.tsv` e revisão em `runs/analysis/transmission_20260915/`. A observação PPO continua bruto/8; perfil operacional automático, slot 1. Isso não valida ponto ideal de troca nem vantagem do manual. |

## Tabela dos competidores

Base `0x0212`, **20 registros × 18 bytes**, último byte `0x0379`. Registros mudam de posição: usar ID, nunca “registro 3 é sempre carro 3”. A ponte filtra **18 IAs, IDs 2..19**; dois registros restantes pertencem aos jogadores. O padrão especial/duplicado de ID zero na coleta antiga não deve virar um adversário artificial.

Essa identificação estrutural não demonstra que os18IDs representem todos os carros fisicamente visíveis em qualquer modo. A participação do segundo registro de jogador/ID0 no modo de uma pessoa deve ser conferida visualmente. O diagnóstico novo inclui os20registros, inclusive os que a observação exclui; não inventa o ID ausente1 nem presume uma máscara de atividade.

| Offset no registro | Tipo/endian | Uso e estado |
|---|---|---|
| `+0` | u8; ID = `byte & 0x1F` | IDs 2..19: sustentados pela ROM e coletas históricas. Bits altos permanecem desconhecidos. V3 detecta IDs repetidos/incompletos durante corrida ativa. |
| `+2` | s16 LE | Lateral na mesma escala de P1. Base de `nearest_lateral` e faixas relativas. Evidência histórica de coincidência do registro P1 e globais em 900/900 frames. |
| `+4` | s16 LE candidato | Movimento/controle lateral. Não entra na observação. Requer série temporal controlada. |
| `+6` | u8 candidato | Acumulador subfracionário. Não confundir com início da palavra comparável ao comprimento. |
| `+7` | u16 LE | Progresso do competidor dentro da volta. Leitura ativa da ponte; evidência histórica e consistência no diagnóstico de pista. |
| `+9` | u8 bruto → s8 → menos 1 | Volta do registro começa em 1 quando P1 global começa em 0. Equivalência relatada em 900 frames. Extremos, registros inativos e repetição além das voltas cobertas precisam de validação. |
| `+10` | u16 LE | `nearest_motion_raw`: movimento longitudinal candidato. Não é velocidade física validada; não entra na rede. A rede recebe derivada temporal da distância para o mesmo ID. |
| `+12` | s16 LE candidato | Delta/aceleração possível. Não utilizado. |
| `+14` | u16 LE candidato | Contador de atualização possível. Não é cronômetro validado da corrida. |
| `+16` | u16 LE candidato | Flags/estado. Coletado em `diagnostico_contexto`; sem significado de bits atribuído. |

`0x0204`/`0x0206`: words candidatos a offsets dinâmicos dos registros P1/P2. Não utilizados no ambiente. `0x1E5C`, `0x1E8C`, `0x1EDA`, `0x1E78`, `0x1E7C`, `0x1F02`, `0x1EF6`: equivalentes P2 sugeridos pelo código, sem validação operacional nesta v3. `0x1EB0` e `0x1F12...`: candidatos históricos de contagem/ordem de finalistas; tamanho total, sinal e uso não confirmados. Não promover por plausibilidade.

## Curva e geometria

| Endereço/estrutura | Leitura | Uso/evidência |
|---|---|---|
| `0x4C00 + 2*floor(p/32)` | byte baixo **s8** de entrada de dois bytes | Curva, onde `p=(WRAM[0046]+lookahead)%22528`. Offsets de antecipação: 0, 512, 1024, 2048. Evidência estática em CPU LoROM `00:8592..85BA`, `ROM_INDEX_EVIDENCE.txt`; 12/12 rótulos reta/esquerda no mapa. |
| 704 entradas válidas | faixa observada 0..32 | 392 zeros, 312 positivas. Adler32 dos bytes baixos **1669863105**. Não usar as 1408 linhas como 1408 entradas: a coleta antiga duplicou o alcance por erro de `/16`. |
| `0x4000` | words LE candidatos | Inclinação/física longitudinal, não curva lateral comprovada. Mantido apenas em diagnósticos históricos. |
| `0x5800` | words LE candidatos | Tipo/geometria local da pista. Sem decodificação confiável de obstáculos. |
| `0x7002` | words/bytes candidatos | Limites usados por rotinas de competidores; não substituem superfície nativa. `road_inside_candidate` antigo não é offtrack validado. |

Regiões de curva não zero: progresso **4128..8159**, **14368..17375**, **17440..18399**, **20512..22495**. São intervalos da tabela, não necessariamente quatro curvas visualmente separadas. Em Las Vegas, os rótulos disponíveis associam coeficiente positivo à curva para esquerda. Curva para direita e coeficiente negativo não foram validados nesta pista.

## Informações ainda sem endereço validado

| Informação | Situação / descoberta necessária |
|---|---|
| Cronômetro/tempo restante | Desconhecido. Procurar u8/u16, BCD, contador de frames e recargas ao cruzar voltas. Não adotar simplesmente um byte decrescente. |
| Flag de corrida ativa | Desconhecido. Hoje há verificação de conjunto plausível + save validado; isso não é um endereço nativo de estado. |
| Causa exata do encerramento | Desconhecida. `race_ended_incomplete` é correto sem afirmar que todo caso foi timeout. |
| Obstáculos, placas/cactos | Não há tabela de obstáculos validada nem observação preventiva. Investigar entidades e, se necessário, VRAM/OAM/rotinas de desenho; snapshots atuais cobrem WRAM. Sprite visível sozinho não fornece distância de colisão no mundo. |
| ID e origem da colisão | Desconhecidos. Correlacionar evento de impacto com registros próximos, velocidades antes/depois e rótulo visual. O bit genérico não identifica culpa. |
| Carro atrás ou lado a lado em outra volta | Coordenadas conhecidas permitem **candidato calculado** por módulo; falta validação física/visual sistemática. Sem novo endereço inventado. |
| Velocidade relativa de cada carro | Derivada possível dos mesmos IDs ao longo do tempo; validar wrap, reordenação e transientes. Escala de `record+10` ainda não equivale comprovadamente à velocidade de P1. |

O diagnóstico novo registra WRAM completa periodicamente, todos os competidores em cada frame e marcações manuais. Veja `VALIDACAO_AO_VIVO.md`. Nenhuma análise de correlação modifica automaticamente o perfil.


## Extensao manual experimental — 16/09/2026

0x1E72 (u16) e o indice de marcha 0..4, confirmado no HUD 1..5 nas coletas
manuais. 0x1E5E (s16) e a entrada do desenho da barra de conta-giro pela rotina
ROM 00:D3CF; nao esta calibrado em RPM fisicos nem define o ponto ideal de troca.
Apenas o perfil manual inclui esse valor adicional na observacao. A ponte confere
0x1EE8=48 (azul observado), 0x1F7A=16 (R) e 0x1F7C=32 (L) depois de reset/step.
Esses dois ultimos sao mascaras de botoes configurados, nao flags independentes.
A nova integracao TCP ainda requer preflight real. Fontes e limites em
[TREINO_MANUAL_PPO.md](TREINO_MANUAL_PPO.md).
