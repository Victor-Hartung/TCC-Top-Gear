# Ensaio local: manter quarta ou subir para quinta

**Próximo ensaio após concluir v7:** [azul já em movimento, slot 3](ENSAIO_CAMBIO_LANCADO.md).
O Lua antigo de largada permanece preservado; o novo é `ensaio_cambio_lancado.lua`.
Não continuar estendendo a trajetória sem direção para dentro do tráfego.

## Histórico: azul manual, terceiro ponto curto (v7 do ensaio)

A segunda coleta azul, `ensaio_cambio_20260915_202314_0.csv`, passou nas quatro
rodadas, com repetições idênticas e sem interferências. Partindo de velocidade
bruta 6754, em 60 frames a quarta chegou a 7178 (ganho 424, consumo 216), e a
quinta a 7126 (ganho 372, consumo 159). A vantagem foi de 14,0% no ganho de
velocidade, mas só 0,73% na velocidade final. A quarta ainda foi melhor neste
ponto; o ponto ideal de troca não foi identificado.

O Lua atual usa `capture_version=7`, `prep_frames=360`, `measure_frames=24`,
carro 48. Espera-se iniciar perto de 7178, a confirmar no jogo. A janela foi
reduzida porque o diagnóstico anterior registrou impacto no frame relativo 679;
com a espera observada de 280 frames, esta coleta mede os frames 640..663.
Esse histórico não garante ausência de impacto em outra trajetória: qualquer
interferência continua invalidando a comparação. A janela de 24 frames mede
somente a resposta imediata, incluindo a troca; não prova vantagem sustentada.

Use o mesmo save 2 e os mesmos comandos abaixo. O overlay mostra **ENSAIO v7
AZUL**; quatro rodadas, cerca de 44 segundos de jogo, sem treino. O analisador
preserva as durações originais de todos os formatos anteriores. Não comparar
ganhos absolutos desta janela com os de 60 frames. Não prolongar sucessivamente
o teste sem direção para dentro do tráfego: se não houver ponto de cruzamento
nesta janela, será necessário outro contexto controlado para medir altas
velocidades. Esta atualização ainda precisa de execução no BizHawk real.

## Histórico: azul manual, segundo ponto (v6 do ensaio)

O primeiro ensaio real do azul (`ensaio_cambio_20260915_201951_0.csv`) passou:
quatro rodadas ABBA com mesmas condições observadas e repetições idênticas,
sem impacto, nitro ou saída da pista. Em 60 frames, partindo de 6137, manter
quarta terminou em 6754 (ganho 617, consumo 223); subir para quinta terminou
em 6666 (ganho 529, consumo 160). Tudo em unidades brutas. A quarta teve 16,6%
mais ganho de velocidade, mas apenas 1,32% mais velocidade final. Não é uma
comparação com o automático nem prova de que se deve manter quarta sempre.

O Lua atual usa `capture_version=6`, `prep_frames=300`, `measure_frames=60`,
carro 48. Mantém quarta por mais 60 frames antes de comparar; espera-se iniciar
perto de 6754, a confirmar no teste real. Aproximadamente 43 segundos de jogo,
quatro rodadas automáticas. Os comandos abaixo e o save 2 permanecem os mesmos.
O overlay mostra **ENSAIO v6 AZUL**. Dez testes com API simulada verificam a
implementação e a compatibilidade do analisador com o primeiro ponto; a v6
ainda aguarda execução no BizHawk. Qualquer interferência invalida a comparação.

## Histórico: azul manual, primeiro ponto (v5 do ensaio)

O usuário escolheu testar o azul; o segundo ponto do branco foi deixado de lado.
Na coleta `cambio_manual_20260915_201647_5718_0.csv`, oito PNGs confirmam o carro
azul do jogador superior e GEAR 1, 2, 3, 4, 5, 4, 5, 4. O valor em `0x1EE8`
foi 48 durante toda a coleta. As sete respostas de R/L passaram. A associação
cor/valor é observada nesta configuração, não uma tabela presumida para carros
ainda não testados. O primeiro impacto ocorreu no frame 679, velocidade bruta
7312 → 5469; nenhuma saída da pista foi registrada.

O Lua atual exige carro 48 e usa `capture_version=5`, `prep_frames=240`,
`measure_frames=60`. Reproduz a preparação até a quarta e compara manter quarta
com subir para quinta, em quatro rodadas ABBA. Pelo diagnóstico, espera-se
partir perto de velocidade bruta 6137; confirmar na execução. A janela anterior
à batida observada não garante ausência de interferência na nova trajetória:
qualquer impacto, nitro ou saída da pista continua invalidando a comparação.

