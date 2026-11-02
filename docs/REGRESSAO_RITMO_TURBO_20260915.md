> Próximo diagnóstico: [freada após a curva](FREADA_APOS_CURVA_20260915.md). O modelo anterior foi selecionado; o novo permanece preservado e fora da seleção padrão.

# Regressão de ritmo e turbo — análise e correção de 15/09/2026

**Estado atual:** perfil `road_v5_race`, recompensa 7, observação 61/schema 10,
ponte 5, detector 3, navegação 1 e 10 ações. **207 testes offline passaram. Novo
preflight real e comparação de políticas pendentes. Nenhum treino foi iniciado
nesta correção.** Os comandos antigos de treino de 500 mil passos não são o
próximo procedimento recomendado.

## O que piorou

Foram comparados os últimos 100 episódios encerrados de cada treino. Encerrar um
episódio não significa completar as três voltas. As métricas abaixo vêm dos JSONL
originais, não de estimativa visual nem de uma curva de recompensa com objetivos
diferentes.

| Medida | Treino de 369.308 passos, 12/09 | Treino de 357.820 passos, 15/09 |
|---|---:|---:|
| Corridas completas | 79/100 | 32/100 |
| Vitórias | 1/100 | 0/100 |
| Velocidade média, unidade bruta da RAM | 6.750,64 | 6.113,16 |
| Impactos por episódio | 6,81 | 3,32 |
| Tempo fora da pista | 0,91% | 1,29% |
| Cargas de nitro restantes, média | 0 | 1,17 |
| Decisões que incluem aceleração | 88,34% | 87,17% |

As médias de velocidade, impactos, offtrack e nitro são médias por episódio; a
fração de ações usa todas as decisões desses episódios. O contador bruto de
velocidade não é km/h. Menos impactos com menos velocidade e menos chegadas não
comprova melhora de desvio. O aumento de freio/coast, sozinho, também não explica
a regressão: a proporção de ações com aceleração mudou pouco.

O treino novo foi interrompido normalmente: 357.820 passos coletados, 356.352
incluídos em atualizações PPO, zero recuperações e zero passos descartados por
falha. Os 1.468 passos finais de rollout parcial não chegaram à atualização; não
há evidência de uma falha de comunicação que explique a perda de desempenho.

O piloto de 10.240 passos imediatamente anterior, já com **61 entradas e a
navegação nova**, manteve o ator anterior e terminou suas oito corridas entre
5º e 7º. Depois disso foram trocados a recompensa e os pesos iniciais, começando
uma rede do zero. Isso mistura causas. Os dois treinos longos também têm
histórias de inicialização diferentes. **A tabela comprova regressão observada,
mas não isola causalmente todas as mudanças.** A vitória anterior foi registrada
e reproduzida em outra validação real; ela não significa vitórias consistentes.

## Vídeo enviado

Arquivo original preservado: `Gravando 2026-09-15 072946.mp4`, duração 115,58 s,
580×514, 30 fps. O vídeo inteiro foi decodificado; 58 imagens, amostradas a cada
dois segundos, foram examinadas em cinco folhas de contato. Os tempos abaixo são
aproximados. Não existe overlay de frame do emulador que permita afirmar
sincronização exata entre vídeo e JSONL.

- O começo mostra o fim de uma corrida, com uso de cargas por volta de 8–10 s e
  20 s do vídeo. O reset ocorre perto de 22 s.
- Na corrida seguinte, o carro mantém três cargas até aproximadamente **1:07 no
  relógio do jogo**. Depois do primeiro turbo sobe de 12º em direção ao 9º lugar.
- Outro consumo aparece próximo de **1:24 no relógio do jogo**. Antes do reset
  seguinte, perto de 112 s do vídeo, aparece em 9º com uma carga sobrando.

Essa sequência é consistente com os episódios registrados 260 e 261. O 260
terminou em 15º sem completar três voltas; o 261 completou em 9º, com primeiro
consumo no passo 1.023, segundo no 1.284 e uma carga restante. É correspondência
compatível com os dados, não alinhamento provado frame a frame. Não foi atribuída
culpa de colisão a um carro só pela imagem.

## Erro no desenho da recompensa

A recompensa 6 que implementei adicionava uma preferência por reserva:

`1,5 × cargas consumidas × max(0, fração de distância restante − nitro restante/3)`.

Esse custo **diminui com o avanço da corrida**, criando um incentivo explícito a
adiar o consumo. Havia ainda custo de ativação 0,10, mais 2,0 se a ativação fosse
classificada como desfavorável. O ganho específico por uso útil tinha teto de
0,75 por carga e dependia de várias condições de velocidade, curva e espaço.
Assim, gastar uma carga cedo podia custar mais que todo o bônus específico
disponível para ela, mesmo sem uma batida. O progresso geral ainda podia compensar
isso; não se afirma que o objetivo proibia matematicamente qualquer uso cedo.

O replay anterior já classificava **24 de 25 consumos** do piloto que completava
corridas como desfavoráveis. Isso demonstrava que a regra era restritiva, não que
24 manobras fossem comprovadamente erradas. Os testes confirmavam a aritmética,
mas não demonstravam que a regra ensinaria boa estratégia. Essa distinção deveria
ter pesado mais antes do experimento longo.

Nos últimos 20 episódios do treino novo, a penalidade por ativação desfavorável
somou −34, a de reserva −7,1449, e o bônus específico de progresso útil somente
+2,8897. Esses componentes são evidência do incentivo aplicado; sua correlação
com o comportamento não substitui um experimento controlado de aprendizado.

## Correção aplicada

