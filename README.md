> Pacote para outro PC (06/10/2026): comece por [LEIA_PRIMEIRO_OUTRO_PC.md](LEIA_PRIMEIRO_OUTRO_PC.md). O azul automatico/save 3 usa road_v6_outcome/11: multa de -1,00 por posicao perdida, multa maior por imobilidade e premio de +1,00 por nova melhor posicao. Mesmo cerebro e mesmos comandos; repetir o preflight real dos arquivos atuais. [Perda de colocacao e continuidade](docs/PERDA_COLOCACAO_20261014.md). [Revisao de 12/10](docs/RECOMPENSAS_PARADO_ULTRAPASSAGEM_20261012.md). [Estado do turbo](docs/TURBO_APRENDIDO_20261006.md).

> 30/09/2026: piloto manual de mais 26.624 passos e avaliacao real concluidos. O refinado ficou em 7º contra 4º da origem na corrida deterministica; nove corridas variadas validas nao mostraram melhora de colocacao, e uma teve telemetria invalida reproduzida. Checkpoints intermediarios tambem nao superaram a origem. O modelo recomendado nesta comparacao continua o de 263.179 passos; nao prolongar automaticamente o refinamento. [Resultados e diagnostico](docs/REFINAMENTO_MANUAL_20260928.md).

> 28/09/2026: comparacao real favoreceu o checkpoint manual de 263 mil (9/10 chegadas) sobre o final de 500 mil (5/10). Refinamento separado com learning_rate 0.0001, preservando pesos, critico e Adam; 258 testes passaram e novo preflight real aprovado. [Evidencias, piloto e comandos](docs/REFINAMENTO_MANUAL_20260928.md).

> **Somente jogar, repetidamente e sem treinamento:** `python\jogar_continuo.py`. Usa o modelo anterior escolhido, mesma pista e decisões variadas da política aprendida. [Comandos e funcionamento](docs/SOMENTE_JOGAR.md).

> Atualização de 15/09/2026 após regressão: perfil ativo **road_v5_race / recompensa 7**. Removidos os incentivos experimentais que favoreciam adiar turbo; sensor e observação de 61 entradas preservados. **207 testes offline passaram; preflight real e comparação sem aprendizado pendentes.** [Análise do vídeo, correção e próximos comandos](docs/REGRESSAO_RITMO_TURBO_20260915.md). As instruções anteriores de treino longo são históricas e não são o próximo passo.

> Atualizacao de 15/09/2026: perfil ativo **road_v4_driving / recompensa 6**, para treino do zero. Custo contextual para soltar acelerador e novo criterio de uso util/reserva de turbo. **202 testes offline passaram; novo preflight real pendente por mudanca de contrato.** [Mudancas, evidencias e comando de 500 mil passos](docs/TREINO_DO_ZERO_RITMO_TURBO.md). Avisos anteriores abaixo sao historicos.

> Atualizacao operacional de 14/09/2026: navegacao inspirada no piloto nativo P2 integrada; **61 features/schema 10, detector 3, ponte 5**. Identidade P2 por offsets e corredor com espacos livres. **Novo preflight real pendente**, antes de treino. Modelos de 47 entradas exigem migracao explicita do ator. [Implementacao, evidencias e comandos](docs/NAVEGACAO_NATIVA.md). Avisos e contagens anteriores abaixo sao historicos.

> Comparação real concluída em 13/09/2026: episódio 249 reproduziu a vitória (lap=3, resultado=0, primeiro na lista de chegada), enquanto episódio 270 confirmou o corte com 10 finalistas antes da chegada de P1. A regra atual separou corretamente esses dois casos. Não foi adicionado tempo artificial. **Próximo passo: preflight_live.py com o Lua principal para os arquivos atuais**, antes do piloto do novo objetivo de turbo. Os candidatos nativos adicionais continuam restritos ao diagnóstico. [Evidências](docs/ENCERRAMENTO_NATIVO.md). Avisos de testes pendentes abaixo são históricos.

> Revisão de 13/09/2026: replay real mostrou mudança do resultado após sua publicação. A ROM contém corte de aceleração com 10 finalistas; correspondência no episódio ainda depende de captura. **Próximo passo: diagnóstico nativo automático, não treino longo.** [Evidências e comando](docs/ENCERRAMENTO_NATIVO.md). Instruções de treino e interpretações de término anteriores abaixo são históricas.

