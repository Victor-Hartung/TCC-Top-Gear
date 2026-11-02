# Validação da tabela de curvas de Las Vegas

## Resultado

A tabela `WRAM 0x4C00` foi validada para a corrida de Las Vegas da ROM
Top Gear (USA), SHA-1 `f686806c676a4b087a3627babbe3555d3704e3b1`.

A rotina da ROM calcula o offset com quatro deslocamentos à direita seguidos de
`AND #$FFFE`:

```text
offset = (position >> 4) & 0xFFFE
       = 2 * floor(position / 32)
```

Cada entrada ocupa dois bytes, mas somente o byte baixo assinado é entregue ao
multiplicador que afeta a posição lateral. A posição usada pela rotina é o
acumulador suavizado em direct page/WRAM `0x0046`.

## Integridade da coleta

- comprimento da pista: `22528`;
- entradas válidas: `704`;
- resolução: 32 unidades de progresso por entrada;
- valor mínimo/mediano/máximo: `0 / 0 / 32`;
- entradas zero/positivas/negativas: `392 / 312 / 0`;
- valores distintos: 7.

A coleta anterior continha 1.408 linhas por usar a hipótese `/16`. As primeiras
704 já formavam a tabela completa; a metade posterior ficava além da tabela
válida. Portanto, não foi necessário repetir a captura.

## Regiões não zero

| Índices | Progresso | Entradas | Faixa | Soma |
|---|---:|---:|---:|---:|
| 129..254 | 4128..8159 | 126 | 4..16 | 1968 |
| 449..542 | 14368..17375 | 94 | 4..24 | 2144 |
| 545..574 | 17440..18399 | 30 | 4..32 | 768 |
| 641..702 | 20512..22495 | 62 | 4..16 | 944 |

## Cruzamento visual

O índice de cada rótulo foi recalculado por `floor(progress/32)`:

| Rótulo | Progresso observado | Índice | Coeficiente |
|---|---:|---:|---:|
| reta | 92 | 2 | 0 |
| reta | 2338 | 73 | 0 |
| esquerda | 5484 | 171 | 16 |
| esquerda | 6687 | 208 | 16 |
| reta | 8742 | 273 | 0 |
| esquerda | 14837 | 463 | 24 |
| esquerda | 15887 | 496 | 24 |
| esquerda | 16718 | 522 | 24 |
| esquerda | 17912 | 559 | 32 |
| reta | 18550 | 579 | 0 |
| reta | 19390 | 605 | 0 |
| reta | 20129 | 629 | 0 |

Separação direta: **12/12 (100%)**. Todas as retas foram zero; todas as curvas
à esquerda foram positivas. Isso valida o sinal e a intensidade para Las Vegas.
Como essa pista não contém curvas à direita, valores negativos ainda precisam
ser confirmados em outra pista antes de afirmar generalização para todo o jogo.

## Integração

A observação v5 publica quatro campos normalizados por `curve_scale=32`:

- curva atual;
- curva a 512 unidades;
- curva a 1024 unidades;
- curva a 2048 unidades.

`curve_telemetry_validated=true`. A ponte real publicou os quatro campos e
preservou reset, `seq/ack` e avanço exato de quatro frames; por isso,
`profile_validated=true` foi liberado na v2.0.27.
