# Correções implementadas na v2

Esta versão parte do projeto corrigido recebido, preserva os artefatos históricos
e altera apenas a cópia `TCC-TopGear-RL_v2`.

| Área | Situação antiga | Correção v2 |
|---|---|---|
| Sincronização | Python amostrava por tempo de parede e podia repetir estado | protocolo causal `seq/ack/episode/frame` |
| Transporte | polling por arquivo podia congelar com o BizHawk pausado | socket TCP local validado, bloqueante e causal |
| Frames | quantidade de frames por ação não era garantida | socket bloqueia entre comandos; `unpause + yield` avança e confere cada frame |
| Reset | comando podia ser aplicado várias vezes/sem confirmação | reset one-shot, `reset_ok`, episódio e erro explícito |
| Segurança da ROM | qualquer ROM/domínio podia alimentar o treino | SHA-1 exato e domínio WRAM verificados pelo Lua |
| Velocidade | `u16` podia converter negativo em valor máximo | leitura `s16` em `0x1E5A` |
| Lateral | endereço `0x09C2` sem suporte estático | candidato forte `0x1E8A`, ainda sujeito a teste ao vivo |
| Adversários | nenhuma observação de carros | varredura candidata de 20 registros e sensores relativos mascarados |
| Ações | quatro ações, sem freio nem direção desacoplada | dez ações; turbo validado e habilitado |
| Observação | quatro valores e sem rank/chegada/oponentes | 19 features nomeadas, incluindo inventário e estado ativo do turbo |
| Reward | velocidade dominava o objetivo | progresso, rank, colisão, pista, chegada e primeiro lugar |
| Exploit de rank | bônus unilateral podia premiar perder/retomar posição | mudança de rank simétrica; ultrapassagem fica como métrica |
| Encerramento | parar cedo podia evitar custo futuro | falha por falta de progresso e time limit recebem penalidade |
| Modelos | salvamento podia sobrescrever e misturar execuções | diretórios únicos, checkpoints e snapshots de falha/interrupção |
| Reprodutibilidade | hiperparâmetros e perfil não ficavam completos na run | INI e configuração PPO salvos por execução |
| Diagnóstico | teste de controles tinha comparações temporais frágeis | ramos do mesmo savestate e durações iguais, inclusive freio vs coast |
| Erros | falha Lua inicial terminava apenas em timeout genérico | Python mostra imediatamente o erro publicado pelo Lua |

## Preservado

- Protocolo textual simples `TGACT2/TGSTATE2`, agora transportado por TCP local.
- BizHawk 2.11.1 e ROM não foram modificados.
- Modelo e 16 arquivos de runs anteriores permanecem byte a byte iguais em
  `archive/`.
- PPO/Stable-Baselines3 continua sendo o algoritmo-base.

## Ainda não resolvido por falta de evidência ao vivo

- semântica do bit de registro ativo/inativo dos adversários;
- escala e sinal exatos do movimento `record+10`;
- centro/largura da pista e limites por segmento;
- curvatura e look-ahead da próxima curva;
- confirmação controlada das transições restantes `2 -> 1 -> 0` do inventário,
  embora a codificação e a primeira transição `3 -> 2` já estejam validadas;
- escalas finais de combustível e marcha;
- confirmação de todas as sentinelas de largada/chegada.

Esses itens não foram preenchidos com valores inventados. O bloqueio geral de
treino permanece ativo e os scripts diagnósticos foram incluídos para descobri-los
de forma controlada.
