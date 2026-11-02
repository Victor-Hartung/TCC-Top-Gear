# Resultado das verificações desta entrega

Data: 2026-09-06  
Versão: `2.0.28-surface-fallback`

## Verificado neste ambiente

| Verificação | Resultado |
|---|---|
| Testes unitários de configuração, protocolos, reward, observação e diagnósticos | 45/45 aprovados |
| Compilação sintática dos módulos Python | aprovada |
| Polling temporizado da v2.0.12 | reprovado ao vivo: não houve primeiro `ack` |
| Diagnóstico TCP da v2.0.13 | conexão aceita; handshake iniciado pelo Lua expirou nos dois lados |
| Diagnóstico TCP da v2.0.14 | `PING` recebido no Lua; Python expirou antes do início manual do script |
| Diagnóstico TCP da v2.0.15 | aprovado ao vivo nos dois sentidos com BizHawk pausado |
| Ponte TCP principal da v2.0.16 | `HELLO` aprovado; travou no primeiro frame por pausa explícita |
| Ponte TCP principal da v2.0.17 | `HELLO` aprovado; `frameadvance` não retomou o primeiro frame |
| Ponte TCP principal da v2.0.18 | aprovada ao vivo: reset, `seq/ack` e delta exato de quatro frames |
| Execução dos diagnósticos com API BizHawk simulada | base v2.0.7 aprovada; diagnóstico v4 ampliado requer validação real |
| Ponte principal com API simulada | base v2.0.7 aprovada; acumulador de impactos v2.0.8 requer validação real |
| Saídas simuladas | 64 linhas de execução, 667 de controles, 18.000 de adversários e 1.800 de pista |
| Integridade do modelo histórico ZIP | aprovada com `unzip -t` |
| SHA-1 da ROM recebida, calculado diretamente | `f686806c676a4b087a3627babbe3555d3704e3b1` |
| ROM/savestate dentro desta distribuição | nenhum encontrado |

## Evidência recebida do BizHawk 2.11.1

### Primeiro teste da ponte principal

A ponte publicada em v2.0.11 iniciou corretamente e produziu `status=ready`,
SHA-1 correto, WRAM de 131.072 bytes e todos os campos, incluindo
`nitro=3`, `nitro_raw=3` e `turbo_active=0`. O Python também escreveu comandos
`TGACT2` válidos em `action.txt`.

Entretanto, tanto o reset quanto uma ação neutra expiraram sem novo `ack`. A Lua
Console mostrou `1 ativo, 0 pausado`, sem exceção. O `state.txt` permaneceu em
`ready` enquanto `action.txt` avançou até um comando residual `close`. Isso
isola o defeito na retomada do laço após a espera ociosa, e não em ROM, perfil,
arquivos, parser, savestate ou telemetria.

A v2.0.12 substituiu `client.pause() + emu.yield()` apenas no laço ocioso por
polling com `client.exactsleep(2)`. O teste real também parou antes do primeiro
`ack`; por isso, a v2.0.13 adiciona um diagnóstico TCP independente. O
transporte principal só será trocado se esse teste mínimo for aprovado no
BizHawk real.

`diagnostico_memoria.csv`, 667 amostras, ROM com SHA-1 esperado e ramos
determinísticos partindo do mesmo savestate:

- neutro: velocidade `1949 → 0`; acelerar (`X`): `1949 → 3767`;
- após a mesma preparação, frear (`Y`): `3649 → 943`; soltar: `3649 → 2283`;
- lateral neutro: `1657 → 1657`; esquerda: `1657 → -10458`; direita: `1657 → 9297`;
- bit candidato de colisão permaneceu zero em todos os ramos;
- o byte em `0x1ED8` evoluiu lentamente, mas o byte seguinte variou de forma
  não monotônica. Com a fração em `0x1ED7`, o valor coerente é o fixed-point
  `u16 LE` iniciado em `0x1ED7` (`0x05D2 → 0x07D9` sob aceleração), comparável
  ao comprimento `0x5800`.

