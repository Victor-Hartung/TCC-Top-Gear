# Diagnóstico de curva e mapa completo

## Etapa preferencial: exportação automática da pista

O jogo mantém em WRAM uma tabela da geometria da pista ativa. Para Las Vegas,
não é necessário dirigir nem marcar manualmente todos os trechos:

1. Abra a corrida de Las Vegas e deixe o jogo carregado na pista. Pode pausar.
2. Feche qualquer outro script Lua.
3. Execute somente `lua/diagnostico_mapa_curvas.lua`.
4. O script exportará imediatamente `diagnostico_mapa_curvas.csv` na raiz.
5. No terminal, execute:

   ```powershell
   py -3.11 python\analyze_curve_map.py
   ```

6. Envie `diagnostico_mapa_curvas.csv` e
   `diagnostico_mapa_curvas_resultado.txt`.

A exportação contém todas as `ceil(track_length/32)` entradas, e não apenas os
índices pelos quais o carro passou. Ela separa o byte baixo efetivamente enviado
ao multiplicador, o word bruto, a tabela de inclinação e a tabela de tipo de
pista. O índice usado pela rotina é a posição suavizada em direct page `$46`.

## Etapa rotulada auxiliar

Esta etapa confirma a tabela candidata `WRAM 0x4C00` sem inventar direção,
limiar ou distância útil. A análise estática da ROM já comprovou que a tabela é
indexada por `2*floor(progress/32)`, equivalente a
`(progress >> 4) & 0xFFFE`, e participa diretamente da atualização da
posição lateral. A corrida vencedora mostrou que cada índice mantém o mesmo
valor entre voltas. Ainda precisamos associar esses valores à imagem.

## Como executar

1. Abra uma corrida e mantenha somente um script Lua ativo.
2. Execute `lua/diagnostico_curva.lua`. Na versão atual, prefira as teclas com o
   jogo em foco: `C` para reta, `V` para esquerda, `B` para direita e `N` para
   finalizar Las Vegas sem curva direita.
3. Aparecerá uma janela com três botões: **RETA**, **CURVA ESQUERDA** e
   **CURVA DIREITA**.
4. Dirija normalmente. Com o carro no asfalto, pressione a tecla correspondente
   ao trecho onde o carro está naquele momento. Os botões continuam disponíveis
   como alternativa, mas soltar o acelerador para clicar pode reduzir a velocidade.
5. Faça seis capturas de cada tipo disponível, em pontos diferentes. O script ignora
   cliques separados por menos de 20 frames e amostras feitas fora do asfalto.
6. Se a pista realmente não tiver curvas à direita, complete seis retas e seis
   curvas à esquerda e clique em **FINALIZAR: ESTA PISTA NÃO TEM CURVA DIREITA**.
   Não invente rótulos à direita.
7. Ao completar a coleta, será criado `diagnostico_curva.csv` na raiz do projeto.
8. No terminal do VS Code, execute:

   ```powershell
   .\.venv\Scripts\python.exe python\analyze_curve.py
   ```

9. Envie `diagnostico_curva.csv` e `diagnostico_curva_resultado.txt`.

## O que será comparado

Cada rótulo registra o coeficiente atual e o mesmo coeficiente nos pontos
`+256`, `+512`, `+1024` e `+2048` de progresso. O analisador procura:

- qual sinal corresponde a esquerda e direita;
- um possível intervalo neutro para retas;
- qual distância tem maior correspondência com a percepção visual;
- valores contraditórios que impeçam a integração.

O script mostra os valores brutos na tela, mas não chama positivo ou negativo
de esquerda/direita. Essa associação só será feita após os rótulos. O
diagnóstico não altera flags automaticamente. Em Las Vegas, a coleta completa
e os 12 rótulos já validaram `curve_telemetry_validated=true`.
Uma pista com apenas uma direção pode validar reta versus curva para o objetivo
específico desse savestate, mas não comprova generalização para outras pistas.