> Atualização do turbo: perfil ativo **road_v3_turbo / recompensa 5**, custo por carga real e desperdício fora da pista. Ator road_v2 reaproveitado somente por inicialização explícita; retomada comum incompatível é recusada. **153 testes offline passaram**; diagnóstico de término e novo preflight real pendentes. [Mudanças, evidências e comandos](docs/TURBO_E_ENCERRAMENTO.md). Avisos anteriores abaixo são históricos.

> Atualização de 12/09/2026: recuperação limitada da regressão de lap, diagnósticos completos e médias de 100 episódios no TensorBoard. **143 testes offline passaram** na .venv Windows/Python 3.11.9; novo preflight real pendente após alteração do ambiente. Contrato preservado: 47 features/schema 9, detector 2, ponte 4. [Análise do treino e comandos de retomada](docs/REVISAO_TREINO_369308.md). Os avisos anteriores abaixo são históricos.

> Revisao atual:47features/schema9,detector2,ponte4. Corrigida associacao entre carro e risco.136 testes offline passaram; repetir preflight real apos esta correcao. [Evidencias e procedimento](docs/REVISAO_DETECTOR_20260912.md).

> Versao operacional atual: detector integrado experimental,47features/schema8,ponte4.134 testes offline passaram; novo preflight real pendente. Veja [contrato e comandos](docs/INTEGRACAO_DETECTOR.md). Instrucoes anteriores abaixo sao historico e nao autorizam retomar modelos de26features.

> Atualizacao local 11/09/2026: suporte experimental a save na contagem regressiva, observacao schema 7 (26 features), recompensa v4 e reset sem avancar frames. Ver [largada e proximo teste](docs/LARGADA_CONTAGEM.md). 116 testes offline passaram; novo preflight real pendente. Historico abaixo preservado.

# TCC-TopGear-RL v3.0

Base consolidada para treinar PPO no Top Gear (USA), em Las Vegas, com BizHawk 2.11.1. O aprendizado acontece por observação, ações e recompensa; não há piloto pronto embutido. Esta versão ainda precisa do primeiro teste ao vivo da ponte v3. O relatório técnico está em `docs/RELATORIO_TECNICO.md`.

## 1. A pasta que você abre no VS Code

Descompacte **TCC-TopGear-RL_v3.0.zip** em Downloads. Abra a pasta que contém diretamente `README.md`, `requirements.txt`, `python`, `lua`, `config` e `tests`:

```text
C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0
```

Se o Windows criar duas pastas com o mesmo nome, entre na interna que contém esses arquivos. Não execute o projeto dentro da visualização do ZIP, que mostra “Extrair tudo”. Não cole a v3 sobre a v2. A v3 usa sua própria `.venv`; as pastas anteriores continuam preservadas.

A ROM que você enviou está em `assets\rom\Top-Gear-USA.sfc`, com os bytes originais e SHA-1 conferido. O BizHawk continua na instalação que você já tem. O slot 1 precisa ser salvo nessa instalação; nenhum savestate operacional foi fornecido neste pacote.

## 2. Instalação desde o zero — Terminal PowerShell do VS Code

