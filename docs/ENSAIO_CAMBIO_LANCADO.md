# Azul em movimento: quarta versus quinta

## Atualização: janela de dois segundos (v10)

A coleta de três segundos `ensaio_cambio_lancado_20260916_163258_0.csv` ficou
**inconclusiva**. Em todas as quatro rodadas, a superfície mudou para 2 (fora
pela direita) no frame relativo 132; o primeiro impacto surgiu no 143. Nitro
permaneceu intacto. A queda de velocidade final não mede o efeito puro da marcha.
O relatório original foi preservado; não se recortou o trecho ruim para promover
essa coleta a aprovada. O analisador agora registra tipo e primeiro frame de
cada interferência por rodada.

O novo ensaio usa o mesmo save 3, `capture_version=10`, medição de 120 frames,
zero preparação. São dois segundos por rodada, quatro rodadas ABBA. Essa duração
é definida antes da nova execução e termina antes da saída de pista observada,
mas a nova coleta ainda precisa passar em todas as verificações. Não comprova
o resultado de três segundos nem um ponto de troca universal.

**Reabra o Lua atualizado e use o mesmo comando de análise abaixo.** O overlay
deve mostrar **ENSAIO LANCADO v10 AZUL**. Não precisa criar outro save ou dirigir.
O novo teste ainda aguarda execução real. As verificações automatizadas usam API
simulada; não modificam os critérios que reprovaram a captura de três segundos.

## Resultado real de um segundo e próximo ensaio

A coleta `ensaio_cambio_lancado_20260916_162956_0.csv` passou: quatro rodadas
ABBA válidas, repetições iguais, sem impacto, saída da pista ou nitro. Partindo
de 7833, em 60 frames manter quarta terminou em 8145 (ganho 312, consumo 275)
e subir quinta em 8136 (ganho 303, consumo 200). Valores brutos. A diferença
final é de apenas 0,11%. Nos últimos 20 frames ambas ganharam 106 unidades;
isso sugere proximidade de desempenho, mas não localiza o ponto ótimo.

**Não precisa preparar outro save.** A versão atual 9 usa o mesmo slot 3 e mede
180 frames por rodada, aproximadamente três segundos, para comparar a resposta
sustentada. Quatro rodadas somam cerca de 12 segundos de jogo, além dos resets
e leituras de memória. Se houver interferência, a comparação será inconclusiva;
o bom resultado da janela de um segundo não garante que a maior ficará limpa.
O save 3 foi copiado para `runs/maintenance/rolling_sustained_20260916_163126/`.
Ainda não foi validada vantagem do manual sobre o automático, nem integração PPO.

## Preparação e procedimento

Os três ensaios anteriores, partindo da largada, favoreceram manter quarta nos
pontos testados. O último (`ensaio_cambio_20260916_162319_0.csv`) partiu de 7178
e, em 24 frames, terminou em 7312 mantendo quarta ou 7294 subindo para quinta.
Ganhos 134 e 116; vantagem de somente 0,25% na velocidade final. Quatro rodadas
válidas, repetições iguais. Isso não identifica o ponto ideal nem prova que
quarta seja superior em qualquer velocidade. Nenhum deles compara com automático.

O tráfego limita prolongar a trajetória sem direção. O próximo ensaio parte de
um **save 3 separado**, já em movimento, para medir uma faixa maior sem repetir
a largada. O slot 2 de largada e o slot 1 automático não devem ser sobrescritos.

## Preparar uma vez, dirigindo manualmente

1. Pare todos os scripts na Lua Console. Carregue o slot 2 azul manual.
2. Dirija em Las Vegas sem usar nitro. Chegue à quarta marcha (GEAR 4).
3. Em uma reta, alinhado no asfalto, procure uma velocidade no painel de cerca
   de 180–190 km/h, sem carros próximos na mesma trajetória e sem estar batendo.
   Essa faixa visual é uma orientação para preparar o cenário, não uma conversão
   calibrada da velocidade bruta nem um ponto de troca validado.
4. Pause o emulador e salve no **slot 3** pelo menu de savestates. Não salve por
   cima dos slots 1/2. Não é necessário mexer em botões durante a medição.

O código exige quarta, azul (`0x1EE8=48`), controle manual Type A, velocidade
bruta maior que 7312, asfalto, nenhum impacto ativo e três nitros intactos.
Se falhar nessa checagem, preserva a coleta e informa o motivo. Estar visualmente
numa reta livre não garante que toda a janela será limpa: a análise verificará.

## Executar

Na Lua Console, abra `lua/ensaio_cambio_lancado.lua`, selecione o perfil habitual
e despause se necessário. Deve aparecer **ENSAIO LANCADO v10 AZUL**. O Lua carrega
somente o slot 3 quatro vezes: manter quarta, subir quinta, subir quinta, manter
quarta. Cada medição dura 120 frames, cerca de dois segundos; o tempo total inclui
as leituras da WRAM e os resets. Não usa nitro, freio ou direção, não aprende e
não escreve WRAM nem savestates. Libera os controles ao terminar/interromper.

Após `ENSAIO CONCLUIDO`:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\analisar_ensaio_cambio.py
```

A coleta se chama `ensaio_cambio_lancado_*.csv`. O formato atual é versão 10,
preparação 0, medição 120, slot 3. As versões 8 (60 frames) e 9 (180 frames) continuam
reconhecida sem reinterpretar seus resultados. A análise exige estado inicial e ponto de
comparação com fingerprints WRAM iguais, séries repetidas iguais, comandos
previstos, resposta da marcha, nenhum impacto/saída da pista/nitro. Não mistura
ganhos de durações diferentes nem usa trechos contaminados para escolher marcha.

O ensaio só compara as duas decisões nesse estado. Não calibra RPM, não libera
treino e não transfere automaticamente a conclusão para todo o circuito ou
para nitro ativo. A implementação foi verificada com APIs simuladas; o novo
ensaio de dois segundos ainda aguarda execução no BizHawk real.
