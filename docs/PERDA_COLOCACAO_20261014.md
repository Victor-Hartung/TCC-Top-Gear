# Penalidade por perder colocacao — 14/10/2026

O perfil azul automatico/save 3 usa `road_v6_outcome`, recompensa 11.
A unica mudanca de valor nesta revisao e a perda de colocacao:

| Evento | Recompensa 10 | Recompensa 11 |
| --- | ---: | ---: |
| Cada posicao perdida | -0,50 | -1,00 |
| Cada posicao que estabelece uma nova melhor colocacao | +1,00 | +1,00 |
| Recuperar uma colocacao ja premiada no episodio | 0 | 0 |
| Decisao parada elegivel apos a tolerancia | -0,10 | -0,10 |

Perder tres posicoes na mesma decisao custa -3,00 nesse componente.
O primeiro rank publicado depois de um rank invalido continua sem bonus ou
multa de colocacao. As regras de progresso, impacto, pista, chegada, tempo e
tolerancia de imobilidade permanecem iguais. Os outros perfis mantem seus
valores anteriores. Nao foi adicionada multa por apertar freio.

## Continuar o mesmo cerebro

O `hermes-ppo-v2` pode continuar dos contratos conhecidos 10 ou 8 para 11.
A validacao compara o contrato completo: somente as revisoes de recompensa
explicitamente conhecidas sao aceitas. Pesos do ator e critico, estado Adam,
contador e nome sao preservados. Os ZIPs e JSONs historicos nao sao editados.

A origem e as versoes reais ficam na proveniencia e no `reward_revision.json`
da proxima run. O arquivo fixo passa ao contrato novo depois de uma atualizacao
PPO concluida. Uma parada antes da primeira atualizacao preserva o alias antigo.
O modo de play continua com pesos congelados; mudar a recompensa nao muda
instantaneamente a politica ja aprendida.

## Iniciar

Repita o preflight real depois desta revisao, pelo comando habitual:

```powershell
Set-Location -LiteralPath 'D:\TCC-2.0\TCC-TopGear-RL_v3.0'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_azul_automatico.ps1 -Modo Preflight
```

Quando o servidor estiver pronto, abra o BizHawk com o mesmo comando de antes,
incluindo save 3 e `start_blue_auto.lua`. Aguarde `PREFLIGHT OK`, feche o BizHawk
e continue o cerebro novo, por exemplo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_azul_automatico.ps1 -Modo Treinar -Passos 100000 -CheckpointCada 2048 -Cerebro hermes-ppo-v2
```

Reabra o jogo pelo mesmo comando ao aparecer o servidor de ponte pronto.
Nao e preciso criar outro cerebro, trocar o Lua ou importar somente o ator.