Abra **Terminal → Novo Terminal**. Execute os comandos abaixo, um por vez:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0"
py --list-paths
py -3.11 --version
```

O último precisa mostrar Python **3.11.x**. Se disser `No suitable Python runtime found`, instale o Python 3.11 de 64 bits pelo [instalador oficial 3.11.9 para Windows](https://www.python.org/downloads/release/python-3119/), feche e reabra o terminal e repita a verificação. Não use Python 3.14 neste projeto.

Depois:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip==25.3
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe python\verify_install.py --manifest
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`requirements-dev.txt` já instala as dependências de treinamento e o interpretador usado pelos testes Lua simulados. O PyTorch para CPU é grande; a primeira instalação pode demorar. Não precisa baixar CUDA, torchvision ou bibliotecas toda vez que abrir o VS Code.

Todos os comandos usam explicitamente o Python da `.venv` desta pasta. Isso resolve a confusão recorrente de `numpy` instalado em outro Python. No VS Code: **Ctrl+Shift+P → Python: Select Interpreter → Enter interpreter path → Find**, escolha:

```text
C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\.venv\Scripts\python.exe
```

A ativação é opcional: `& .\.venv\Scripts\Activate.ps1`. Se o PowerShell a bloquear, continue com os comandos completos acima; não é necessário mudar a política de execução. `scripts\setup.ps1` automatiza a mesma instalação para quem já consegue executar scripts PowerShell.

Espere `INSTALACAO OK` e testes terminando em `OK`, sem testes Lua ignorados. Se algum falhar, devolva a saída completa. `verify_install --manifest` confere o pacote original; depois de uma atualização intencional, use o manifesto atualizado.

## 3. Primeiro teste ao vivo: comunicação, reset e controles

Não inicie treino longo antes deste teste. Ele dura somente **60 ações e cinco resets**, mais o tempo de abrir o jogo. Não altera modelo.

**Terminal 1**, na raiz da v3:

```powershell
.\.venv\Scripts\python.exe python\preflight_live.py
```

Ele abre o servidor local e espera o emulador. Deixe esse terminal aberto.

**Terminal 2**, aberto pelo botão `+` do terminal do VS Code:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Feche outras instâncias do BizHawk antes de usar essa. No BizHawk:

1. **File → Open ROM**: abra `C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\assets\rom\Top-Gear-USA.sfc`.
2. Entre na primeira corrida, Las Vegas. Use transmissão automática e o layout de controles já validado. A tecla **S acelera**, **A freia**, **X usa turbo**; as setas dirigem. Isso corresponde aos botões SNES **X**, **Y**, **A** respectivamente.
3. Após a largada, ainda no começo da reta, mantenha o carro no asfalto, próximo ao centro e sem contato com outro carro. Salve **slot 1** pelo menu **File → Save State → Save State 1** (confira o número do slot no menu; não é “Load State”). Se o menu da sua instalação estiver organizado por seleção de slot, selecione 1 antes de salvar. Não use um save dos menus ou da contagem regressiva.
4. Abra **Tools → Lua Console**. Remova/desative scripts antigos da lista. Abra **somente** `C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\lua\Top Gear (USA).lua`.
5. Se pedir perfil, selecione `C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\config\game_profile.ini`.
6. Deixe o teste controlar o jogo. Ele solta, acelera, freia, vira à esquerda e à direita, sempre carregando o mesmo slot. Não pressione teclas de pilotagem ou pausa durante o teste.

Se demorar mais de três minutos para preparar a corrida, o servidor pode expirar. Feche essa instância do BizHawk, reinicie o comando do Terminal 1 e depois o comando do Terminal 2. O save já criado continuará disponível. Cada nova execução Python precisa de uma nova conexão: reinicie o BizHawk com o comando completo; não basta reiniciar somente o Lua em um socket encerrado.

Resultado esperado: `PREFLIGHT OK`. O jogo pausa ao terminar; isso é intencional. A mensagem “Ponte encerrada pelo Python” indica encerramento normal quando o terminal terminou sem erro.

**Arquivo para devolver:** o terminal imprime o caminho completo de um JSON, por exemplo:

```text
C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\runs\preflight\preflight_AAAAMMDD_HHMMSS_microsegundos.json
```

Envie esse JSON. Se falhar, envie também a saída inteira do terminal e da Lua Console. `latest.json` é a referência interna à última tentativa; uma reprovação nova invalida a aprovação anterior. Não edite para liberar o treino. A aprovação cobre comunicação, reset e controles básicos, sem comprovar pilotagem, sensores traseiros ou obstáculos.

## 4. Primeiro treinamento

Após `PREFLIGHT OK`, o código autoriza o treino automaticamente. Não é preciso editar `profile_validated`. Feche o BizHawk após o teste.

**Terminal 1:**

```powershell
.\.venv\Scripts\python.exe python\train_hermes_ppo.py --timesteps 10240 --seed 42
```

**Terminal 2:** use novamente o comando real do BizHawk da seção 3. Abra a ROM, carregue o slot 1 no menu **Load State**, execute somente o Lua principal da v3. O treino confirma o save e o recarrega automaticamente quando cada episódio termina. **Reset não é uma ação que a IA aprende.**

São 10.240 decisões, não 10.240 corridas. Esse primeiro treino testa estabilidade e oferece um modelo inicial para avaliação. Não basta para declarar aprendizado. O PPO termina um bloco de coleta antes de parar; outros totais solicitados podem ser arredondados para cima em múltiplos de 2.048.

Em cada execução são criadas pastas novas:

```text
C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\runs\hermes-ppo_DATA_HORA_MICROSSEGUNDOS
C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\models\hermes-ppo_DATA_HORA_MICROSSEGUNDOS
```

O terminal imprime os caminhos exatos. Em `runs`: configuração congelada, logs por passo e por episódio, `monitor.csv`, TensorBoard e status. Em `models`: cada checkpoint `.zip` possui seu `.zip.json`. Preserve os dois juntos. Use **Ctrl+C uma vez no Terminal 1** para interromper e salvar; fechar o processo à força pode impedir o salvamento final.

O treino é interrompido se a causalidade da ponte for perdida. Ele não repete silenciosamente uma ação cujo ACK desapareceu. A retomada usa um checkpoint compatível e um novo episódio, preservando o experimento anterior.

## 5. Avaliar o modelo, sem atualizar a rede

Com o treino encerrado, feche o BizHawk. No PowerShell da v3:

```powershell
$modelo = Get-ChildItem .\models -Recurse -File -Filter "final_*_steps.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $modelo) { throw "Nenhum modelo final da v3 encontrado. Confira o fim do treino." }
$modelo.FullName
.\.venv\Scripts\python.exe python\avaliar_modelo.py --model "$($modelo.FullName)" --episodes 1 --compare-accelerate --scenario-id las_vegas_inicio
```

Reabra o BizHawk pelo Terminal 2, carregue o mesmo slot e execute o Lua principal. O modelo corre primeiro; depois, a referência só acelera. Essa referência não dirige nem usa turbo. O avaliador grava todas as transições e confirma que o arquivo do modelo permaneceu intacto.

**Para devolver depois do primeiro treino:** compacte a pasta `runs\hermes-ppo_...` recém-criada, envie o JSON impresso em `runs\avaliacao_modelo\avaliacao_...json` e, se solicitado para investigar a rede, o modelo `.zip` **com o respectivo `.zip.json`**. Não envie `.venv`.

## 6. Continuar treinando, preservar e atualizar

Para acrescentar 100 mil passos ao último modelo final, usando a variável `$modelo` obtida acima:

```powershell
.\.venv\Scripts\python.exe python\train_hermes_ppo.py --resume "$($modelo.FullName)" --timesteps 100000 --checkpoint-every 25000 --seed 42
```

Reabra o BizHawk como antes. Uma nova pasta de experimento será criada. O arquivo anterior não é sobrescrito. Para retomar um `interrupted_*` ou `checkpoint_*`, obtenha o caminho desse arquivo na pasta `models` e passe-o em `--resume` com aspas.

Se mudar observações, ações, recompensa, perfil ou hiperparâmetros incompatíveis, o programa recusa a retomada e informa os campos divergentes. Os modelos v2 estão em `archive\models`; não entram silenciosamente na v3. Não existe conversão segura automática de uma rede de 24 entradas para a observação atual de 26 entradas.

Futuras atualizações serão feitas **nesta pasta v3**, preservando `.venv`, `runs`, `models` e dados pessoais de experimento. Instale dependências novamente somente se os requirements mudarem. Alterações na ponte, no ambiente, no perfil ou no savestate exigem repetir o preflight; adicionar um diagnóstico isolado não exige isso.

TensorBoard, em outro terminal:

```powershell
.\.venv\Scripts\python.exe -m tensorboard.main --logdir .\runs --host 127.0.0.1 --port 6006
```

Abra `http://127.0.0.1:6006` no navegador. Métricas e critérios para treino longo estão no relatório técnico. Uma recompensa maior sozinha não comprova direção melhor.

