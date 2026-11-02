> Atualização de 15/09/2026 após regressão: perfil ativo **road_v5_race / recompensa 7**. Removidos os incentivos experimentais que favoreciam adiar turbo; sensor e observação de 61 entradas preservados. **207 testes offline passaram; preflight real e comparação sem aprendizado pendentes.** [Análise do vídeo, correção e próximos comandos](REGRESSAO_RITMO_TURBO_20260915.md). As instruções anteriores de treino longo são históricas e não são o próximo passo.

# Novo treino do zero: ritmo e turbo — 15/09/2026

Perfil ativo **road_v4_driving**, recompensa **6**. Continuam observacao 61/schema 10,
ponte 5, detector 3, navegacao 1 e 10 acoes. A rede nova nao importa ator, critico,
otimizador ou contadores anteriores. Arquivos antigos foram preservados.

## O que os registros mostraram

O piloto `hermes-ppo_20260915_031924_155890` terminou normalmente com 10.240 passos,
zero recuperacoes e nenhum rollout descartado. Foram 8 episodios completos e uma
coleta parcial posterior. Todas as 8 corridas completas terminaram as tres voltas,
com posicoes de 5o a 7o e 6 a 9 impactos por corrida. Isso nao demonstra boa estrategia
de turbo ou desvio; tambem significa que uma rede do zero perdera habilidades
que a politica anterior ja tinha aprendido.

Houve 1.735 acoes sem aceleracao em 10.240 decisoes (16,94%). Em 906 dessas decisoes
havia risco publicado; em 844 a curva atual excedia 8 (grupos se sobrepoem).
Portanto, nao e correto tratar todas como erros. O novo criterio contextual
penalizaria 159 dessas decisoes. Esse criterio e uma heuristica, nao rotulacao
humana que comprove necessidade/desnecessidade de cada manobra.

O registro inclui 25 consumos de carga. O novo criterio classificaria 24 como
oportunidades desfavoraveis. Nas primeiras cinco corridas, a primeira carga
foi usada no passo 30, com velocidade baixa e lap=-1; as tres se esgotaram
ate os passos 192 a 211. Lap=-1 nao identifica precisamente o GO.

Auditoria: `runs/analysis/driving_reward/reward_audit_20260915_033526_684027.json`.
A recompensa antiga foi reproduzida com erro maximo **zero**. O replay aplica
recompensas novas as mesmas acoes antigas; **nao demonstra como a nova politica
vai dirigir**. O arquivo registra o tamanho/hash exato do prefixo lido, inclusive
quando uma coleta ainda esta em andamento.

## Recompensa implementada

Os ganhos existentes de progresso novo no asfalto, classificacao e chegada
continuam. O custo de tempo durante corrida, offtrack e impactos permanece.
Nao houve mudanca na deteccao de termino: resultado sem tres voltas nunca recebe
bonus de chegada; reset continua automatico e fora do espaco aprendido.

1. **Aceleracao:** custo 0,015 por decisao sem aceleracao quando o estado anterior
   indica corrida ativa, combustivel, superficie conhecida/asfalto, navegacao e
   alvo validos, sem impacto, sem intervalo bloqueando a lateral de P1 e curvas
   atual/a 512 unidades com modulo <= 8. O custo e dispensado se houver impacto,
   offtrack ou termino na transicao. Acoes de freio/direcao continuam disponiveis;
   nada forca os botoes. Apertar acelerador parado nao gera bonus.
2. **Largada:** custo 0,005 por decisao enquanto o estado anterior tiver lap=-1,
   sem fabricar progresso, lap ou chegada. Evita que esperar indefinidamente
   tenha retorno zero. Nao e leitura de cronometro nem detector de GO.
3. **Oportunidade de turbo:** mesmas verificacoes de espaco/superficie, curva
   atual e a 512 unidades com modulo <= 4 e velocidade bruta 4000 a 11000. Decisao usa
   somente dados anteriores a acao. Limiares sao experimentais, nao uma estrategia
   otima demonstrada pela ROM ou pelas corridas.
4. **Consumo:** custo 0,10 por carga real; custo adicional 2,0 por carga em
   oportunidade desfavoravel. Repetir acao 9 sem consumir carga nao repete custos
   de ativacao. O botao nao gera bonus de uso.