Conclusão: controles básicos e lateral foram validados para o layout testado.
Turbo, volta completa, rank, chegada, colisão e registros de adversários continuam
pendentes de validação específica.

Uma captura posterior de adversários confirmou 900 amostras completas dos 20
registros, com IDs `2..19` presentes uma vez por frame e dois registros de jogador
com ID bruto zero. O registro de índice 0 coincidiu com a lateral de P1 em 900/900
frames. Nesse mesmo registro, o byte `record+7` coincidiu com o byte baixo do
progresso global de P1 em 900/900 frames; por isso, a posição do registro permanece
como `u16 LE` em `record+7`, enquanto `record+6` é mantido separadamente como
acumulador fracionário.

A captura seguinte, já com os offsets separados, confirmou:

- 18 IDs de IA (`2..19`) presentes uma vez em cada um dos 900 frames;
- exatamente um registro ID 0 coincidindo com lateral e progresso de P1 em
  900/900 frames;
- `record+9 = player_lap + 1` nesse registro em 900/900 frames, comprovando a
  necessidade de normalizar a volta da tabela para base zero;
- `record+10` corresponde ao movimento longitudinal: a velocidade derivada do
  progresso diferiu entre 0,15% e 0,17% do campo nos 18 adversários;
- após normalizar a volta, o carro longitudinalmente mais próximo foi o ID 17
  nos 900 frames, a uma distância entre 81 e 519 unidades;
- o bit `0x0080` apareceu por um frame no final da captura anterior, exatamente
  quando o usuário informou ter ocorrido a colisão. O comportamento é compatível
  com pulso de impacto, embora colisões de tipos diferentes ainda devam ser testadas.

O limiar de mesma faixa, descarte de registros inativos e correspondência visual
do adversário continuam pendentes; `opponent_telemetry_validated` permanece falso.

O primeiro `diagnostico_pista.csv` contém 1.800 frames consecutivos e percorre
progresso `137 → 14896`, cobrindo 59 dos 88 segmentos da volta. Os acessos foram
determinísticos para cada valor de progresso observado, mas usaram o fixed-point
bruto como índice. Isso percorreu milhares de bytes de WRAM e não demonstrou uma
relação estável com curvatura: as correlações dos candidatos com deslocamento
lateral futuro ficaram fracas e o usuário dirigiu manualmente, confundindo curva
com comando. A batida informada nessa execução não pode ser localizada porque a
versão do CSV não registrava colisão. O diagnóstico v2.0.6 passa a registrar
segmento, look-ahead, comandos, velocidade, volta e pulso de colisão.

A captura v2.0.6 recebida em seguida contém 3.600 frames consecutivos
(`4922..8521`), percorre todas as 88 regiões de 256 unidades e inclui a volta
zero, a volta um e o início da volta dois. Ela registrou:

- velocidade `0..12879` e lateral `-10401..16910`;
- aceleração em 3.464 frames, esquerda em 1.277 e direita em 176; freio não foi
  usado nesta execução;
- nove bordas/grupos separados do bit `0x0080`, totalizando 17 frames ativos;
- queda imediata de velocidade em todas as nove bordas, por exemplo
  `8693 → 4002`, `10846 → 5234`, `12369 → 6064` e `6041 → 3017`;
- impactos tanto com lateral próxima do centro (`-2715..1354`) quanto com lateral
  extrema positiva (`12157..13468`). Como o usuário informou colisões com carros
  e com placa fora da pista, isso é forte indício de que o bit seja um pulso de
  impacto genérico, mas a captura não rotulou cada evento individualmente;
- um valor transitório de volta `0 → 1 → 0` por um único frame em progresso
  `22025`, antes da transição verdadeira no wrap `22524 → 45`. Esse transiente
  precisa ser filtrado antes do treino para não criar salto absoluto falso.

