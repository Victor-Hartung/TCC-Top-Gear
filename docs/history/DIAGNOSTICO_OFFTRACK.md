# Diagnóstico rotulado de pista/offtrack

Este diagnóstico existe porque os pares de `WRAM 0x7002` não representam os
limites físicos do jogador. Na corrida completa já capturada, eles produziram
muitos falsos estados “fora da pista”. O treino continua bloqueado até existir
evidência melhor.

## Como executar

1. Abra a ROM e entre em uma corrida jogável.
2. Na Lua Console, execute **somente** `lua/diagnostico_offtrack.lua`.
3. Dirija normalmente e faça as capturas em pontos diferentes da pista:
   - clique em **NA PISTA** quando o carro estiver claramente sobre o asfalto;
   - clique em **FORA ESQUERDA** quando estiver claramente fora pelo lado esquerdo;
   - clique em **FORA DIREITA** quando estiver claramente fora pelo lado direito.
4. Faça seis amostras de cada tipo. O contador aparece na janela e sobre o jogo.
5. O script encerra automaticamente em `6/6/6` e cria
   `diagnostico_offtrack.csv` na raiz do projeto.
6. No terminal do VS Code, com o ambiente virtual ativado, execute:

   ```powershell
   python python\analyze_offtrack.py
   ```

7. Envie o arquivo `diagnostico_offtrack_resultado.txt` e mantenha o CSV para a
   auditoria completa.

Os botões ficam em uma janela própria porque a tecla `F` é normalmente associada
a **Frame Advance** no BizHawk e pode pausar a emulação. O script não altera a
memória do jogo, não carrega savestate e não habilita treinamento.

## Critério de aceitação

Um bit altamente correlacionado ainda é somente candidato. Antes de usá-lo,
será repetido em trechos diferentes e observado durante as transições exatas
asfalto → acostamento → asfalto, nos dois lados. As coordenadas laterais das
amostras também dirão se um centro e uma largura constantes são defensáveis ou
se a geometria precisa variar por segmento.
