> Revisão de 13/09/2026: replay real mostrou mudança do resultado após sua publicação. A ROM contém corte de aceleração com 10 finalistas; correspondência no episódio ainda depende de captura. **Próximo passo: diagnóstico nativo automático, não treino longo.** [Evidências e comando](ENCERRAMENTO_NATIVO.md). Instruções de treino e interpretações de término anteriores abaixo são históricas.

# Ajuste de estratégia de turbo e investigação do encerramento

Atualização local de 12/09/2026. Base exclusiva v3.0. Os modelos e registros
anteriores permanecem intactos. Não foi iniciado treinamento nem executado
BizHawk real nesta atualização.

## Consumo observado

A auditoria do treino `hermes-ppo_20260912_175046_376997` detectou o consumo pela
redução do inventário `nitro`, não pela quantidade de ações TURBO_ACCELERATE.
Nos últimos 20 episódios encerrados, os três consumos ocorreram em média nos
passos 30,35; 117,40; 207,65. Com quatro frames por passo, isso corresponde a
aproximadamente 2,0; 7,8; 13,8 segundos após o save, usando 60 fps como referência.
Esses segundos não foram lidos do HUD. Todas essas corridas consumiram três cargas.

A primeira carga foi consumida com lap=-1 em todos esses 20 episódios. Esse
valor não identifica precisamente a contagem ou o GO. O perfil anterior zerava
todos os componentes de recompensa nas transições envolvendo lap=-1; portanto,
não fornecia custo imediato de recurso nessa fase. Isso não prova, por si só,
que todo uso de turbo na largada seja ruim.

Evidência: `runs/maintenance/turbo_timing_review.json`. A frequência da ação 9
não mede a frequência de ativações: quando o turbo já está ativo ou sem carga,
a Lua mantém a aceleração normal e não inventa uma nova carga.

## Novo objetivo experimental

O perfil ativo agora é **road_v3_turbo, recompensa versão 5**. O perfil road_v2
continua disponível com seu contrato/recompensa versão 4, para análise comparativa.
Observação schema 9 (47 features), ações (10), detector 2, ponte 4 e endereços de
memória foram mantidos.

Além da recompensa road_v2, são aplicados:

| Componente | Regra |
|---|---|
| Custo da carga | -0,25 por carga efetivamente consumida |
| Custo da reserva | Até -1,00 por carga, proporcional à fração de corrida restante |
| Ativação fora do asfalto conhecido | -0,75 adicional por carga |
| Efeito desperdiçado fora do asfalto conhecido | -0,01 por passo com turbo ativo |

A fração restante usa o maior progresso líquido acumulado pelo reward, dividido
por três vezes o comprimento da pista. Não usa um cronômetro suposto nem acompanha
cegamente os pulsos do contador de volta. Recuar não aumenta o crédito de reserva.
O consumo com lap=-1 também é cobrado; não recebe progresso ou chegada inventados.

Na pista, uma carga custa aproximadamente -1,25 no início e -0,25 perto do fim.
Esse custo representa uma hipótese de incentivo para preservar opções futuras;
não é uma propriedade física comprovada do jogo. As três cargas permanecem
disponíveis em qualquer volta. Não há proibição de turbo na largada, uma carga
obrigatória por volta, recompensa por apertar turbo, bônus por guardar cargas
nem um piloto que escolha os momentos no lugar da rede.

O ganho por avanço, ultrapassagem inédita e chegada continua vindo das consequências
no jogo. Um uso cedo que renda progresso suficiente pode compensar o custo.
O novo objetivo precisa ser avaliado: pode deslocar o uso para mais tarde ou
reduzir o uso em excesso. As métricas de cargas restantes permitem detectar isso.

Não foi adicionada penalidade baseada em suposta culpa de colisão ou em todo aviso
do detector. O bit de impacto continua genérico, e avisos não são colisões confirmadas.

No replay fixo dos 365.212 passos antigos, o custo adicional total foi -1.035,70;
nos últimos 20 episódios, -3,63 por episódio em média. Isso apenas mede a mudança
de pontuação das trajetórias já registradas, não prevê ações nem classificação de
uma política futura. Dados: `runs/maintenance/turbo_strategy_20260912_225715/reward_replay.json`.

## Preservação da pilotagem e compatibilidade

Uma retomada comum do modelo road_v2 sob a nova recompensa é recusada. Foi criada
uma operação explícita `--initialize-policy-from`, restrita a road_v2/v4 →
road_v3_turbo/v5, com todos os demais campos de contrato iguais.

