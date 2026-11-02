# Implementação experimental — primeiro teste do câmbio manual

Implementados `lua/diagnostico_cambio_manual.lua` e
`python/analisar_cambio_manual.py`. Não há integração no PPO nesta etapa: o teste
valida a resposta mecânica aos comandos antes de decidir pontos de troca.
Configuração operacional, modelo, ponte TCP e save automático permanecem intactos.

**Atualização solicitada pelo usuário: slot 2 para o experimento manual.** O Lua
carrega exclusivamente o slot 2; nunca salva nem carrega o slot 1. Uma eventual
adoção definitiva no slot 1 só ocorrerá depois de demonstrar vantagem, preservando
antes uma cópia identificada do save automático. Não foi substituído nenhum save.

1. Pare o Python atual com Ctrl+C e feche o BizHawk. Abra sem socket:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe"
```

2. **Se já criou o slot 2 MANUAL, mantenha esse save e pule para o passo 4.**
   Caso contrário, abra a ROM. No menu inicial, entre na configuração de **1 PLAYER** e selecione
   **MANUAL**, controle **TYPE A**, o mesmo carro e a mesma pista Las Vegas dos
   testes anteriores. Se abrir um save automático, a transmissão continuará
   automática; comece essa corrida pelo menu. Não sobrescreva o slot 1 existente.
3. Pause na largada/contagem ou no GO, ainda em primeira e baixa velocidade, e
   **salve no slot 2** pelo menu de savestates do BizHawk. Mantenha o vermelho
   neste primeiro teste para separar câmbio de carro. O slot 1 fica automático.
4. Em Tools → Lua Console, pare todos os outros scripts e abra
   `lua\diagnostico_cambio_manual.lua`. Quando o seletor aparecer, escolha
   `config\game_profile.ini` da pasta operacional v3.0.
5. Deixe o emulador rodar/despause se necessário. Não é preciso dirigir nem
   clicar durante o teste. Ele acelera com X, espera velocidade bruta de pelo
   menos 1500 por oito frames consecutivos e só então inicia os sete pulsos de
   R/L em 480 frames (aproximadamente oito segundos de jogo, além da largada).
   A espera tem limite de 1200 frames; sem movimento, encerra com erro e preserva
   a coleta. Não usa nitro. O overlay informa a fase de espera/teste,
   frame, comando, marcha bruta e valor candidato a conta-giros. Observe se a
   marcha no HUD acompanha as trocas; a barra ainda precisa de correlação visual.

Sequência v2: depois da espera, mantém primeira por mais 60 frames; sobe quatro
vezes, reduz, sobe e reduz. Pulsos nos frames 60, 120, 180, 240, 300, 360 e 420
da sequência, cada um com quatro frames de botão pressionado e liberação entre
pulsos. O CSV registra `capture_version=2`, `phase=0` na espera e `phase=1` no
teste, `sequence_frame=-1` na espera e 0..479 no teste. `relative_frame` continua
desde o início da coleta. O limite de velocidade é apenas um critério operacional
de movimento: não identifica GO, RPM nem o ponto ideal de troca. A sequência não
é uma estratégia de corrida nem um teste de aceleração máxima: seus tempos
foram escolhidos para separar efeitos de comandos. Não há escrita em WRAM nem
gravação de savestate: há somente carregamento do slot 2 no início. Ao terminar/interromper, os botões são liberados e o
CSV preservado em `runs/diagnostics/cambio_manual_*.csv`.

Depois da mensagem `COLETA CONCLUIDA`, analise no PowerShell:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\analisar_cambio_manual.py
```

O analisador seleciona o CSV mais recente e cria relatório com nome único. Ele
exige captura completa, espera por movimento na v2, continuidade de frames/marcha, comandos previstos,
primeira marcha sem troca espontânea e exatamente uma troca na direção esperada
por pulso e os cinco estados brutos 0..4. Isso nao comprova sozinho os números
exibidos no painel GEAR. Mantém suporte ao cronograma legado
para analisar CSVs antigos sem reinterpretá-los como a nova coleta.
`controls_observed_ok` significa que a sequência foi observada no
arquivo; **não** valida escala RPM, momento ideal, vantagem de desempenho ou treino.
Se falhar, investigamos o relatório sem alterar limiares para fazê-lo passar.

Dados: marcha bruta 0x1E72 já existente; candidato a conta-giros 0x1E5E e máscaras
0x1F7A/0x1F7C permanecem diagnósticos. Contexto está na pesquisa em
`runs/analysis/transmission_20260915/RELATORIO.md`. Também registra velocidade,
superfície, impacto, nitro, combustível e volta para identificar interferências.

