> Atualização de 15/09/2026 após regressão: perfil ativo **road_v5_race / recompensa 7**. Removidos os incentivos experimentais que favoreciam adiar turbo; sensor e observação de 61 entradas preservados. **207 testes offline passaram; preflight real e comparação sem aprendizado pendentes.** [Análise do vídeo, correção e próximos comandos](REGRESSAO_RITMO_TURBO_20260915.md). As instruções anteriores de treino longo são históricas e não são o próximo passo.

> Atualizacao de 15/09/2026: perfil ativo **road_v4_driving / recompensa 6**, para treino do zero. Custo contextual para soltar acelerador e novo criterio de uso util/reserva de turbo. **202 testes offline passaram; novo preflight real pendente por mudanca de contrato.** [Mudancas, evidencias e comando de 500 mil passos](TREINO_DO_ZERO_RITMO_TURBO.md). Avisos anteriores abaixo sao historicos.

> Atualizacao operacional de 14/09/2026: navegacao inspirada no piloto nativo P2 integrada; **61 features/schema 10, detector 3, ponte 5**. Identidade P2 por offsets e corredor com espacos livres. **Novo preflight real pendente**, antes de treino. Modelos de 47 entradas exigem migracao explicita do ator. [Implementacao, evidencias e comandos](NAVEGACAO_NATIVA.md). Avisos e contagens anteriores abaixo sao historicos.

> Revisao atual:47features/schema9,detector2,ponte4. Corrigida associacao entre carro e risco.136 testes offline passaram; repetir preflight real apos esta correcao. [Evidencias e procedimento](REVISAO_DETECTOR_20260912.md).

> Versao operacional atual: detector integrado experimental,47features/schema8,ponte4.134 testes offline passaram; novo preflight real pendente. Veja [contrato e comandos](INTEGRACAO_DETECTOR.md). Instrucoes anteriores abaixo sao historico e nao autorizam retomar modelos de26features.

> Atualizacao local 11/09/2026: suporte experimental a save na contagem regressiva, observacao schema 7 (26 features), recompensa v4 e reset sem avancar frames. Ver [largada e proximo teste](LARGADA_CONTAGEM.md). 116 testes offline passaram; novo preflight real pendente. Historico abaixo preservado.

# Validação real da v3 e descoberta das memórias restantes

## Primeiro: preflight da base nova

Siga `README.md`, seções 1–3. O primeiro resultado para enviar é:

```text
C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\runs\preflight\preflight_DATA_HORA_MICROSSEGUNDOS.json
```

Essa execução testa cinco ramos a partir do mesmo slot e confere ações, observações e frames. Não precisa dirigir nem clicar em rótulos durante o teste. O fim do teste pausa o emulador por projeto. Não confundir essa pausa com tempo da corrida acabando.

Depois do preflight, pode executar o teste de300 ações e o treino de10240 do README. Não é necessário descobrir todas as memórias para começar a medir aprendizado da base conhecida. A v3 não traz um preflight fabricado marcado como aprovado.

## Descoberta complementar: uma corrida por coleta

O script novo `diagnostico_contexto.lua` não é o script de treino. Não execute ambos simultaneamente.

1. Termine o Python e feche a Lua Console antiga. Abra o BizHawk normalmente para jogar manualmente, sem precisar de servidor Python.
2. Abra a ROM da v3 e carregue um save em uma corrida. Para este diagnóstico, pode usar outro save; preserve o slot1 do preflight se quiser continuar o mesmo treino depois.
3. Execute somente:

```text
C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\lua\diagnostico_contexto.lua
```

4. Escolha o perfil em `C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\config\game_profile.ini`.
5. Jogue e observe o overlay com candidatos frontal/traseiro e número de frame. Os valores são **candidatos**, não detecção física já validada. Os botões da janela marcam TRASEIRA, FRENTE, PLACA/CACTO, TEMPO ZERO, CHEGADA e LADO A LADO.
6. Marque somente o evento que viu. O clique acontece depois do evento; seu frame é uma referência temporal aproximada. Se possível, grave a tela com o overlay e HUD. O CSV contínuo antes/depois do clique permite investigar o atraso; não atribuir causalidade exata ao instante do clique.
7. Clique **ENCERRAR E SALVAR**. Há também limite de7200 frames para não gerar captura ilimitada. A captura de RAM completa pode reduzir a velocidade do jogo; isso não é um benchmark de treino. Não recarregue save no meio; encerre e inicie outra coleta.

Os cinco arquivos têm o mesmo prefixo `contexto_DATA_HORA_FRAME`:

