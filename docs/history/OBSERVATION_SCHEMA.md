# Esquema da observação v5

O ambiente fornece um vetor `float32` com 24 posições. Os campos marcados como
validados foram confirmados por diagnósticos causais no BizHawk com a ROM de SHA-1
esperado. Superfície/offtrack e a curva de Las Vegas estão validados; combustível
e a escala exata da marcha continuam pendentes.

| Índice | Nome | Origem | Transformação e intervalo |
|---:|---|---|---|
| 0 | `speed_norm` | `WRAM 0x1E5A`, `s16` | `clip(speed / speed_scale, 0, 1)` |
| 1 | `lateral_norm` | `WRAM 0x1E8A`, `s16` | posição relativa a `lateral_center`, em `[-1, 1]` |
| 2 | `progress_norm` | fixed-point `u16 LE` em `0x1ED7` e comprimento `0x0200` | progresso na volta, em `[0, 1]` |
| 3 | `lap_norm` | volta `0x1E76`, total `0x1E56` | `clip(lap / total_laps, 0, 1)` |
| 4 | `rank_norm` | `0x1E7A`, candidato zero-based | `rank / 19`; **menor é melhor** |
| 5 | `collision` | borda do bit `0x0080` em `0x1EF5` | evento ocorrido em qualquer frame da última ação |
| 6 | `offtrack` | `WRAM 0x0727`, `u8` | `0` somente quando o estado é pista (`1`); senão `1` |
| 7 | `surface_direction` | `WRAM 0x0727`, `u8` | estado menos 1: `-1` fora à esquerda, `0` pista, `+1` fora à direita |
| 8 | `fuel_norm` | `0x1E62`, `u16` | `clip(fuel / fuel_scale, 0, 1)` |
| 9 | `nitro_norm` | contagem decodificada de `0x1E6C` | nitros disponíveis divididos por 3, em `[0, 1]` |
| 10 | `turbo_active` | bit 15 do estado `0x1E6C` | flag binária validada |
| 11 | `gear_norm` | `0x1E72`, `u16` | `clip(gear / gear_scale, 0, 1)` |
| 12 | `curve_current_norm` | byte baixo `s8` de `0x4C00`, indexado por `0x0046` | `clip(curve / 32, -1, 1)` |
| 13 | `curve_ahead_512_norm` | mesma tabela, posição suavizada `+512` | curva futura normalizada em `[-1, 1]` |
| 14 | `curve_ahead_1024_norm` | mesma tabela, posição suavizada `+1024` | curva futura normalizada em `[-1, 1]` |
| 15 | `curve_ahead_2048_norm` | mesma tabela, posição suavizada `+2048` | curva futura normalizada em `[-1, 1]` |
| 16 | `nearest_valid` | derivada da tabela de corredores | máscara binária |
| 17 | `nearest_distance_norm` | tabela `0x0212`, offsets `+7/+9` | distância longitudinal à frente dividida pelo alcance |
| 18 | `nearest_lateral_norm` | tabela `+2` menos lateral P1 | delta lateral em `[-1, 1]` |
| 19 | `closing_rate_norm` | diferença de `nearest_distance` entre estados | positivo quando P1 se aproxima; em `[-1, 1]` |
| 20 | `lane_negative_risk` | adversários à frente com delta lateral negativo | `1 - distância/alcance`, em `[0, 1]` |
| 21 | `lane_center_risk` | adversários na banda central relativa | `1 - distância/alcance`, em `[0, 1]` |
| 22 | `lane_positive_risk` | adversários à frente com delta lateral positivo | `1 - distância/alcance`, em `[0, 1]` |
| 23 | `finished` | `0x1F00` em faixa de rank | flag binária validada de chegada |

## Curva atual e antecipação

A ROM calcula o índice como `(position >> 4) & 0xFFFE`, equivalente a
`2 * floor(position / 32)`. A posição usada é o acumulador suavizado `u16` em
direct page/WRAM `0x0046`; cada entrada ocupa dois bytes em `0x4C00`, mas a rotina
entrega somente o byte baixo assinado ao multiplicador lateral.

Para `track_length=22528`, a tabela possui 704 entradas válidas. A exportação
completa apresentou quatro regiões não zero. Cruzando-a com os rótulos manuais:

- 6/6 retas: coeficiente `0`;
- 6/6 curvas à esquerda: coeficiente `16`, `24` ou `32`;
- separação total: 12/12.

Os quatro look-aheads são calculados com wrap no comprimento da pista. O sinal
assinado é preservado, mas Las Vegas não contém curva à direita; o significado
do sinal negativo deve ser validado em outra pista antes de generalizar.

## Sensor de superfície