5. **Reserva:** a cada consumo, custo adicional
   `1,5 * cargas_consumidas * max(0, fracao_distancia_restante - nitro_restante/3)`.
   A distancia vem do progresso maximo acumulado do reward. E uma preferencia
   suave por manter reserva ao longo da corrida, sem bloquear uso ou obrigar
   uma carga em determinada volta. Nao ha premio por guardar cargas nem multa
   terminal por cargas nao usadas, que incentivaria descarte na linha de chegada.
6. **Uso util:** uma ativacao em boa oportunidade habilita bonus por progresso
   novo ja elegivel na recompensa base, durante boost e condicoes favoraveis.
   Peso 4 por volta de progresso, teto 0,75 por carga; sem bonus ao recuperar trecho
   repetido. Ao terminar o boost, o saldo e descartado. Estados e saldo reiniciam
   no reset, e nao sao importados de outro episodio.
7. **Desperdicio:** durante turbo, custo 0,03 por decisao fora da pista e 0,5 por
   impacto real adicional ao custo de colisao da base. O sensor nao identifica
   autoria ou causa do impacto. Uma colisao nao gera bonus de progresso util.

O corredor continua sendo limite interno candidato do piloto nativo, nao borda
fisica comprovada. Nao confiar nele isoladamente: a superficie real e mantida.
Curvas/riscos podem justificar soltar o acelerador. O objetivo nao garante
aceleracao permanente, turbo otimo ou primeiro lugar apos 500 mil passos.

Novos registros: `driving_context_before_action` e componentes separados da
recompensa. TensorBoard: `driving/accelerating_action`, `driving/throttle_opportunity`,
`driving/turbo_opportunity` e os termos correspondentes em `reward_components`.

## Testes e preservacao

**202 testes automatizados passaram** na .venv Windows/Python 3.11.9; baseline 192.
Cobrem excecoes ao custo de soltar acelerador, decisao causal de turbo, consumo
real, reserva, limite do bonus, anti-repeticao de progresso, largada, termino
incompleto e exclusividade de `--from-scratch` com importacao/retomada.
Nao foi executado treino ou preflight novo nesta alteracao.

Backup: `runs/maintenance/driving_reward_20260915_002750`.
Perfis road_v2 e road_v3_turbo continuam no codigo para reproduzir evidencias.
O avaliador legado exclui explicitamente o novo perfil por nao possuir os
sensores necessarios; ele nao inventa navegacao para avaliar a nova recompensa.

## Proximo passo e comando dos 500 mil

O contrato/configuracao/codigo de recompensa mudou. O preflight anterior de
15/09 validou os sensores, mas seu recibo nao libera silenciosamente o objetivo
novo. Feche o BizHawk e execute no terminal 1:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\preflight_live.py
```

No terminal 2, depois que o servidor estiver aguardando:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Abra a ROM e somente `lua\Top Gear (USA).lua` na Lua Console, usando a pasta
operacional acima. O script carrega o slot 1 automaticamente. Caso haja erro,
investigue o JSON antes de treino longo.

**Depois de PREFLIGHT OK para estes arquivos**, o comando do novo treino e:

```powershell
.\.venv\Scripts\python.exe python\train_hermes_ppo.py --from-scratch --timesteps 500000 --checkpoint-every 10240
```

Reinicie o BizHawk usando o comando do terminal 2 e abra o mesmo Lua principal
apos o servidor do treino aguardar. Cada execucao cria pastas novas. Para editar
a quantidade, altere somente o numero apos `--timesteps`. O PPO fecha blocos de
2048; 500000 solicitados correspondem normalmente a **501760 passos coletados**,
podendo existir interacoes extras se uma recuperacao descartar rollout parcial.
O parametro nao reduz nem sobrescreve treinos antigos.

Para interromper preservando o modelo, use Ctrl+C no terminal Python e espere
a mensagem MODELO/REGISTROS. Para continuar esse novo treino depois, use
`--resume` com seu checkpoint do **mesmo contrato**, sem `--from-scratch`.
Modelos antigos sao recusados pelo novo contrato; nao houve importacao de pesos.
