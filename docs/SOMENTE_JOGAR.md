# Somente jogar continuamente

Modo pedido pelo usuário: mesma pista/savestate, decisões variadas usando a
distribuição de ações do modelo já aprendido. Sem treinamento, sem atualização
de pesos e sem a intervenção de freio do diagnóstico. Modelo padrão:
`models/hermes-ppo_20260915_031924_155890/final_10240_steps.zip` (anterior escolhido).

Feche o BizHawk atual. No primeiro terminal PowerShell:

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\jogar_continuo.py
```

Quando Python aguardar conexão, em outro terminal:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Abra a ROM e `lua\Top Gear (USA).lua` no Lua Console **uma única vez**. A cada
episódio encerrado, o ambiente recarrega o mesmo slot 1 usando a conexão aberta.
Não alterna pistas, não avança campeonato e não inventa savestates.

**Ctrl+C no terminal Python encerra.** O programa libera a conexão ao sair.
Uma regressao isolada de lap para o valor sentinela salva diagnostico em
`runs/jogando/jogando_*/lap_sentinel*.json`, descarta a tentativa e recarrega
o savestate. Ela nao conta como corrida nem recebe chegada. Depois de tres
recuperacoes em 10.000 passos, uma quarta falha encerra com erro. Outras falhas
de protocolo continuam fatais. O preflight valido continua exigido.

Para jogar com o modelo azul/manual recomendado na comparacao de 30/09, use no
terminal Python o perfil e o checkpoint correspondentes:

```powershell
$env:TOPGEAR_PROFILE = 'game_profile_manual.ini'
.\.venv\Scripts\python.exe python\jogar_continuo.py --model .\models\hermes-ppo_20260927_152129_971034\training_candidate_263179_steps.zip --modo variado
```

No BizHawk, abra `lua\Top Gear Manual (USA).lua` com a ROM e o save 2.

O padrão `--modo variado` chama a política com `deterministic=False`: sorteia
ações de acordo com as probabilidades aprendidas. Não usa ações aleatórias
uniformes, não altera recompensa/controles nem aprende com resultados. As corridas
podem variar, inclusive em qualidade, mas não há garantia de que todas sejam
diferentes. O modo anterior de avaliação determinística escolhe sempre a ação
mais provável e pode repetir a mesma trajetória no mesmo save.

Opções adicionais:

```powershell
# Mesmas decisões determinísticas, repetidas sem treinamento:
.\.venv\Scripts\python.exe python\jogar_continuo.py --modo fiel

# Encerrar automaticamente após cinco corridas:
.\.venv\Scripts\python.exe python\jogar_continuo.py --corridas 5
```

O campo `--model` permite escolher outro checkpoint compatível explicitamente.
O ator do modelo anterior é importado sob validação de contrato; a diferença de
recompensa não atualiza seus pesos. Nenhum arquivo de modelo é salvo. Ao encerrar,
são conferidos pesos, contador e hash do arquivo original. O reward calculado
pelo ambiente é ignorado pelo jogador e não vai para uma atualização PPO.

Há apenas um resumo compacto por corrida em `runs/jogando/jogando_*/corridas.jsonl`
e os dados da sessão em `sessao.json`. Não armazena em memória a lista de todas as
corridas nem gera o registro completo de observações do avaliador de diagnóstico.

Validação desta implementação: três testes focados passaram (repetição no mesmo
ambiente, escolha de modo e interrupção com preservação dos resumos). São testes
simulados/offline; a execução contínua nova ainda precisa ser observada no
BizHawk real. Não houve mudança do código crítico de telemetria/reset/recompensa;
o preflight existente permaneceu válido ao final da implementação.