O Lua lê somente `0x0727`. O segundo candidato, `0x0A67`, não é usado porque a
captura contínua mostrou 51 divergências em 3.600 frames e comportamento de
buffer atrasado. A codificação usada pelo protocolo foi confirmada em duas
coletas rotuladas e por overlay ao vivo:

```text
0 -> fora à esquerda -> offtrack=1, surface_direction=-1
1 -> pista           -> offtrack=0, surface_direction= 0
2 -> fora à direita  -> offtrack=1, surface_direction=+1
```

Python rejeita qualquer outro valor e também rejeita combinações inconsistentes
entre `surface_state`, `surface_direction` e `offtrack`.

No primeiro treino real, uma colisão com cacto longe da pista produziu o byte
bruto `255`. A partir da v2.0.28, a ponte mantém duas representações:

- `surface_raw`: byte original de `0x0727`, inclusive `255`;
- `surface_unknown`: `1` quando o byte não pertence a `0/1/2`;
- `surface_state`: estado compatível usado pela observação;
- `offtrack=1` e direção obtida do último lado conhecido ou da lateral de P1.

O valor desconhecido nunca pode ser convertido em pista. Os dois campos novos
ficam na telemetria e em `info`, mas não alteram as 24 posições da observação v5.

## Decodificação do turbo

O protocolo mantém `nitro_raw` para auditoria, mas a rede recebe dois campos
semanticamente estáveis:

```text
turbo_active = 1 se nitro_raw >= 0x8000; caso contrário, 0
nitro_low2 = nitro_raw % 4
nitro_disponivel = nitro_low2 - 1 enquanto turbo_active=1
                   nitro_low2     enquanto turbo_active=0
```

O diagnóstico causal começou em `0x0003`, entrou no estado ativo em `0x8003`,
percorreu o temporizador até `0xFF03` e terminou em `0x0002`. Portanto, uma carga
é considerada consumida desde o início do impulso, e a observação continua
indicando duas disponíveis durante e depois dele.

## Derivação dos adversários

Cada registro candidato fica em:

```text
record(i) = 0x0212 + i * 0x12, para i = 0..19
```

Campos usados:

| Offset | Leitura candidata | Uso atual |
|---:|---|---|
| `+0` | ID e flags | ID mascarado com `% 32`; P1/P2 excluídos por ID |
| `+2` | lateral `s16` | delta lateral para P1 |
| `+7` | progresso `u16` | distância longitudinal relativa |
| `+9` | volta `s8`, baseada em 1 | subtrai 1 e compõe progresso absoluto relativo |
| `+10` | movimento longitudinal `u16` | publicado como `nearest_motion_raw`, fora da rede |
| `+16` | status/flags | apenas diagnóstico; sem semântica confirmada |

O Lua considera candidatos com IDs `2..19` e calcula:

```text
delta_forward = ((lap_ai_raw - 1) - lap_p1) * track_length
                + (progress_ai - progress_p1)
delta_lateral = lateral_ai - lateral_p1
```

Somente `0 < delta_forward <= sensor_range` entra nos sensores. Esse método
resolve a passagem pela linha de volta quando os contadores são válidos. A
captura validada manteve os 18 IDs de IA e associou seis impactos a carros entre
18 e 56 unidades à frente. Ainda falta descobrir como identificar registros
inativos, invisíveis ou finalizados em outros modos de corrida.

O protocolo também publica `collision_events`, contador cumulativo reiniciado a
cada episódio. O Lua inspeciona todos os frames da ação; assim, pulsos de 1–3
frames não desaparecem quando `frame_repeat=4`. O reward usa a diferença desse
contador e não depende de observar o nível do bit no último frame.

## Máscaras e valores ausentes

- Sem adversário detectado, `nearest_valid=0`, distância normalizada `=1` e delta
  lateral `=0`.
- Uma banda sem carro recebe risco `0`.
- A taxa de aproximação só é calculada quando o mesmo ID é o mais próximo em dois
  estados consecutivos.
- Valores são verificados contra `NaN`, infinito e limites do `Box`.

## Informação ainda ausente

A v5 ainda não contém centro variável da pista, distância exata até a transição
de curva nem limites esquerdo/direito por segmento. `0x4000` participa da física
longitudinal, `0x5800` seleciona tipos/limites locais e `0x7002` limita
competidores; eles não foram promovidos à observação sem semântica validada.
Modelos v4 têm dimensão incompatível e não podem ser carregados como v5.

Os sensores de adversário cobrem apenas `delta_forward > 0`. Eles ajudam a evitar
o carro à frente, mas ainda não descrevem carros emparelhados ou vindo por trás.
Uma versão voltada a trocas de faixa robustas deve acrescentar máscaras/distâncias
laterais e traseiras depois de validar o filtro de registros ativos.
