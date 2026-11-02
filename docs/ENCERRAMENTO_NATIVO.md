> Comparação real concluída em 13/09/2026: episódio 249 reproduziu a vitória (lap=3, resultado=0, primeiro na lista de chegada), enquanto episódio 270 confirmou o corte com 10 finalistas antes da chegada de P1. A regra atual separou corretamente esses dois casos. Não foi adicionado tempo artificial. **Próximo passo: preflight_live.py com o Lua principal para os arquivos atuais**, antes do piloto do novo objetivo de turbo. Os candidatos nativos adicionais continuam restritos ao diagnóstico. [Evidências](ENCERRAMENTO_NATIVO.md). Avisos de testes pendentes abaixo são históricos.

> Atualização após captura real: o relatório `finish_replay_20260913_143716_109800.json` completou o replay e registrou 5.721 frames consecutivos com o Lua corrigido (hash conferido). **Corte por 10 finalistas confirmado no episódio 270**, em conjunto com a rotina de aceleração da ROM. A validação da chegada normal será feita no episódio 249, que foi conferido no registro: 1.143 ações, lap=total_laps=3, final_rank=0 no frame 9744. Ainda não integrar os candidatos ao treino nem declarar novo preflight aprovado.

# Encerramento nativo: evidência e teste pendente — 13/09/2026

Base exclusiva v3.0, ROM SHA-1 F686806C676A4B087A3627BABBE3555D3704E3B1.
Os endereços abaixo pertencem ao jogo em WRAM. O código do emulador executa a
ROM e permite observar essa memória; alterar o emulador não revela automaticamente
a semântica de cada endereço. Nenhum byte da ROM, savestate ou modelo foi alterado.

## Evidência real recebida

`runs/diagnostico_termino/finish_replay_20260913_141058_261551.json` concluiu o
replay de 1.370 ações do episódio 270 com telemetria idêntica à gravação original,
seguido de 240 frames com aceleração, sem reset.

| Momento | Frame BizHawk | Volta | Resultado publicado, base zero | Velocidade bruta |
|---|---:|---:|---:|---:|
| Primeira publicação | 10652 | 2 | 11 (12º) | 8211 |
| Cruzamento posterior | 10764 | 3 | 10 (11º) | 3877 |
| Fim da captura | 10892 | 3 | 10 (11º) | 1339 |

O usuário também forneceu imagem com **RACE OVER** e 11º lugar. A imagem não
contém frame de diagnóstico para alinhar exatamente sua exibição ao JSON.
O resultado 0x1F00 pode mudar depois da primeira publicação. Movimento e cruzamento
posteriores não demonstram, sozinhos, que o jogador ainda podia acelerar ou
que a chegada posterior deve ganhar recompensa. Afirmar que a primeira publicação
é um resultado final imutável foi incorreto.

## O que a análise estática da ROM demonstrou

Foi usado somente o disassembler de leitura que já acompanha a v3.0 em
`archive/tools/disasm65816.py`; não foi restaurada implementação antiga.
Trechos e hash da ROM estão em
`runs/maintenance/native_finish_20260913_112516/rom_finish_disassembly.txt`.
Endereços de instrução abaixo são CPU/LoROM, diferentes dos offsets WRAM.

- **00:877D–00:87B2:** compara WRAM `0x1EB0` com 10. Se maior ou igual e P1 ainda
  não tem resultado, copia rank atual para `0x1F00` e agenda mensagem 5 em `0x0118`.
- **05:D4B0–05:D4B6:** mesmo com aceleração solicitada, compara `0x1EB0` com 10
  e desvia para o caminho de desaceleração em 05:D529. O teste seguinte trata
  combustível zero. Portanto, existe um corte de aceleração por esse contador.
- **00:A1E4–00:A1F9:** quando um adversário cruza o total de voltas, grava seu ID
  na lista iniciada em `0x1F12` e incrementa `0x1EB0`. Isso sustenta a interpretação
  de contador de finalistas, em vez de cronômetro.