Execute os mesmos comandos abaixo com o save 2 atual; aproximadamente 39 segundos
de jogo. O novo ensaio passou em nove testes com API simulada e aguarda execução
real. A análise mantém suporte às coletas vermelhas e brancas sem misturar suas
identidades. Perfil operacional, PPO e saves não foram alterados; uma cópia do
save azul foi preservada. Isso ainda não comprova que o azul seja o melhor carro.

## Histórico: branco manual, segundo ponto preparado (v4 do ensaio)

Primeira comparação do branco aprovada: `ensaio_cambio_20260915_195044_0.csv`.
Em 60 frames, ambas as variantes partiram de 6554. Manter quarta terminou em
7172 (ganho 618, consumo 187); subir para quinta terminou em 7165 (ganho 611,
consumo 140). Unidades brutas. As repetições coincidiram e não houve interferência.
A diferença de velocidade final foi somente 0,10%; não reproduziu a grande
vantagem da quarta observada no vermelho. Não se deve fixar quarta para o branco
nem extrapolar este resultado para velocidades maiores.

O Lua atual usa `capture_version=4`, `prep_frames=300`, `measure_frames=60`,
carro 16. Mantém quarta por mais 60 frames antes de comparar: espera-se partir
perto de 7172, a conferir na próxima coleta. Continua exigindo quatro rodadas
ABBA válidas, sem impacto, nitro ou saída da pista. Aproximadamente 43 segundos
de jogo; os comandos abaixo permanecem os mesmos. O save não precisa ser recriado.
O novo ensaio foi testado com API simulada e ainda aguarda execução real.
Prioridade do usuário: tempo/aceleração nesta pista; o consumo será registrado,
mas não será usado sozinho para escolher uma marcha mais lenta.

## Histórico: branco manual (v3 do ensaio)

A coleta real `cambio_manual_20260915_194654_3963_0.csv` e seus oito PNGs
confirmaram o carro branco, `0x1EE8 = 16`, bruto 0..4 = GEAR 1..5 e sete
respostas corretas de R/L. Essa associação vale para a configuração observada;
não foi deduzida uma tabela de cores para valores ainda não testados.

Houve impacto no frame relativo 677 (bit 0x80, velocidade 7627 → 4594).
A coleta continua válida para os comandos, mas esse trecho não deve calibrar
aceleração. O ensaio v3 mediu antes: `capture_version=3`, `prep_frames=240`,
`measure_frames=60`, carro obrigatório 16. Espera movimento, prepara a quarta
e compara uma janela de 60 frames, duas vezes por opção. Deve levar cerca de
39 segundos de jogo com o save atual. Mantém a recusa de qualquer interferência;
encurtar a janela não garante ausência de colisão na nova trajetória.

**Execute os mesmos comandos abaixo, reabrindo o Lua atualizado.** Não precisa
recriar o save. Os resultados vermelhos continuam preservados e reconhecidos
pelos formatos v1/v2; não transferimos suas conclusões ao branco. O ensaio v3
passou em nove testes com API simulada e aguarda execução real. O PPO e o perfil
operacional continuam sem alterações.

## Histórico e procedimento

Pré-requisito atendido: a coleta real com imagens de 15/09 confirmou os controles
R/L e bruto 0..4 = GEAR 1..5 no carro vermelho, slot 2 manual. O teste abaixo
teve uma primeira execução real válida, registrada abaixo. A segunda medição
atualizada ainda precisa ser executada no BizHawk real; os oito testes de
implementação usaram API simulada e não medem a física real do jogo.

O `lua/ensaio_cambio.lua` carrega o slot 2 quatro vezes, sempre com X pressionado,
sem nitro e sem direção. Depois de esperar movimento, reproduz a preparação
validada até a quarta marcha e a mantém por mais 180 frames que na primeira
medição. Compara então 60 frames mantendo quarta versus
enviando quatro frames de R para quinta. Ordem: manter, subir, subir, manter.
Cada opção tem duas repetições. Duração esperada nesse save: cerca de 49 segundos
de jogo no total, além do tempo de leitura dos fingerprints.

