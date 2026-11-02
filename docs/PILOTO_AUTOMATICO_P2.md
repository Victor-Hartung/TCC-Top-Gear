# Investigação do desvio do carro inferior — 13/09/2026

## Conclusão

A ROM contém um controlador programado de trajetória para P2. Foi localizada a
rotina que escolhe espaço lateral ao se aproximar do próximo registro de carro,
suaviza a trajetória desejada, compensa curva e produz direção interna. Ela oferece
uma referência concreta para melhorar a observação do PPO, mas não é um parâmetro
único de sensor nem uma garantia de ausência de colisões.

A análise da última avaliação do PPO também encontrou uma distinção importante:
em seis dos sete impactos havia risco positivo selecionado na observação antes
do evento. Logo, as colisões não podem ser atribuídas todas à falta de alerta.
Há ainda uma lacuna real: os sensores atuais excluem o outro registro de jogador.

Esta investigação leu somente a ROM oficial e evidências existentes. Não executou
novo teste no BizHawk, não alterou a ROM, ações, recompensa, savestate, contrato,
pesos ou código operacional. Os endereços novos permanecem resultados de análise
estática e correlação, com o escopo explicitado abaixo.

## Fontes e reprodução

- ROM `assets/rom/Top-Gear-USA.sfc`, SHA-1
  `f686806c676a4b087a3627babbe3555d3704e3b1`.
- Disassembler somente leitura já distribuído na v3.0:
  `archive/tools/disasm65816.py`. Nenhuma versão antiga foi restaurada.
- Fluxo de instruções: `runs/analysis/p2_rom_investigation/p2_control_flow.txt`.
- Hashes de fontes: `runs/analysis/p2_rom_investigation/sources.json`.
- Captura manual existente: `runs/diagnostics/contexto_20260912_084321_5525`,
  arquivos `_snapshots.csv`, `.wram.bin` e `_racers.csv`.
- Valores P2 extraídos: `runs/analysis/p2_rom_investigation/p2_snapshots.json`.
- Avaliação real de 3º lugar:
  `runs/avaliacao_modelo/avaliacao_20260913_164215_701717.json`.
- Auditoria por impacto e script de reprodução:
  `runs/analysis/p2_sensor_audit/audit.json` e `audit.py`.
- Paridade das 21 features do sensor com as entradas efetivamente entregues à
  rede em todas as 1.184 decisões:
  `runs/analysis/p2_rom_investigation/observation_parity.json`, zero divergências
  com tolerância de 1e-6. Não é uma nova corrida.

## Fluxo da ROM

Endereços de instrução nesta seção são CPU/LoROM. Endereços de dados são offsets
WRAM ou seus espelhos de banco; não são offsets do arquivo da ROM. As rotinas
alternam acumulador de 8/16 bits, e essa largura é essencial à interpretação.

1. **05:DB52–05:DB5C:** lê **word** em `0x1EF3`. Se não negativo e `0x1F04==0`,
   segue para o caminho automático em 05:ED92. Em M16, o sinal desse word vem do
   bit 7 do byte **0x1EF4**; não do byte 0x1EF3 isolado.
2. **05:F174–05:F17D:** se `0x1EEE==0`, executa o planejamento de trajetória;
   outros estados seguem um caminho de recuperação/relaxamento da direção.
3. **05:F188–05:F1A4:** usa o offset dinâmico P2 em `0x0206`, avança um registro
   de 18 bytes na tabela e trata o retorno ao primeiro dos 20 registros. Lê a
   lateral do vizinho e a lateral global P2, ambas divididas por dois com sinal.
4. **05:F222–05:F244:** no caminho normal, obtém dois limites de trajetória da
   tabela `WRAM 0x7002 + 2*floor(progresso_P2/32)`. Os bytes são expandidos com
   sinal em meia escala lateral. São limites internos usados pelo controlador;
   não devem ser chamados automaticamente de bordas físicas validadas da pista.
   Há caminhos especiais ligados a combustível/estado que usam outras tabelas.
5. **05:F246–05:F267:** verifica a distância para o vizinho. O caminho de desvio
   é considerado abaixo de **0x0200 = 512 unidades longitudinais**, ou no ramo
   de subtração com borrow. Também exige o vizinho dentro do corredor lateral.
   Não é uma distância em metros nem um tempo em segundos.
6. **05:F26A–05:F2E9:** escolhe o lado levando em conta espaço, diferença lateral,
   sinal do campo lateral `+4` do outro registro e estado de lado anterior.
   Os limiares incluem **0x0F00, 0x0A00 e 0x0800 em meia escala lateral**.
   Em unidades da lateral publicada no projeto, correspondem a 7680, 5120 e
   4096. O corredor é restringido de um lado do carro, mantendo margem.
7. **05:F2EB–05:F340:** suaviza a mudança dos limites, usando passos máximos
   de 0x0258/0x0500 em meia escala, e guarda os limites em `0x1EC4`/`0x1EC6`.
   O estado de lado é o byte alto do word em `0x1EC7`, isto é, **0x1EC8**;
   0x1EC7 também sobrepõe o word de limite, portanto não são campos independentes.
8. **05:F343–05:F392:** calcula o centro do corredor, aplica compensação de curva
   dependente da velocidade e escreve a direção interna em **0x1E80**. No caminho
   normal, a leitura `0x4C08+X` consulta quatro entradas à frente, equivalentes
   a 128 unidades de progresso. A aritmética usa o multiplicador do SNES,
   saturação e operações de 16 bits; copiar apenas constantes em float não é uma
   reprodução bit a bit.
9. **05:F3D1–05:F444:** transforma a direção interna em deslocamento lateral,
   aplica limites e atualiza `0x1E8C`.

