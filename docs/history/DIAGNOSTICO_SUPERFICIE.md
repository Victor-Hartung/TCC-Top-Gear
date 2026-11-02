# Validação causal dos candidatos de superfície

As duas coletas rotuladas encontraram exatamente dois endereços que separaram
36 de 36 amostras com três valores distintos:

- `WRAM 0x0727`: `0=fora à esquerda`, `1=pista`, `2=fora à direita`;
- `WRAM 0x0A67`: cópia idêntica de `0x0727`.

Os endereços pertencem a duas sequências espelhadas de sete bytes, espaçadas a
cada quatro bytes. Isso é evidência dinâmica forte, mas ainda não prova se o
buffer representa a superfície física do jogador ou apenas um dado de
renderização. O diagnóstico desta etapa registra todos os frames e mostra o
valor ao vivo sobre o jogo.

## Execução

1. Abra uma corrida e execute somente `lua/diagnostico_superficie.lua`.
2. Durante aproximadamente 60 segundos, atravesse esta sequência pelo menos
   três vezes:

   `pista → fora à esquerda → pista → fora à direita → pista`

3. Observe o texto sobre o jogo. Ele deve mudar exatamente nas bordas:
   `PISTA (1)`, `FORA ESQUERDA (0)` e `FORA DIREITA (2)`.
4. Ao terminar, execute no terminal do VS Code:

   ```powershell
   python python\analyze_surface.py
   ```

5. Envie `diagnostico_superficie.csv` e
   `diagnostico_superficie_resultado.txt`, informando também se o texto visual
   acertou todas as entradas e saídas.

O script não usa atalhos de teclado, não varre toda a memória e não deve causar
as pausas do diagnóstico anterior.

## Resultado validado

A captura de 3.600 frames e a confirmação visual do usuário validaram
`0x0727`. O endereço está integrado a partir da v2.0.22. `0x0A67` não é usado,
pois apresentou divergências compatíveis com atraso de buffer. Essa validação
libera somente a superfície/offtrack; o treinamento segue bloqueado até validar
curva atual/futura.