Essa captura também demonstrou que a interpretação por segmento introduzida na
v2.0.6 estava errada: `0x4000` ficou zero em `s8`, e `0x7002` apenas alternou
`-40/40`. A revisão das instruções da ROM mostrou a fórmula exata usada antes dos
dois acessos: quatro `LSR`, `AND #$FFFE`, isto é,
`offset = 2 * floor(progress / 16)`. Em `0x7002+offset`, a ROM separa os bytes
alto e baixo, preserva o sinal e os compara com coordenadas laterais; portanto,
eles são candidatos fortes a limites laterais. O diagnóstico v3 usa esse índice,
registra os limites na escala de `0x1E8A`, inclui look-ahead, rank e adversário
mais próximo no mesmo frame. Ainda é necessário executá-lo ao vivo antes de
ativar offtrack, geometria ou telemetria de adversários no perfil.

### Captura v3: ultrapassagens, contatos e primeiro lugar

O arquivo recebido em 4 de setembro contém 3.600 frames consecutivos
(`4405..8004`), sem lacunas, com pré-largada, duas passagens pela linha e começo
da volta de índice 2. O usuário informou que ultrapassou, teve contato apenas com
carros, não bateu em placas e chegou à liderança. Os dados confirmam:

- o rank percorreu todos os valores de `19` a `0` em 23 transições: 21 posições
  ganhas e duas perdidas;
- `rank=0` permaneceu por 539 frames consecutivos, de `lap=2/progress=219` até o
  fim da captura em `progress=9186`;
- os 18 IDs de IA estiveram presentes em todos os 3.425 frames de corrida;
- houve 15 bordas do bit `0x0080`, totalizando 41 frames ativos;
- nos seis primeiros impactos havia um adversário a somente `18..56` unidades
  à frente. Os deltas laterais no impacto foram `1969`, `-716`, `-2849`, `4083`,
  `-65` e `2699`;
- a rotina da ROM compara a diferença lateral após dividi-la por dois com
  `0x0800`, equivalente a `4096` na escala original. Esse limiar abrange os seis
  contatos observados e substitui o candidato anterior `2048`;
- nove bordas posteriores ocorreram enquanto P1 estava em segundo/primeiro e o
  sensor não tinha carro estritamente à frente. Isso não contradiz o sensor
  preventivo: o contato pode ser lateral/traseiro. O diagnóstico v4 passa a
  registrar também o adversário longitudinalmente mais próximo em qualquer lado;
- o contador de volta repetiu um transiente de um frame (`1 → 2 → 1`) sem wrap
  de progresso. O reward agora calcula avanço pelo delta modular de progresso,
  portanto esse pulso não cria salto falso nem interrompe o rollout;
- dez dos 15 pulsos duraram menos que quatro frames. Como o agente publica um
  estado a cada quatro frames, a ponte agora acumula bordas em todos os frames e
  transmite `collision_events`, impedindo que impactos curtos desapareçam.

Com essa evidência, `opponent_telemetry_validated=true` e
`same_lane_half_width=4096`. A captura não chegou ao fim da corrida e não contém
`final_rank`; portanto, liderança viva foi validada, mas chegada/vitória final
ainda não. `profile_validated` permanece falso.

Os pares derivados de `0x7002` foram estáveis entre voltas, porém classificaram
584 frames como “fora”, inclusive longos trechos rápidos sem impacto. Eles não
são limites físicos confiáveis para `offtrack`. A revisão adicional da ROM
separou as funções: `0x4000` atua na física longitudinal, `0x4C00` é aplicado à
posição lateral, `0x5800` seleciona tipos/limites locais e `0x7002` participa das
rotinas de competidores. O diagnóstico v4 registra essas regiões separadamente;
nenhuma foi inserida na observação ainda.

O diagnóstico v4 também foi estendido para 5.400 frames (aproximadamente 90
segundos) e agora registra `final_rank_s16`, `total_laps` e
`finished_candidate`. Esses campos permitirão distinguir liderança durante a
corrida de chegada efetiva em primeiro na próxima captura.