## 7. Diagnósticos e comandos auxiliares

| Objetivo | Comando no Terminal 1 / procedimento |
|---|---|
| Repetir somente comunicação e reset | `.\.venv\Scripts\python.exe python\test_connection.py --reset --steps 3` e iniciar BizHawk/Lua como antes |
| Testar ações sem aprender | `.\.venv\Scripts\python.exe python\smoke_test_env.py --steps 300 --log-every 20 --auto-reset` |
| Recalcular comparações antigas | `.\.venv\Scripts\python.exe python\replay_rewards.py` — não precisa de BizHawk |
| Recalcular evidências de memória | `.\.venv\Scripts\python.exe python\audit_evidence.py` — não precisa de BizHawk |
| Investigar traseira, obstáculos e temporizador | Execute somente `lua\diagnostico_contexto.lua` no BizHawk; procedimento em `docs\VALIDACAO_AO_VIVO.md` |

Os testes e a v3 não afirmam que a IA já sabe vencer. Há telemetria frontal, superfície e curvas; a percepção traseira física, obstáculos específicos, cronômetro e autoria das colisões ainda são limitações documentadas.

## Cérebro Hermes PPO 3 — separado dos outros modelos

O Hermes PPO 3 começa com ator, crítico, otimizador Adam e contador novos. Ele usa o mesmo perfil azul automático/save 3, contrato PPO, observações, ações e recompensa road_v6_outcome do cenário atual. O primeiro treino cria models/hermes-ppo-3.zip; os arquivos hermes-ppo.zip, hermes-ppo-v2.zip, apolo.zip e ares.zip permanecem independentes.

