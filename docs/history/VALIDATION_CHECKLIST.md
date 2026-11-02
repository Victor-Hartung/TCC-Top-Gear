# Checklist de validação no BizHawk

Não marque uma flag como `true` apenas porque o script executou. O critério é a
correspondência repetível entre memória, HUD, imagem e ação controlada.

## 0. Preparação

- [x] Usar BizHawk 2.11.1 x64 e a ROM Top Gear (USA) com SHA-1
  `f686806c676a4b087a3627babbe3555d3704e3b1`.
- [x] Abrir uma corrida reproduzível e criar o savestate inicial no slot 1.
- [ ] Registrar pista, carro, câmbio, layout de controles e core SNES usados.
- [ ] Manter somente um script desta pasta ativo por vez.
- [ ] Não pressionar controles manualmente durante teste da ponte ou treino.

## 1. Execução e endereços globais

Executar `lua/diagnostico_execucao.lua`.

- [x] `rom_ok=1` e hash exatamente igual ao esperado.
- [x] domínio atual `WRAM`; tamanho compatível e todos os endereços dentro dele.
- [x] `0x1E5A` varia coerentemente com aceleração, freio, parada e colisão.
- [x] `0x1E8A` muda com esquerda/direita; medir centro e bordas nos dois sentidos.
- [x] o fixed-point `u16 LE` em `0x1ED7` avança com o carro e faz wrap coerente na volta.
- [x] `0x1E76` acompanha pré-largada e mudança de volta; há um transiente de um frame já filtrado no reward.
- [x] `0x1E7A` coincide com a posição viva no HUD e confirma `0 = primeiro`.
- [x] `0x1F00` fica negativo antes da chegada e recebeu `0` exatamente ao terminar em primeiro.
- [x] `0x1EF5 & 0x0080` reage a contatos carro-carro; outros tipos de impacto ainda exigem distinção.
- [x] `0x1E56` permaneceu em `3` e a chegada ocorreu na transição de volta `2 → 3`.
- [ ] combustível e marcha têm escala/codificação anotadas.
- [x] nitro tem contagem disponível e estado ativo decodificados em `0x1E6C`.
- [x] `0x0727` representa superfície: `0=esquerda`, `1=pista`, `2=direita`.

O perfil de Las Vegas foi marcado como `profile_validated=true` após validar os
campos essenciais de controle, corrida, adversários, superfície, curva e ponte.
Combustível e a escala exata da marcha continuam identificados como limitações.

## 2. Controles e comparações causais

Executar `lua/diagnostico_memoria.lua`. O script parte do mesmo savestate em cada
ramo e compara durações iguais.

- [x] `accelerate_80` supera `neutral_80` em velocidade/progresso.
- [x] `brake_after_accelerate` reduz mais que `coast_after_accelerate`.
- [x] ramo esquerdo difere do ramo neutro sempre no mesmo sentido lateral.
- [x] ramo direito difere no sentido oposto.
- [ ] confirmar que o layout selecionado no jogo não altera os botões lógicos.
- [x] tecla física `X` mapeada para botão SNES `A`, confirmada na configuração do BizHawk.
- [x] executar `diagnostico_turbo.lua` e confirmar que somente o ramo SNES `A` altera `0x1E6C`.

O teste confirmou o retorno `0xFF03 -> 0x0002`; por isso,
`controls_validated=true` e `enable_turbo=true`. O espaço atual possui 10 ações.

## 3. Adversários

Executar `lua/diagnostico_adversarios.lua` enquanto grava a tela ou anota cenas
com carro perto/longe, à esquerda/direita, ultrapassagem e colisão.

- [x] aparecem 20 registros e IDs coerentes, sem assumir que índice é identidade.
- [x] registros de P1/P2 foram identificados; IDs `2..19` correspondem às IAs.
- [ ] `record+2` acompanha a lateral visual de cada carro.
- [x] a posição em `record+7`, o acumulador iniciado em `record+6` e a volta baseada em 1 em `record+9` ordenam os carros na corrida observada.
- [x] o menor `delta_forward > 0` antecipou seis contatos confirmados com carros.
- [x] o sinal de `delta_lateral` e o limiar de contato foram coerentes na captura.
- [x] `same_lane_half_width=4096`, derivado da comparação `0x0800` após divisão lateral por dois e confirmado nos seis contatos.
- [ ] medir um alcance que dê tempo de desviar sem incluir a pista inteira.
- [ ] decodificar `record+16`/bits de `record+0` para ativo, invisível ou finalizado.
- [ ] testar largada, carros já finalizados e posições vazias para excluir fantasmas.
- [x] colisões sucessivas produzem novas bordas; 15 bordas e 41 frames ativos foram observados.

Somente depois marcar `opponent_telemetry_validated=true`.

## 4. Pista e curvas

Executar `lua/diagnostico_pista.lua` por retas e curvas rotuladas.

- [x] exportar `diagnostico_mapa_curvas.csv` e correlacionar o byte baixo de
  `0x4C00` com direção/intensidade visual.
- [ ] decodificar `0x5800` como tipo/limites da pista, se necessário.
- [x] o índice correto é `2*floor(progress/32)`, equivalente a
  `(progress >> 4) & 0xFFFE`, confirmado na ROM e nos 12 rótulos.
- [ ] descobrir centro e limites por segmento, caso não sejam relativos ao carro.
- [x] expor look-ahead em 512, 1024 e 2048 unidades para comparação no treino.
- [ ] repetir em mais de uma pista; não generalizar uma tabela sem evidência.

### Superfície/offtrack

- [x] duas coletas rotuladas separaram pista, esquerda e direita em 36/36 amostras;
- [x] overlay contínuo acompanhou visualmente as duas bordas em 3.600 frames;
- [x] `0x0727` foi integrado; `0x0A67` foi excluído por atraso/divergências;
- [x] Python rejeita valores ou combinações de superfície inconsistentes;
- [x] validar curva atual/futura de Las Vegas antes de marcar
  `curve_telemetry_validated=true` (12/12 rótulos e ponte confirmada).

A observação v5 integra o byte baixo assinado de `0x4C00`. Curvas à direita e
outras pistas ainda devem ser testadas antes de generalizar o sinal.

## 5. Configuração e ponte

- [x] usar o sensor ternário nativo para offtrack, sem inventar `track_half_width`.
- [ ] preencher escalas ainda pendentes somente com valores medidos, não palpites.
- [ ] reiniciar `lua/Top Gear (USA).lua` depois de toda mudança no INI.
- [x] executar a validação principal com reset e passos neutros.
- [x] confirmar `seq == ack`, episódio correto e delta exato de quatro frames.
- [ ] executar os testes unitários e depois `python/smoke_test_env.py --steps 100`.
- [ ] inspecionar observações, reward por componente, colisões e resets.

## 6. Primeiro treino controlado

- [ ] começar com poucas etapas e uma pasta de run nova.
- [ ] verificar TensorBoard, rank, chegadas, colisões e causa de terminação.
- [ ] avaliar deterministicamente com `evaluate_hermes.py`; não escolher modelo só
  pelo reward de treino.
- [ ] manter seed, perfil INI e versão do código anexados a cada resultado do TCC.