### Captura v4: vitória final confirmada

A captura seguinte contém 5.400 frames consecutivos (`4232..9631`), sem
lacunas. A corrida tinha três voltas e o usuário informou ter chegado em
primeiro. No frame `8730`, os campos mudaram simultaneamente:

- progresso `22498 → 22`, confirmando o wrap da linha de chegada;
- volta `2 → 3`, igualando `total_laps=3`;
- `final_rank_s16: -1 → 0` e `finished_candidate: 0 → 1`;
- `final_rank_s16=0` permaneceu estável pelos 902 frames restantes.

O rank vivo chegou a zero 1.084 frames antes da chegada, após 21 posições
ganhas e duas perdidas. Isso valida separadamente liderança e vitória final. A
ponte principal já converte `final_rank=0` em `finished=1`; o ambiente termina o
episódio e o reward concede chegada, qualidade máxima e bônus exclusivo de
primeiro lugar.

Foram observadas seis bordas de impacto. Nas quatro primeiras, havia um carro
na mesma faixa a `10..46` unidades à frente. Nas duas últimas não havia
adversário próximo e P1 estava além do limite candidato positivo; isso é
compatível com cenário/placa, mas permanece inferência sem rótulo visual.

A configuração de controles do BizHawk associa a tecla física `S` a `P1 X` e a
tecla física `X` a `P1 A`. O usuário confirmou usar `S` para acelerar e consumir
os três nitros com `X`; portanto, `turbo_button=A` foi preenchido. A ação ficou
desabilitada até a conclusão dos dois testes causais descritos abaixo.

### Primeiro teste causal do turbo

O `diagnostico_turbo.csv` contém 302 linhas completas: 151 para acelerar sem
turbo e 151 para o ramo com um pulso de `P1 A`. Os dois ramos começaram no mesmo
frame e permaneceram idênticos até o comando. Dois frames após o início do
pulso, velocidade, progresso e `0x1E6C` divergiram simultaneamente:

- sem turbo: velocidade final `4119`, progresso `153` e `0x1E6C=0x0003`;
- com `P1 A`: velocidade final `6765`, progresso `404` e
  `0x1E6C=0xC703`;
- o ramo com turbo cruzou a linha de largada 15 frames antes.

Isso comprova causalmente que SNES `A` ativa o turbo. Também mostra que a leitura
`u16` de `0x1E6C` não é uma contagem simples: o bit de sinal é ativado e o campo
evolui como temporizador/perfil do impulso. A ROM inicializa o campo com `3`,
preserva os dois bits baixos durante o estado negativo e usa um valor reduzido
na exibição. Como o CSV terminou enquanto o campo ainda era negativo, a versão
seguinte prolonga os dois ramos, separa os bytes e registra candidatos explícitos
de turbo ativo e quantidade disponível. Naquele estágio, `enable_turbo`
permaneceu falso até a transição final ser observada.

### Diagnóstico estendido: término e consumo confirmados

O `diagnostico_turbo(1).csv` recebido em 5 de setembro contém 1.042 amostras:
521 no ramo de controle e 521 no ramo com pulso de SNES `A`. Não há lacunas nos
frames relativos. Os dois ramos partem do mesmo estado e somente o segundo aplica
turbo entre os frames relativos 160 e 163.

- o ramo de controle manteve `0x1E6C=0x0003` nos 521 frames;
- no ramo experimental, velocidade, progresso e `0x1E6C` divergiram juntos no
  frame 162;
- o estado ativo durou do frame 162 ao 481, inclusive;
- o campo percorreu `0x8003 ... 0xFF03` e, no frame 482, tornou-se `0x0002`;
- o ramo de controle terminou com velocidade `4288` e avanço modular `4880`;
- o ramo com turbo terminou com velocidade `7185` e avanço modular `5444`;
- ocorreram contatos durante os ramos, portanto a diferença final de desempenho
  não deve ser interpretada como medição isolada da potência; a ativação, o
  término e o consumo da carga não dependem dessa comparação final.