Foi criado um perfil novo e explícito, `road_v5_race`/7. A recompensa de corrida
volta à aritmética de `road_v2`, **já presente na própria v3.0**, mantendo apenas
o custo de tempo de largada de 0,005. Isso remove as regras experimentais de
momento do turbo para testar o objetivo por resultados. Não restaura uma versão
antiga do projeto, um Lua antigo nem uma observação antiga.

Continuam progresso novo elegível no asfalto, ganho de classificação, custo de
tempo/parada/impactos/offtrack, prêmio de chegada e primeiro lugar, e penalidade
de encerramento incompleto. Progresso repetido não gera prêmio. Chegada continua
exigindo resultado válido e três voltas. Não foi alterado o término nativo.

Foram removidos neste perfil o custo de reserva, o classificador de oportunidade
de turbo, custos específicos de ativação/boost e o custo contextual por soltar
acelerador. Acelerar e usar turbo devem valer pelo avanço e resultado obtidos;
apertar botões não rende pontos. Não há regra de gastar uma carga por volta nem
multa por carga sobrando, que poderia ensinar descarte no fim.

O detector e as 14 entradas de navegação continuam. Eles informam carros, riscos
e um alvo candidato; **não acionam automaticamente o volante**, nem garantem uma
trajetória sem colisão. A política ainda precisa aprender a utilizar os sinais.
Esta correção não declara que todo problema do detector foi eliminado.

Alterar a recompensa não reescreve os pesos já aprendidos. Por isso foi preparado
`python/compare_race_policies_live.py`: compara um episódio determinístico de cada
ator preservado no mesmo savestate. O primeiro é o piloto de 61 entradas que
manteve as habilidades anteriores; o segundo é o modelo interrompido de 357.820
passos. A importação é explícita, somente do ator, em memória. Não chama `learn`,
não salva pesos e verifica os hashes dos modelos no final. O crítico novo não é
usado para escolher ações. Uma corrida determinística por política fornece um
teste de referência; não mede robustez em outras pistas/saves/sementes.

## Validação e preservação

- 207 testes automatizados passaram na `.venv` Windows, em 11,906 s. Incluem
  equivalência com a recompensa base, ausência do incentivo de reserva, recusa
  de contrato incompatível e comparação de duas políticas com **ponte simulada**.
- Auditorias offline dos dois modelos reais encontraram diferença máxima zero
  nas probabilidades do ator antes/depois da importação, crítico novo preservado,
  otimizador vazio, contador zero e arquivo de origem intacto.
- O preflight antigo é recusado após a mudança de contrato/código. A retomada
  comum dos dois checkpoints também é recusada; a comparação tem uma migração
  específica limitada à mudança de recompensa e exige as mesmas 61 entradas,
  ações, sensores e demais parâmetros.
- Não foi executada nova validação no BizHawk nem treinamento nesta correção.
  Modelos, vídeo, logs e evidências existentes foram preservados.
- Backup anterior às alterações: `runs/maintenance/race_reward_repair_20260915_074024`.

Estatísticas, hashes, quadros do vídeo e script de reprodução:
`runs/analysis/regression_20260915/`. Arquivo principal:
`regression_summary.json`. Auditorias de ator:
`runs/analysis/native_navigation/migration_audit_20260915_104325_862973.json` e
`migration_audit_20260915_104327_179587.json`.

## Próximo teste — sem aprendizado

Feche a instância atual do BizHawk. No **terminal 1** do PowerShell, inicie primeiro
o servidor Python:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\preflight_live.py
```

Quando estiver aguardando conexão, no **terminal 2**:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Abra a ROM `assets\rom\Top-Gear-USA.sfc`. Em **Tools → Lua Console**, abra somente
`lua\Top Gear (USA).lua` desta pasta v3.0. Não abra `native_navigation.lua`
isoladamente. O slot 1 é carregado automaticamente; use o save já validado.

**Somente após PREFLIGHT OK**, feche o BizHawk e rode no terminal 1:

```powershell
.\.venv\Scripts\python.exe python\compare_race_policies_live.py
```

Quando aguardar conexão, repita o comando do terminal 2 e abra a mesma ROM e o
mesmo Lua principal. Deixe terminar os dois episódios. O script salva
`runs\avaliacao_modelo\comparacao_correcao_DATA_HORA.json`; o nome exato aparece
no terminal. Não precisa enviar arquivos que já estão nesta pasta acessível.

Se houver erro de preflight, investigamos o relatório antes da comparação.
Depois da comparação, o próximo passo é escolher uma experiência curta de
aprendizado com essa recompensa e avaliar separadamente seus resultados. Não
iniciar outro bloco de 500 mil passos só porque os testes offline passaram.

## Assistir somente a um modelo

O avaliador também aceita uma única origem em `--models`. Exige o mesmo preflight
atual e executa uma corrida determinística, sem atualizar pesos. A origem anterior
abaixo é o descendente de 61 entradas que preservou o ator antigo, não o checkpoint
original de 369.308 passos. Atualização: sem `--models`, usa somente o anterior selecionado; o modelo novo foi retirado da seleção padrão.

Anterior:

```powershell
.\.venv\Scripts\python.exe python\compare_race_policies_live.py --models models\hermes-ppo_20260915_031924_155890\final_10240_steps.zip
```

Novo:

```powershell
.\.venv\Scripts\python.exe python\compare_race_policies_live.py --models models\hermes-ppo_20260915_035041_119669\interrupted_357820_steps.zip
```

Inicie Python antes do BizHawk e carregue a ROM e o Lua principal, conforme acima.
Ctrl+C no terminal Python interrompe a avaliação e preserva registros parciais.
Seis testes focados passaram após acrescentar a seleção de uma única política;
são testes offline, inclusive com ponte simulada, e não validação real de pilotagem.
