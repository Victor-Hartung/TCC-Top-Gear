# Piloto conferido e experimento de500mil passos

Piloto:hermes-ppo_20260912_173640_718500. Statusfinal,4096passos,3resets identicos,
sem salto de frames. Dois episodios encerrados incompletos na primeira volta e
terceiro parcial ao atingir limite. Fora da pista90,8447% dos passos. Isso nao
comprova pilotagem, mas nao exige que uma politica inicial ultrapasse para
verificar transporte, observacoes e resets.

Todos4099registros (steps+reset) foram recalculados: candidatos identicos aos
registrados,21features novas dentro dos limites,1amostra no reset/4no step.
Presenca por pacote: frente2602,tras2313,lado a lado149; com risco85/32/5.
308pacotes anteriores a lap0 tinham candidatos. Frequencias nao sao taxa de acerto.

## Correcao necessaria

Metadados do modelo tinham5252611bytes porque repetiam todo preflight. Carregador
recusava acima de2MB. Original preservado. Copia de retomada com MESMOS bytes ZIP
(pesos/otimizador), mesmo contrato, metadados compactos12971bytes e referencia com
hash para metadados originais. PPO.load executado:4096passos e47entradas conferidos.
Novos treinos guardam preflight completo uma vez em preflight_receipt.json, e
checkpoints referenciam esse arquivo por caminho/hash. Limite do carregador mantido.
Nao houve alteracao de sensor/observacao/acoes/recompensa/hiperparametros.

## Rodar

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\scripts\treino_500k_detector.ps1
```

Depois reiniciar somente lua/Top Gear (USA).lua no BizHawk com socket55355.
Se estiver fechado, abrir DEPOIS de iniciar Python:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

500000ADICIONAIS arredondados aos blocos de2048:501760nesta execucao,505856total
incluindo piloto. Checkpoints a cada51200adicionais apos atualizacao. Ultimo
bloco salvo como final. Cada execucao cria novas pastas e logs por step completos.
Reexecutar este comando parte do piloto, NAO retoma automaticamente uma interrupcao.
Para retomar outro checkpoint, passar -Retomar com caminho exato compativel.
Pode alterar -Passos para outros valores; sempre adicionais, arredondados por rollout.
Nao recarregar save manualmente durante treino, nem executar Lua de diagnostico junto.

## Curvas

Em outro terminal na mesma raiz:

```powershell
.\.venv\Scripts\python.exe -m tensorboard.main --logdir .\runs --host 127.0.0.1 --port 6006
```

Abrir http://127.0.0.1:6006. Monitorar recompensa media, conclusao/progresso e fora
da pista; ao fim, avaliar checkpoints sem aprendizado para detectar colapso de
acoes. Melhor recompensa nao garante tres voltas/primeiro lugar.500mil e um
experimento, nao promessa de convergencia. Sem mudancas oportunistas de reward
no meio: preservar comparabilidade dentro desta continuacao.

Treino longo preparado mas nao iniciado pelo agente: usuario abre Lua e executa.
