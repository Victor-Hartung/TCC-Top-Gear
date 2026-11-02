> Historico da revisao de 12/10 (recompensa 10). Desde 14/10 a recompensa 11
> aumenta a multa por posicao perdida para -1,00; os demais valores desta
> nota permanecem. [Estado atual e comandos](PERDA_COLOCACAO_20261014.md).

# Penalidade por imobilidade e recompensa por colocacao

O perfil azul automatico/save 3 usa `road_v6_outcome`, recompensa 10.
Os comandos, os argumentos, o Lua, a abertura do jogo e os modos de play
continuam iguais. Nao foi criado outro inicializador nem outro cerebro.

## Recompensas

| Evento | Antes | Agora |
| --- | ---: | ---: |
| Decisao parada elegivel, depois da tolerancia | -0,02 | -0,10 |
| Nova melhor colocacao, por posicao ganha | +0,50 | +1,00 |
| Posicao perdida | -0,50 | -0,50 |
| Recuperar colocacao que ja foi premiada | 0 | 0 |

A imobilidade exige velocidade bruta exatamente zero, ausencia de progresso
positivo e ausencia de impacto atual ou novo incremento do contador de
impactos. O fim da corrida nao recebe multa por imobilidade. Movimento,
progresso positivo, impacto ou fim reiniciam o contador.

Durante a corrida, a tolerancia continua de 15 observacoes consecutivas:
a multa comeca na 16a. Antes da primeira linha, inclusive em `lap=-1`,
a tolerancia e de 30 observacoes consecutivas, com multa desde a 31a.
Essa tolerancia nao detecta o GO e nao foi validada para outros saves.
Velocidade bruta 1 nao e elegivel para esta multa.

O ganho usa o rank validado e somente novas melhores colocacoes no episodio.
O primeiro rank publicado nao conta como ultrapassagem. O contador
`overtakes_total` continua sendo uma metrica; nao gera bonus adicional.
Perder e recuperar a mesma posicao nao permite repetir o premio.
As recompensas de progresso, pista, impactos, tempo e chegada ficam iguais.
Os outros perfis de recompensa conservam seus valores anteriores.

## Mesmo cerebro e mesmos comandos

A retomada reconhece exclusivamente a revisao conhecida do azul de
recompensa 8 para 10. Observacoes, acoes, ROM, save, configuracao do PPO e
todos os outros campos precisam continuar identicos. Alteracoes inesperadas
continuam sendo recusadas. Os contratos historicos dos ZIPs nao sao editados.

O treino habitual com `hermes-ppo` conserva ator, critico, estado Adam e
contador total. O critico e os momentos Adam precisarao adaptar-se aos novos
retornos durante o aprendizado. A origem e os dois contratos ficam
registrados em `reward_revision.json` e na proveniencia dos checkpoints.
O alias so passa ao contrato novo depois de uma atualizacao PPO concluida;
uma parada antes da primeira atualizacao preserva o alias antigo.

Como a recompensa e os arquivos criticos mudaram, repita o preflight real
pelo procedimento existente antes do treino ou play que exige esse recibo:

```powershell
& '.\scripts\treino_azul_automatico.ps1' -Modo Preflight
```

Depois de `PREFLIGHT OK`, o comando habitual continua valido, por exemplo:

```powershell
& '.\scripts\treino_azul_automatico.ps1' -Modo Treinar -Passos 24576
```

A abertura de BizHawk/Lua permanece a descrita em
[LEIA_PRIMEIRO_OUTRO_PC.md](../LEIA_PRIMEIRO_OUTRO_PC.md).
Os comandos existentes de play continuam sem aprender ou atualizar o ZIP.
A revisao da recompensa nao melhora instantaneamente as decisoes ja salvas;
o efeito no comportamento precisa ser medido depois dos proximos treinos.