## Primeira coleta real e correção do diagnóstico

A coleta `cambio_manual_20260915_165856_26181_0.csv` respondeu corretamente a
seis dos sete pulsos. O primeiro R, nos frames relativos 180..183, ocorreu com
velocidade bruta 1 e marcha 0; o movimento apareceu no frame 197 (velocidade 237).
As seis trocas posteriores ocorreram nos frames 301, 422, 542, 662, 780 e 900.
A quinta marcha não foi alcançada nessa sequência. O relatório original continua
reprovado e foi preservado. A falha motivou a espera por movimento da v2.
Não usamos `lap>=0` como condição: a primeira troca real bem-sucedida ocorreu
com `lap=-1`. A barra candidata variou entre 96 e 4064; isso não calibra RPM.

Os testes automatizados executam o Lua real com API simulada e verificam
trocas manuais, largada atrasada, espera consecutiva, limite sem movimento,
carregamento exclusivo do slot 2, recusa de slot ausente, seleção automática,
captura incompleta, pulso ignorado e rejeição da falha legada.
A coleta real v2 `cambio_manual_20260915_192142_26181_0.csv` passou nas sete
respostas R/L: espera de 253 frames seguida de 480 frames de sequência,
estados brutos 0..4, sem bit de impacto 0x80 nem superfície fora do asfalto.
SHA-256: `9fb79d6bb405030650e17083b42cea9becd12c1e32915fa867b6cca61b314ad9`.

**Divergência visual relatada pelo usuário:** ele viu no máximo GEAR 4 no painel
original. A coleta registra valor bruto 4 nos frames 494..553 e 614..673; termina
em bruto 3 após a última redução. Esses fatos não resolvem a correspondência
visual. A afirmação anterior de que a quinta marcha estava confirmada foi
prematura. `controls_observed_ok` continua significando respostas em memória;
`hud_mapping_validated=false` explicita que o painel ainda precisa ser conferido.

Para esclarecer, o mesmo Lua agora salva **oito PNGs automaticamente**: um na
sequência 0 e um 24 frames após cada pulso. O arquivo `_hud.tsv` ao lado do CSV
liga cada PNG ao frame relativo, frame do emulador, sequência e estado bruto.
Os nomes incluem `_hud_f<frame>_raw<valor>.png`; nenhuma captura anterior é
sobrescrita. A captura usa `client.screenshot`, da
[API oficial do BizHawk](https://tasvideos.org/Bizhawk/LuaFunctions#clientscreenshot).
Se a captura falhar, o teste libera botões, encerra com erro e preserva o CSV.
Não é necessário gravar a tela, tirar prints ou tocar nos controles.

**Próximo passo atual:** repetir este Lua e o comando de análise acima para
confrontar os PNGs do painel com os estados brutos, antes do ensaio de desempenho.
O analisador lista as imagens e seus hashes, mas não faz reconhecimento visual
automático nem promove a validação do HUD. Não foi integrado controle manual ao
PPO. Os testes automatizados verificam chamadas e índices de captura com API
simulada; ainda não validam os PNGs no BizHawk real.

## Correspondência visual confirmada em 15/09/2026

Na coleta `cambio_manual_20260915_192807_26181_0.csv`, as oito imagens foram
inspecionadas diretamente. Frames relativos 253, 337, 397, 457, 517, 577, 637 e
697 mostram, no painel do jogador superior, GEAR **1, 2, 3, 4, 5, 4, 5, 4**.
Os valores brutos correspondentes são **0, 1, 2, 3, 4, 3, 4, 3**. O usuário
também confirmou visualmente a quinta. Fica resolvida a divergência anterior:
**marcha exibida = valor bruto de 0x1E72 + 1** nesta configuração.

A sequência R/L passou novamente e o CSV é idêntico em conteúdo ao da coleta
anterior, com SHA-256 `9fb79d6bb405030650e17083b42cea9becd12c1e32915fa867b6cca61b314ad9`.
A revisão visual com hashes está em `runs/analysis/transmission_20260915/`.
O analisador genérico continua sem promover validação visual automaticamente:
o recibo separado se aplica a esta coleta, não a qualquer CSV futuro.

**Próximo passo:** [ensaio local de aceleração](ENSAIO_CAMBIO.md). Não é preciso
repetir o diagnóstico de correspondência nem recriar o slot 2.