Ela copia somente a rede de decisão e sua saída categórica (ator). A rede que
estima o retorno futuro, o otimizador e o contador começam novos. O modelo de
origem não é modificado nem recebe metadados adulterados. O novo experimento
registra caminho, hashes e contador de origem em `policy_initialization.json` e
na proveniência dos checkpoints.

O ator real do modelo `failed_369308_steps.zip` foi carregado e comparado em 100
observações sintéticas dentro dos limites: probabilidades de ações idênticas
antes de qualquer aprendizado novo. Essa verificação não foi uma corrida.
A pilotagem de partida foi preservada, mas as atualizações seguintes podem mudá-la.

O novo contador começar em zero identifica os passos deste objetivo; não significa
que a rede de decisão foi reinicializada aleatoriamente. Não comparar diretamente
os totais de reward dos dois perfis como se o objetivo fosse idêntico.

## Registro e TensorBoard

Cada episódio agora registra consumo real, primeiro passo de ativação, ativações
com lap=-1, frames/volta/progresso de cada carga e tempo do efeito fora da pista.
O campo `episode_elapsed_frames` mede tempo emulado desde o reset; não é o timer
do jogo. No TensorBoard:

- `turbo/rolling100_turbo_charges_used`;
- `turbo/rolling100_turbo_prestart_charges`;
- `turbo/rolling100_first_activation_step`;
- `turbo/rolling100_turbo_offroad_active_steps`;
- `turbo/rolling100_nitro` (cargas restantes ao encerrar);
- componentes separados em `reward_components/turbo_*`.

Avaliar isso junto de conclusão, posição final, vitórias e impactos. Usar turbo
mais tarde não é sucesso se a corrida ficar pior.

## Encerramento em 1:29 versus 1:32

Não há um corte fixo de 89 segundos no código. Os 279 episódios encerrados do
treino tinham `final_rank` válido publicado pelo jogo: 163 chegadas completas e
116 encerramentos incompletos. Nenhum terminou por `time_limit` ou `no_progress`.
Os limites de coleta não causaram esses términos.

O timer nativo ainda não foi identificado. A relação entre o tempo percebido,
o HUD e o momento em que 0x1F00 publica resultado não pode ser concluída só desses
logs. Não aumentamos um limite fictício nem concedemos três segundos extras de
recompensa depois de um resultado sem verificar a semântica.

Foi preparado `diagnose_finish_live.py`. Ele reproduz exatamente as ações do
episódio 270 a partir do mesmo save, verifica a telemetria contra o registro e
observa mais 240 frames após o primeiro resultado, mantendo aceleração nessa
cauda. Não treina nem altera o ambiente. Registra os sinais antes e depois do
momento em que o treino normalmente teria feito reset. Movimento residual sozinho
não prova que a corrida ainda aceita classificação.

**Próximo teste para investigar o encerramento:**

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\diagnose_finish_live.py
```

Ele primeiro lê as ações do log grande. Depois de aparecer o servidor aguardando,
abra uma nova conexão do BizHawk em outro terminal:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Execute somente `lua/Top Gear (USA).lua` desta v3. Mantenha o save atual e deixe o
diagnóstico dirigir. Não precisa clicar em marcações. Se puder, observe o HUD
nos segundos finais. O JSON é salvo em `runs/diagnostico_termino/finish_replay_*.json`.
Uma divergência interrompe o replay com ambos os estados preservados.

## Preflight e primeiro ajuste do turbo

Depois de investigar o resultado acima, repetir o preflight por causa da mudança
de configuração e recompensa:

```powershell
.\.venv\Scripts\python.exe python\preflight_live.py
```

Usar uma conexão nova do BizHawk e o Lua principal. Após PREFLIGHT OK, o ajuste
curto está preparado:

```powershell
.\scripts\ajustar_turbo_detector.ps1
```

O padrão é 10.240 passos de novo objetivo, com checkpoints a cada 2.048, usando
o ator de 369.308 passos. `-Passos` altera o orçamento. Os scripts anteriores que
retomam road_v2 são incompatíveis com o perfil ativo novo por projeto.
Para continuar um checkpoint já treinado em road_v3_turbo, usar `--resume` com
esse checkpoint, não repetir a inicialização do ator antigo.

Não foi prometido bom uso do turbo somente pela edição dos arquivos. A eficácia
será medida no novo treino e na avaliação separada; o encerramento continua em
investigação até receber dados após a publicação do resultado.