Isso valida que o bit 15 indica o impulso ativo e que os dois bits baixos
preservam a contagem anterior durante o impulso. A quantidade realmente
disponível é `low2 - 1` enquanto ativo e `low2` em repouso. A transição controlada
`3 -> 2` está comprovada; transições posteriores `2 -> 1 -> 0` ainda podem ser
registradas como confirmação adicional, mas não bloqueiam a ação porque o jogo
ignora tentativas sem carga e a rede recebe inventário e estado ativo separados.

Com essa evidência, `enable_turbo=true`, `nitro_scale=3`, o espaço passa a
`Discrete(10)` e a observação v3 recebe `nitro_norm` e `turbo_active`.

A simulação de API testa chamadas, laços, caminhos, CSVs, campos do protocolo e
tratamento de tipos. Ela **não** prova que um endereço representa uma variável do
jogo.

## Não verificável neste ambiente

- execução do BizHawk Windows com renderização e core SNES;
- conteúdo do savestate do slot 1, que não foi fornecido;
- correspondência ao vivo dos endereços com HUD e imagem;
- filtro de registros ativos da tabela de adversários;
- semântica/escala de combustível e marcha;
- confirmação adicional das transições de nitro `2 -> 1 -> 0`;
- curvas à direita e generalização da semântica do sinal para outras pistas;
- importação completa de Gymnasium, Stable-Baselines3 e PyTorch, ausentes no
  ambiente de auditoria;
- smoke test real, rollout PPO ou qualidade de aprendizagem.

Os itens ainda não verificados limitam a generalização para outras pistas, mas
não bloqueiam o smoke test de Las Vegas. Controles, adversários, chegada, turbo,
superfície/offtrack e a tabela de curvas dessa pista estão validados.
O bloqueio é um resultado correto da auditoria, não uma falha de instalação.

### Ponte TCP principal validada ao vivo

Em 5 de setembro, a revisão baseada em `client.unpause() + emu.yield()` completou
o fluxo principal. O estado inicial foi publicado no frame 4301, o reset do slot
1 foi confirmado no frame 4165 e três comandos neutros terminaram nos frames
4169, 4173 e 4177. Isso comprova `HELLO`, reset, `seq/ack` e delta fixo de quatro
frames. O Lua também registrou o recebimento e a conclusão do primeiro `STEP` e
o encerramento solicitado pelo Python.

### Rejeição quantitativa dos limites candidatos de `0x7002`

Na captura vencedora de 5.400 frames, 4.265 amostras pertenciam a voltas ativas
com velocidade positiva. Os pares derivados de `0x7002` classificariam 911
dessas amostras como fora da pista (21,4%). Também surgiram meia-largura zero e
trechos em que o jogador estava muito distante do intervalo candidato sem a
assinatura de uma saída real. Isso confirma quantitativamente que a tabela não
deve preencher `lateral_center`/`track_half_width`.

A próxima coleta é `diagnostico_offtrack.lua`: seis amostras visuais de asfalto,
seis fora à esquerda e seis fora à direita, em pontos diferentes. Ela procura
bits de WRAM correlacionados e mede a estabilidade da coordenada lateral. Os
resultados continuarão sendo candidatos até repetição causal.

A primeira interface desse diagnóstico usava as teclas físicas `N/F/G`. O teste
ao vivo mostrou que `F` conflita com **Frame Advance** e pode pausar o BizHawk.
A revisão seguinte removeu os atalhos e passou a usar três botões em uma janela
Lua própria; a lógica e os dados capturados não mudaram.

### Segunda coleta rotulada: candidato ternário reproduzido

A segunda coleta contém novamente seis amostras de pista, seis fora à esquerda
e seis fora à direita. Os rótulos foram intercalados e abrangeram dois inícios
de corrida. Ao cruzar as duas coletas, somente `0x0727` e `0x0A67`, entre todos
os 8.192 bytes varridos, mantiveram três classes perfeitas nas 36 amostras:
`0=esquerda`, `1=pista`, `2=direita`. Os dois endereços e as sete posições
vizinhas espaçadas por quatro bytes foram idênticos em todas as capturas.