| Arquivo | Conteúdo |
|---|---|
| `.csv` | Jogador e sinais conhecidos por frame; distâncias candidatas frente/trás |
| `_racers.csv` | Vinte registros por frame: ID, lateral, progresso, volta bruta, movimento e flags brutas |
| `.wram.bin` | Snapshots de131072 bytes a cada60frames e em marcações |
| `_snapshots.csv` | Índice com frame, offset no binário, tamanho e motivo |
| `_marks.csv` | Rótulos manuais e frame do clique |

Todos ficam em:

```text
C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\runs\diagnostics
```

Compacte **os cinco do mesmo prefixo** e envie o ZIP. Acrescente uma frase dizendo quais eventos ocorreram e se havia carro de outra volta. Se houver vídeo, envie o trecho correspondente. Esses dados serão comparados; não é necessário pedir autorização para prosseguir com a análise.

## Ordem dos experimentos de memória

| Experimento | Execução discriminante | Critério para validar |
|---|---|---|
| Carro atrás | P1 lento no asfalto; adversário se aproxima por trás, fica lado a lado e passa. Repetir com um adversário uma volta à frente | ID estável, distância circular negativa→zero→positiva, lateral coerente com tela, sem salto de22528 no cruzamento da volta |
| Carro à frente | Aproximar sem contato, desviar e passar; repetir em três posições laterais | Distância diminui com mesmo ID; derivada muda quando P1 afasta; faixa acompanha posição visual |
| Contato traseiro | P1 lento/reto, atingido por trás; registrar velocidade antes/depois e bit genérico | Mesmo adversário plausível antes/durante impacto, rótulo visual e hipótese distinguível de contato frontal. Repetir≥5 exemplos, manter classe desconhecida quando ambígua |
| Contato frontal/obstáculo | Coletas separadas para carro e placa/cacto | Comparar registros/flags que mudam em ambos e os que distinguem. Uma queda de velocidade sozinha não identifica origem |
| Tempo | Capturar HUD desde corrida ativa até tempo zero, uma coleta sem gastar combustível rapidamente e outra pilotando | Candidato acompanha decremento do HUD, pausa, possível recarga em voltas e zero; não apenas correlação com combustível |
| Chegada | Corrida completa com lap2→3 e resultado final | Coletar agora também superfície, tempo candidato e entidades; isso permitirá contrafactual de recompensa completo |
| Obstáculo preventivo | Aproximação sem impacto e passagem do mesmo objeto por lados diferentes | Entidade/posição detectável antes da batida; negativo em pista livre; não confundir sprite com coordenada física |

Critério de cobertura: pelo menos duas corridas independentes, múltiplas voltas, as duas direções relativas frente/trás e exemplos negativos sem contato. Para sensores de segurança, reservar cenas que não foram usadas para escolher offsets/limiares. Documentar falsos positivos/negativos; não escolher uma máscara porque “os números parecem certos”.

## Análise local opcional dos snapshots

Deixe os cinco arquivos juntos. O comando abaixo escolhe o binário mais recente e seu índice correspondente, sem você digitar o nome com data:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0"
$captura = Get-ChildItem .\runs\diagnostics -File -Filter "contexto_*.wram.bin" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $captura) { throw "Nenhuma captura encontrada em runs\diagnostics" }
$indice = $captura.FullName.Replace(".wram.bin", "_snapshots.csv")
.\.venv\Scripts\python.exe python\analyze_context.py --binary "$($captura.FullName)" --index "$indice"
```

Saída: `runs\diagnostics\candidatos_DATA_HORA_MICROSSEGUNDOS.json`. O analisador prioriza bytes com tendência decrescente, verifica tamanho/offset e rejeita retorno de frames. **Não declara nenhum deles como timer.** Pode destacar combustível ou animação; tempo também pode estar em u16, BCD ou contador composto e não aparecer no ranking. A descoberta completa exige ler os eventos, a ROM e a tela.

Sem candidatos discriminantes na WRAM, o próximo diagnóstico deve incluir a tabela de objetos ou leitura de OAM/VRAM fornecida pelo core. Ainda não foi escrito um endereço de obstáculo no perfil. Não é seguro substituir isso por distâncias imaginadas a partir de um sprite.

## Liberação e evolução

Depois de validar sensores novos, modificar nesta ordem: mapa de memória/perfil, leitura Lua, parser/Telemetry, observação/máscaras, testes, contrato e relatório. Mudou significado/ordem/dimensão? Incrementar versão formal da observação/ação/reward. Só então iniciar treino compatível. As funções ainda não validadas não devem entrar na política escondidas atrás de um `validated=true` manual.

Repetir preflight quando mudar a ponte, ambiente, reward, perfil ou save. Diagnóstico isolado adicionado não invalida treino por si só. O plano busca reduzir pedidos de coleta repetidos, mas não substituir evidência real por teste simulado.