- **05:E7AB–05:E823:** ao cruzar o comprimento da pista, atualiza volta; na volta
  final escreve `0x1EB0` em `0x1F00`, registra ID 0 na ordem de chegada e incrementa
  o contador. Esse caminho pode sobrescrever resultado já publicado. É compatível
  com 12º → 11º observado no replay, sem provar recuperação do controle.
- **00:DB75–00:DB81:** uma mensagem pendente 5 se transforma em ID 35. A ligação
  visual exata desse ID com RACE OVER continua pendente de captura ao vivo.

**Hipótese forte para o episódio 270:** o décimo finalista chegou antes de P1,
o jogo cortou sua aceleração e publicou resultado; o carro cruzou depois por
movimento residual. Ainda falta medir o contador naquele episódio. Não foi
demonstrado que aumentar o episódio para 1:33 permitiria continuar competindo.

## Candidatos coletados, sem entrada no treino

| WRAM | Tipo | Papel na investigação / limite |
|---|---|---|
| 0x1EB0 | u16 | Contador de finalistas e corte >=10; análise estática forte, ao vivo pendente |
| 0x1EB4 | u16 | Máscara alterada ao terminar/ficar sem combustível; não é isoladamente game over |
| 0x1F12..0x1F25 | 20 bytes | Lista de IDs de chegada; considerar apenas entradas já preenchidas pelo contador |
| 0x1E58 | s16 | Fase da lógica; também usado em pausa/inicialização, não é flag exclusiva de término |
| 0x1EF2 / 0x1EF3 / 0x1EF5 | word/bytes | Estados auxiliares de controle/flags; bits restantes não identificados |
| 0x1EE0 | u16 | Contagem de transição no loop; não é o cronômetro do HUD |
| 0x0118 / 0x0124 / 0x0128 | u16/s16/u16 | Mensagem pendente, ID e estado de exibição |
| 0x1EAE / 0x1F26 | u16 | Valores usados na rotina de chegada; unidade e correspondência com HUD não validadas |

A coleta também mantém volta, rank, resultado, velocidade, combustível, progresso
e total de voltas por frame. Não promove nenhum candidato a feature nem altera
terminação, recompensa, contrato de modelos ou preflight. A correção de recuperação
do erro de lap e o ajuste experimental de turbo da revisão anterior permanecem.

## Próximo teste real, automático