O antigo candidato perfeito `0x1E96` falhou na coleta intercalada e a revisão da
ROM mostrou que ele é um acumulador atualizado por `0x1E9A`; `0x1ED8` é o
progresso já conhecido. Ambos foram descartados como falsos sensores. A etapa
seguinte registra `0x0727`/`0x0A67` a cada frame e exige confirmação visual das
transições nas duas bordas antes de integrar qualquer campo.

### Captura contínua: superfície validada e integrada

O `diagnostico_superficie.csv` recebido contém 3.600 frames consecutivos
(`4835..8434`), sem lacunas. O usuário confirmou que o overlay acompanhou
corretamente as entradas e saídas da pista. Em `0x0727` foram observados 487
frames com valor 0, 2.665 com valor 1 e 448 com valor 2, além de 17 transições:
cinco pista→esquerda, cinco esquerda→pista, quatro pista→direita e três
direita→pista. Não houve transição entre valores incompatível com esse ciclo.

As entradas à esquerda ocorreram com lateral mediana `-11232` e as entradas à
direita com mediana `11334`; as saídas voltaram por volta de `-10552` e `10529`.
Esses números descrevem a captura, mas não foram promovidos a limites globais:
o próprio byte ternário é a fonte mais direta e já incorpora a superfície local.

O candidato `0x0A67` divergiu do central em 51 frames. Uma comparação temporal
reduziu a divergência ao deslocar a série, evidenciando comportamento de buffer
secundário/atrasado. Por isso, somente `0x0727` entra na ponte.

Na v2.0.22, `surface_telemetry_validated=true`; o protocolo passou a publicar o
valor bruto, `offtrack` e a direção da saída. A observação v4 tinha 20 entradas e
o reward de offtrack passou a usar essa fonte nativa. Naquela etapa, o treino
continuava bloqueado porque a curva ainda não estava validada.

### Ponte com superfície confirmada e próximo diagnóstico

O teste real da v2.0.22 publicou `surface=1`, `direction=0` e `offtrack=0` no
estado inicial, após reset e em três ações neutras. Os frames avançaram
`4165 → 4169 → 4173 → 4177`, preservando o delta exato de quatro frames. A Lua
registrou superfície validada e encerrou a ponte por solicitação do Python.

A corrida vencedora anterior já mostra que cada índice observado em `0x4C00`
mantém o mesmo valor entre voltas. Na ROM, a rotina carrega
`$7E4C00,X`. A interpretação inicial foi `X=2*floor(progress/16)`; a coleta
completa posterior corrigiu-a para `X=2*floor(progress/32)`, equivalente a
`(progress >> 4) & 0xFFFE`. A rotina multiplica esse coeficiente e aplica o
resultado à lateral de P1. Isso comprova participação causal na física lateral,
mas ainda não define visualmente qual sinal significa esquerda/direita nem qual
look-ahead oferece antecipação suficiente ao agente.

Por isso, a v2.0.23 adiciona um diagnóstico rotulado de 18 amostras e compara
`+0`, `+256`, `+512`, `+1024` e `+2048` de progresso. A observação e o reward não
mudam nesta etapa; `curve_telemetry_validated` permanece falso até a captura.

O primeiro uso mostrou que a pista do savestate não possui curvas visuais à
direita. A v2.0.24 não exige nem aceita que o usuário invente essa classe: após
seis retas e seis curvas à esquerda, um botão registra explicitamente a ausência
da direção direita. O analisador aceita a coleta, mas declara cobertura parcial.
Isso pode ser suficiente para modelar a pista específica do treinamento; não é
evidência de generalização para outras pistas do jogo.

### Captura rotulada e revisão do acesso à curva

