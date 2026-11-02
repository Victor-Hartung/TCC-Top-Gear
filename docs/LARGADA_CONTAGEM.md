# Largada desde a contagem regressiva — 11/09/2026

Implementacao local sobre a v3.0. Ainda requer preflight no BizHawk real com o novo save.

## Comportamento

O slot 1 e carregado a cada episodio, com post_reset_frames=0. O PPO escolhe a
primeira acao imediatamente, inclusive durante 3...2...1...GO. Nenhum bot acelera
pelo agente no treino. Reset continua sendo operacao do ambiente, fora das 10 acoes.
O hello pode chegar antes da corrida; a prontidao e conferida depois do reset.
ROM, WRAM, perfil, pista e tres voltas continuam obrigatorios.

lap=-1 e tratado como fase anterior a primeira volta valida. Nao e um detector de
GO: nao ha novo endereco de memoria nem instante exato de liberacao dos controles
comprovado. O agente recebe lap_norm=-1; depois recebe 0, 1/3, 2/3, 1 conforme a volta.
Sao 26 features, observation_schema=7. Adversarios continuam mascarados pelo Lua
quando lap<0. Nao se afirma que esses sensores foram validados durante a contagem.

Reward version=4: transicoes envolvendo lap=-1 e sem resultado publicado recebem
recompensa zero; isso inclui o primeiro -1->0, evitando salto de progresso e ganho
artificial de rank. A recompensa posterior pode ensinar escolhas anteriores via
retorno do PPO. Nao existe premio por apertar acelerador. O shaping de pilotagem
comeca apos estabelecer lap=0. Durante essa fase inicial, impactos ainda aparecem
na telemetria bruta, mas nao geram shaping nem contagem de impactos recompensados.

No-progress e idle nao punem a contagem. Um limite independente de 600 decisoes
(2400 frames; limite de seguranca, nao duracao do GO) trunca com prestart_timeout.
O max_steps geral continua contando todas as decisoes. Regressao de volta valida
para -1 e salto direto de -1 para lap>0 sao recusados. Chegada permanece dependente
de resultado valido e tres voltas completas; encerramento incompleto nao ganha bonus.

## Proximo teste real

1. No BizHawk 2.11.1, mantenha o nucleo usado para criar o save. A configuracao
   encontrada indica BSNESv115+, com QuickSave1 proprio; Snes9x tem outro arquivo.
   Ambos foram preservados. Nao renomeie um save para trocar seu nucleo.
2. Sem o Lua de treino rodando, salve no slot 1 durante a contagem de Las Vegas,
   corrida de tres voltas. Pause e confira visualmente que carregar o slot mostra
   a contagem. Se esse save ja foi criado, use-o.
3. Na raiz que contem python e .venv, execute:
   `.\.venv\Scripts\python.exe python\preflight_live.py`
4. Carregue/reinicie somente `lua/Top Gear (USA).lua` da mesma raiz no Lua Console.
   O executavel deve estar aberto com --socket-ip 127.0.0.1 --socket-port 55355.

O preflight repete cinco resets. Somente neste teste, um prefixo ACCELERATE a partir
de lap=-1 estabelece lap=0 e speed>=1500 para comparar coast/accelerate/brake/left/right
por 12 decisoes cada. Isso testa controles, nao aprendizado nem o instante de GO.
O JSON grava initial, launch_states, control_initial e states de cada ramo,
compara resets e prefixos completos. Impactos na aproximacao sao registrados,
sem reprovar so por seu contador acumulado. A janela causal so comeca com lap=0,
speed>=1500 e uma transicao sem contato/novo impacto. Novo impacto durante os
12 passos de comparacao continua reprovando. Termino ou limite excedido reprovam.
O prefixo usa uma linha atualizavel no terminal. O limite exibido nao e estimativa
percentual da duracao da contagem.

Se houver erro, examine runs/preflight/latest.json antes de qualquer treino.
Os modelos anteriores permanecem intactos, mas sao recusados no novo contrato;
nao editar seus metadados para forcar compatibilidade. O preflight anterior tambem
nao libera este codigo. Apos um novo PREFLIGHT OK, o proximo experimento deve ser
curto e com modelo novo, antes de decidir sobre treinamento longo.

## Verificacao offline

116 testes unittest passaram na .venv Python 3.11.9. Incluem Lua com APIs simuladas,
zero frames escondidos no reset, decisoes desde lap=-1, resets repetidos, transicao
sem recompensa falsa, limite de largada, regressao rejeitada e prefixo registrado.
Isso nao e validacao no BizHawk, nem demonstra capacidade de completar a corrida.


## Investigacao do preflight 20260911_163457_153728

Usuario confirmou save no GO, junto dos demais carros; esse inicio e aceito.
No JSON real: frame inicial 3086, lap=-1, speed=0, progress=21856, rank=19.
No passo 21/frame 3170 surgiu collision_events=1 e collision=1; finished=0,
final_rank=-1, lap=-1. Logo, houve sinal de impacto, nao termino. Causa desconhecida.
O carro se moveu antes da primeira volta valida; lap=-1 nao equivale a controles
bloqueados pela contagem. Relatorio original preservado. Corrigido o preflight
para distinguir impactos acumulados na aproximacao de novos impactos no ramo.
118 testes offline passaram, inclusive aceitar impacto anterior e recusar novo
impacto no ramo. Novo preflight real continua pendente; nao houve treinamento.