Esquema conceitual, não implementação pronta para controlar P1:

```text
obter vizinho pelo próximo registro da tabela
obter corredor interno da pista no progresso atual
se vizinho próximo e dentro do corredor:
    escolher lado com espaço e considerar movimento lateral/estado anterior
    afastar o corredor do carro mantendo margem
suavizar os limites escolhidos
calcular direção para o centro do corredor, compensando curva e velocidade
aplicar a direção interna à física de P2
```

P2 automático escreve uma magnitude de direção diretamente. P1 com PPO escolhe
entre dez ações de controle, mantidas por quatro frames. Reproduzir a estratégia
para P1 exige traduzir uma trajetória desejada para esses controles; escrever
diretamente a variável interna de P1 mudaria o problema experimental.

## O que as capturas antigas confirmam

Foram lidos 83 snapshots completos de WRAM, espaçados aproximadamente 60 frames.
Em todos, `0x1F04=0` e o word em `0x1EF3` não era negativo: condição de seleção
do caminho automático presente. Isso não equivale a um trace de execução de
cada instrução. Sessenta e seis amostras têm volta P2 não negativa; em 56 dessas
o próximo registro está a distância longitudinal de 0 a 511.

O registro apontado por `0x0206` coincide com a lateral global `0x1E8C` e com o
progresso global `0x1EDA` em **83/83 snapshots**. Seu ID bruto mascarado é **zero
em todos os 83**. Logo, P2 não pode ser identificado exclusivamente por ID 1
nesta coleta. O índice muda durante a corrida e precisa ser acompanhado.

Exemplo registrado, frame 6545: P2 em lateral -5976, vizinho em 1990, distância
415; direção interna -1468 e corredor suavizado [-5120, -1440] em meia escala.
O exemplo é coerente com a estrutura da rotina, mas não mede isoladamente o
efeito causal de cada comparação.

Nenhum snapshot amostrado tinha o bit 0x80 de 0x1EF6 ativo. A amostragem de 60
frames pode perder pulsos: **isso não demonstra que P2 nunca bate**, nem permite
comparar sua taxa de impactos com um contador observado a cada frame.

## O que aconteceu nos sete impactos do PPO

Foram auditados os 64 frames anteriores a cada evento, usando somente observações
disponíveis antes das ações. O risco positivo abaixo estava selecionado e presente
nos valores efetivamente entregues à rede; não foi inferido usando o futuro.

| Impacto | Frame do evento | Maior antecedência de risco selecionado nessa janela | Ação na transição do impacto |
|---|---:|---:|---|
| 1 | 5560 | 40 frames | ACCELERATE |
| 2 | 5860 | Nenhum alerta na janela | TURBO_ACCELERATE |
| 3 | 6304 | 56 frames | LEFT |
| 4 | 7992 | 40 frames | LEFT_ACCELERATE |
| 5 | 8188 | 44 frames | ACCELERATE |
| 6 | 8388 | 44 frames | ACCELERATE |
| 7 | 9396 | 40 frames | LEFT_ACCELERATE |

O bit de impacto não informa autoria ou objeto. Um aviso próximo de um impacto
não identifica definitivamente quem causou o contato. Esses números não são
recall de 6/7 de um conjunto rotulado, nem taxa de falsos positivos. Eles mostram
que não faltou informação de risco em todos os casos; decisão, antecedência útil,
trajetória e recompensa também precisam ser avaliadas.

No impacto 2, os registros IDs 2..19 próximos estavam lateralmente distantes;
a causa segue desconhecida. A ausência de P2 no pacote é uma possibilidade a
investigar, **não prova de colisão com P2**.

## Lacuna do sensor atual e aplicação ao projeto

O Lua e `live_detector.py` aceitam somente os 18 IDs 2..19. Os dois registros
de jogador ficam de fora. Excluir P1 é necessário, mas excluir também P2 deixa
um carro participante sem representação de proximidade. A leitura por offsets
dinâmicos `0x0204`/`0x0206`, com checagem contra as globais, permite distinguir
os jogadores mesmo quando seus IDs brutos são iguais.

O detector atual fornece um carro selecionado por região (frente, trás, lado),
distâncias, velocidades relativas e risco previsto em 30 frames. Ele não fornece
o corredor escolhido nem o plano de trajetória que o controlador nativo executa.

Melhorias justificadas por esta investigação:

1. Incluir P2 com identidade própria derivada do offset validado, sem confundi-lo
   com P1 ou quebrar associação temporal quando a tabela muda de ordem.
2. Extrair e validar o corredor interno para informar espaço disponível em cada
   lado, preservando a distinção de bordas reais e alvos do controlador.
3. Comparar a margem/antecedência de aviso com o tempo necessário para o PPO
   efetivamente completar uma manobra; não limitar avaliação a haver um alerta.
4. Construir um controlador de referência separado a partir da rotina nativa,
   executado primeiro sobre registros e depois testado pelos mesmos botões de P1.
   Ele pode gerar exemplos ou servir de comparação. Não atribuir suas ações ao
   aprendizado do PPO.
5. Reavaliar incentivos de colisão após separar alertas ausentes, manobras tardias
   e avisos aos quais a política não respondeu de modo útil. A recompensa atual
   custou apenas 1,75 ponto pelos sete impactos; isso é hipótese de incentivo
   insuficiente, não prova causal de que aumentar a penalidade resolve.

Uma integração posterior mudará a semântica do sensor e deverá versionar o
contrato, preservar modelos antigos e exigir validação real antes de treino.
O preflight atual continua válido para o código operacional existente; esta
investigação não representa aprovação de um detector novo.