Feche a sessão anterior do BizHawk. No primeiro terminal PowerShell:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\diagnose_finish_live.py --native-probe
```

Depois de aparecer **Servidor em**, abra outro terminal:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Abra Top Gear (USA), e em Tools → Lua Console abra **somente**:

`C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0\lua\diagnostico_fim_corrida.lua`

Não carregue outro Lua junto nem dirija. O teste carrega o mesmo slot 1, reproduz
as ações sozinho, confere a gravação original, observa mais 240 frames e pausa.
Não salve por cima do slot 1. O relatório novo é criado em `runs/diagnostico_termino`;
não substitui os anteriores. O modo exige esse Lua, que por sua vez recusa HELLO
normal de treino, evitando mistura acidental.

Depois da coleta, comparar primeiro resultado, décimo finalista, mensagem e
cruzamento, e conferir o caminho de chegada normal em outra corrida registrada
se necessário. Só então integrar um motivo nativo de encerramento, com proteção
contra premiar cruzamento após eliminação. Não usar um tempo fixo como substituto.

## Verificação offline

Os testes executam o Lua de captura com APIs simuladas e comparam comandos,
frames, reset e telemetria original com a ponte principal. Também cobrem recusa
do HELLO de treino, histórico limpo no reset, pacotes incompletos, resumo que
mantém corte e chegada tardia separados, e replay Python completo com proveniência.
Esses testes não validam a memória no BizHawk. A captura nativa real acima está
pendente; não iniciar outro treino longo antes de resolver o encerramento e
obter novo PREFLIGHT OK para os arquivos atuais.

Verificação desta revisão: **160 testes offline passaram em 11,735 segundos**, sem falhas ou testes ignorados, na .venv Windows/Python 3.11.9 da v3.0. Registro: `runs/maintenance/native_finish_20260913_112516/test_results.json`. Captura nativa no BizHawk real pendente.

### Correção de carregamento NLua

O BizHawk real carregou o diagnóstico como `[string "main"]`, sem caminho no debug. Removida a exigência de origem `@arquivo`. O diagnóstico agora procura a ponte pela pasta disponível e, se necessário, pede o `config/game_profile.ini` da v3.0. A regressão foi reproduzida em Lua simulado com diretório externo; 161 testes offline passaram em 8,002 segundos. Repetir o teste real; nenhum sinal de término foi validado por essa correção.

## Captura nativa real recebida

- Frame 10649: `0x1EB0=10`, lap=2, resultado=-1. P1 não está nas dez entradas preenchidas da lista de chegada.
- Frame 10651: lap=2, resultado=11 (12º), mensagem pendente=5, velocidade=8223.
- Frame 10652: ID de mensagem=35, velocidade=8211; começa a queda observada apesar da aceleração.
- Frame 10763: lap=3, resultado=10 (11º), P1 entra na lista na posição 10 (base zero), velocidade=3877.

O cruzamento ocorreu 112 frames depois da publicação inicial. A análise da ROM já mostrou que o contador >=10 desvia a aceleração para desaceleração. Portanto, neste episódio o encerramento da disputa vem do jogo; prolongar a coleta não restaura a aceleração. Não confundir a animação/movimento posterior com tempo adicional de competição. A frase anterior de que reset na primeira publicação necessariamente interrompia uma corrida ainda ativa não é sustentada neste caso.

A contagem de finalistas e o resultado final não são o cronômetro do HUD. A captura da chegada normal precisa confirmar que um término legítimo (especialmente próximo ao décimo colocado) não será classificado como corte. Detalhes e hashes: `runs/diagnostico_termino/native_review_20260913_143716.json`.

Próxima execução: `python/diagnose_finish_live.py --native-probe --episode 249`, usando a .venv local e o mesmo Lua de diagnóstico. Repete automaticamente a vitória gravada, sem modelo, aprendizado ou alteração no slot 1. A conclusão dessa nova execução ainda está pendente.

## Comparação real: vitória do episódio 249

Relatório `finish_replay_20260913_144228_135307.json`, status completed, 1.143 ações reproduzidas exatamente e mais 240 frames. Captura de 4.813 frames consecutivos, hashes do Lua principal e diagnóstico conferidos.

No frame 9743: lap=2, resultado=-1, contador de finalistas=0.
No frame 9744: lap=3, total_laps=3, resultado=0, contador=1, primeira entrada da lista=ID 0 (P1), máscara ativa=2, byte auxiliar P1=255. Não houve contador >=10 nem mensagem 35 no trecho capturado. A máscara/byte auxiliar mudam também na chegada tardia; portanto, isoladamente não distinguem vitória de eliminação.

O término atual na primeira publicação de resultado aceitou essa chegada e rejeitou a chegada incompleta do episódio 270. Os dois replays não demonstram um corte antecipado pelo Python enquanto a aceleração permanecia disponível. Não se amplia a corrida até 1:33 nem se concede recompensa pela chegada posterior à eliminação. A memória adicional permanece no diagnóstico, sem mudança no contrato ou na observação. Este escopo não equivale a validação de todos os modos de jogo, chegada simultânea ao décimo finalista ou cronômetro do HUD.

Próximo passo operacional: novo `python/preflight_live.py`, com **lua/Top Gear (USA).lua**, não o Lua de diagnóstico. Isso verifica reset/controles/detector e registra o contrato atual. Só após PREFLIGHT OK, executar o piloto de 10.240 passos de `scripts/ajustar_turbo_detector.ps1`; a mudança experimental de recompensa ainda precisa ser avaliada. Nenhum treino foi iniciado nesta análise.