É uma comparação no ponto específico atingido pela preparação, não uma busca
completa pelo ponto ideal. Ambas as variantes estão em modo manual; não se deve
concluir vantagem sobre o automático ou aumento de vitórias a partir dela.
Não treina, não usa o ator PPO, não altera ações/observações/recompensas, não
grava savestates nem escreve WRAM. O save automático no slot 1 é preservado.

## Executar

Com Python de jogo/treino parado e BizHawk sem socket, abra a ROM habitual.
Se precisar abrir o emulador:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe"
```

Em **Tools → Lua Console**, pare os outros scripts e abra
`lua\ensaio_cambio.lua` na pasta operacional v3.0. Escolha o mesmo
`config\game_profile.ini`. Deixe rodar/despause se necessário. Não toque nos
controles e não recarregue saves durante a coleta: as quatro rodadas são
automáticas. O painel indica rodada, variante, fase e marcha.

Ao aparecer `ENSAIO CONCLUIDO`, execute:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\analisar_ensaio_cambio.py
```

O resultado vai para `runs/diagnostics/ensaio_cambio_*_analysis_*.json`, com
nome único e hash do CSV. A análise exige quatro execuções completas, comandos
e marchas corretos, continuidade, mesma preparação observada e fingerprints
Adler-32 de toda a WRAM iguais após o reset e no ponto de comparação. Exige
também que as duas repetições de cada variante tenham as mesmas séries medidas.
Fingerprint não é prova de identidade de todo o estado interno do emulador;
o experimento combina reset pelo mesmo slot com essas verificações observadas.

Qualquer impacto (bit 0x80), saída da pista, uso de nitro, preparação divergente
ou troca ignorada torna a comparação inconclusiva. Não descarta só os trechos
ruins para declarar uma opção vencedora. A flag bruta 16 da largada, sozinha,
não é classificada como impacto.

Se válido, informa ganho de velocidade, velocidade média e combustível gasto,
todos em valores brutos. `hold_minus_shift` é manter quarta menos subir para
quinta; valor positivo em velocidade favorece manter quarta **nesse ponto e
nessa janela**. Valor positivo em consumo significa maior gasto de combustível.
RPM calibrado, melhor ponto de troca, efeito do nitro, comparação com automático
e desempenho em corrida completa continuam fora do alcance deste ensaio.

## Primeira medição real: troca com velocidade bruta 4818

Fonte preservada: `runs/diagnostics/ensaio_cambio_20260915_193607_0.csv`, SHA-256
`b684b3da840b93822360797f64198b89cf11b5f250bcee79a7920e6a074435c2`.
Resultado `paired_measurement_ok`: quatro rodadas completas, preparação e
fingerprints iguais; séries idênticas entre repetições da mesma variante.
Sem impacto, saída da pista ou uso de nitro. A janela original era de 180 frames.

| Variante | Velocidade inicial | Velocidade final | Ganho de velocidade | Combustível consumido |
|---|---:|---:|---:|---:|
| Manter quarta | 4818 | 6572 | 1754 | 725 |
| Subir para quinta | 4818 | 5710 | 892 | 485 |

Tudo em unidades brutas. Na janela testada, manter quarta deu 96,6% mais ganho
de velocidade e consumiu 49,5% mais combustível. A velocidade final foi 15,1%
maior; não confundir ganho de velocidade com velocidade final. É uma evidência
real de custo de trocar cedo **nesse ponto**, não de que quarta sempre vence
quinta ou de que o manual já supera o automático.

## Segunda medição preparada

O Lua atual usa `capture_version=2`, `prep_frames=420`, `measure_frames=60`.
A primeira medição usou preparação de 240 frames e medição de 180 frames.
Os três pulsos para chegar à quarta são os mesmos; agora o carro permanece
mais 180 frames em quarta antes da comparação. Pelo resultado anterior, espera-se
iniciar perto de velocidade bruta 6572, mas isso será conferido na nova coleta.
A janela mais curta evita avançar desnecessariamente para fora do trecho reto;
se houver interferência, o resultado continuará inconclusivo.

Não comparamos diretamente ganhos de janelas de 180 e 60 frames como se tivessem
a mesma duração. Cada rodada de quarta é pareada com a de quinta da própria
medição. O analisador reconhece o formato legado e os metadados novos, rejeita
misturas e mantém o resultado da primeira coleta sem reinterpretar seu cronograma.
Os comandos e o arquivo Lua para executar permanecem os mesmos. Modelos, perfil
operacional automático, slots 1 e 2 e relatórios anteriores foram preservados.