O `diagnostico_curva.csv` recebido contém seis retas e seis curvas à esquerda.
Os rótulos são espacialmente coerentes: as curvas foram marcadas em dois grupos,
nos progressos `5484..6687` e `14837..17912`; as seis retas ficaram fora desses
grupos. Velocidades iguais ou próximas de zero ocorreram porque o foco foi
movido para a janela de botões. Isso não invalida o endereço da pista, mas torna
a interface inadequada para novas coletas.

O score preliminar de 75% em `curve_1024` não libera a telemetria. A inspeção da
rotina da ROM mostrou dois detalhes que o primeiro diagnóstico não reproduzia:

- `0x1ED7` alimenta a posição suavizada de P1 em direct page `$46`; a tabela é
  indexada por `$46 >> 4`, não necessariamente pelo alvo instantâneo em movimento;
- a rotina carrega um word de `$7E4C00,X`, transfere-o para `X`, muda o acumulador
  para 8 bits e entrega somente o byte baixo ao multiplicador. Interpretar o par
  inteiro como um único `s16` mistura o coeficiente usado com o byte adjacente.

A v2.0.25 exportou 1.408 linhas porque interpretou incorretamente o alinhamento
`AND #$FFFE` como uma multiplicação posterior a `progress/16`. A fórmula real é
`(progress >> 4) & 0xFFFE`, equivalente a uma entrada a cada 32 unidades. Assim,
as primeiras 704 linhas da coleta já continham a tabela completa; as 704
seguintes liam dados posteriores e foram descartadas sem exigir nova captura.

Na tabela válida, 392 entradas são zero e 312 são positivas, em quatro regiões
de curva. O cruzamento corrigido por `floor(progress/32)` obteve 12/12:
seis retas com valor zero e seis curvas à esquerda com `16`, `24` ou `32`.
Isso valida direção e intensidade para Las Vegas. A v2.0.26 publica o valor
atual e look-ahead em 512, 1024 e 2048 unidades na observação v5. Naquele ponto,
o teste da ponte ainda era obrigatório antes de marcar `profile_validated=true`;
pistas com curvas à direita continuam exigindo validação própria.

### Ponte v5 e estado inicial ativo confirmados

O teste final foi executado com um novo savestate já em volta ativa. O estado
inicial publicou `lap=0`, `rank=19`, `surface=1`, `offtrack=0`, 18 adversários e
distância `1870` para o carro mais próximo à frente. O reset retornou ao frame
4453 com os mesmos invariantes e distância `1848`.

Três comandos neutros terminaram nos frames `4457`, `4461` e `4465`, mantendo
delta exato de quatro frames e `seq/ack` correto. Os quatro coeficientes de curva
foram publicados como `0/0/0/0` nesse trecho reto, sem erro de protocolo. A Lua
também confirmou todas as flags parciais. Com essa evidência,
`profile_validated=true` na v2.0.27 e o próximo teste permitido é o smoke test
curto do ambiente.

### Primeiro treino: estado bruto 255 após impacto externo

O smoke test completou 100 passos e confirmou as 24 observações, as dez ações,
reward positivo por progresso e penalidade offtrack nos passos 99–100. No
primeiro treino PPO, o agente saiu muito da pista, bateu em um cacto e, no passo
249, `WRAM 0x0727` assumiu o valor bruto `255`. O Lua anterior aceitava somente
`0/1/2` e encerrou a ponte com erro.

Esse evento não invalida `0x0727`: ele demonstra um estado adicional durante
impacto externo. A v2.0.28 publica `surface_raw=255` e `surface_unknown=1`, mantém
`offtrack=1` e deriva a direção pelo último lado válido ou pela lateral. O Python
valida que um estado desconhecido jamais seja apresentado como pista. A
observação permanece v5/24 campos, portanto não há mudança de arquitetura da
rede. O snapshot de 249 passos é apenas diagnóstico: PPO ainda não havia
completado o rollout `n_steps=2048` nem feito sua primeira atualização.