Ao repetir o comando Treinar, o script retoma automaticamente somente o Hermes PPO 3, preservando ator, crítico, Adam e contador. Como PPO é on-policy, ele coleta um rollout novo; não há replay buffer. Cada run guarda logs e TensorBoard em runs/hermes-ppo-3_....

Depois de iniciar BizHawk e Lua com o perfil azul, rode o preflight. Feche o jogo após PREFLIGHT OK; inicie o treino e reabra o BizHawk/Lua quando a ponte estiver aguardando:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_hermes_ppo_3.ps1 -Modo Preflight
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_hermes_ppo_3.ps1 -Modo Treinar -Passos 100000 -CheckpointCada 25000

Para continuar treinando, use o mesmo comando Treinar. Para jogar apenas com esse cérebro, mantenha o BizHawk/Lua no perfil azul e rode:

    $env:TOPGEAR_PROFILE = 'game_profile_blue_auto.ini'
    & '.\.venv\Scripts\python.exe' '.\python\jogar_continuo.py' --model '.\models\hermes-ppo-3.zip' --modo fiel

A inclusão desse treinador altera os hashes de origem; gere um PREFLIGHT OK real e atual antes do primeiro treino.

## Cérebro Apolo (DQN) — separado do Hermes PPO

O Apolo usa o mesmo perfil azul automático/save 3, observações, 10 ações discretas e recompensa `road_v6_outcome` do Hermes PPO 2. Ele começa com uma rede nova e não importa pesos nem steps do Hermes. Os valores compartilhados que fazem sentido entre algoritmos são `learning_rate=0.0003`, `gamma=0.999`, `batch_size=64`, rede 64×64 com `Tanh` e CPU. PPO usa GAE e blocos de rollout, que não existem no DQN; o Apolo usa replay buffer de 100 mil transições, início de aprendizado após 10 mil transições, atualização da rede-alvo a cada 1.000 steps e exploração epsilon decaindo até 0,05 nos primeiros 200 mil steps.

Primeiro rode o preflight com BizHawk/Lua conectados. Quando ele terminar com `PREFLIGHT OK`, feche o BizHawk. Depois inicie o treino e abra o BizHawk/Lua novamente quando o servidor da ponte estiver aguardando:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_apolo_dqn.ps1 -Modo Preflight
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_apolo_dqn.ps1 -Modo Treinar -Passos 1000000 -CheckpointCada 25000
```

O primeiro treino cria `models\apolo.zip`. Para continuar, use o mesmo comando `Treinar`; o script retoma esse nome fixo e recupera também o replay buffer. Preserve `apolo.zip`, `apolo.zip.json` e a pasta `models\apolo-replay-buffers`. Os arquivos `models\hermes-ppo-v2.zip` e os registros Hermes ficam separados.

Para apenas jogar, selecione o perfil azul automático e use o player contínuo já existente:

```powershell
$env:TOPGEAR_PROFILE = 'game_profile_blue_auto.ini'
& '.\.venv\Scripts\python.exe' 'python\jogar_continuo.py' --model '.\models\apolo.zip' --modo fiel
```

O modo `variado` do DQN usa epsilon-greedy com 5% de ações aleatórias; o modo fiel escolhe sempre a ação com maior Q prevista. Para interromper o treino, pressione **Ctrl+C uma vez** no terminal Python; o código salva a última atualização DQN completa e o replay buffer.
