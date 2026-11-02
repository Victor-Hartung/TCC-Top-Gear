# Cerebro hermes-ppo

O arquivo de uso diario e models/hermes-ppo.zip. Preserve tambem models/hermes-ppo.zip.json.

O lancador azul retoma esse cerebro por padrao. Execute na raiz:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_azul_automatico.ps1 -Modo Treinar -Passos 24576 -CheckpointCada 2048
```

Espere "Servidor da ponte pronto" e abra o BizHawk com a ROM e a ponte Lua azul automatico, como no preflight. A cada atualizacao PPO concluida, ao terminar e ao interromper com Ctrl+C, o arquivo fixo passa a conter a versao mais recente. Aguarde "CEREBRO FIXO:" antes de fechar o emulador.

Cada execucao preserva snapshots e registros em suas pastas historicas. O cerebro fixo e uma copia validada do snapshot indicado em seu JSON; seus pesos, critico, Adam e contador sao preservados na retomada. Passos de coleta ainda nao usados em uma atualizacao nao sao reaproveitados.

Se Ctrl+C chegar no meio de uma atualizacao do otimizador, o arquivo fixo conserva a ultima atualizacao completa. O snapshot interrompido fica no historico para diagnostico.

O parametro -Cerebro escolhe outro nome previamente registrado. Por exemplo, -Cerebro hermes-ppo-2 usa models/hermes-ppo-2.zip. O projeto implementa PPO; nomes distintos nao mudam o algoritmo.

-Retomar e -ImportarAtor explicitos continuam disponiveis para experimentos separados. Se -Retomar aponta para o arquivo fixo do cerebro selecionado, ele tambem sera atualizado. Para um novo treino separado do zero, use -DoZero; esta opcao preserva o cerebro fixo.

Um bloqueio do sistema operacional evita treinos simultaneos do mesmo cerebro e e liberado quando o processo termina. A dupla anterior do modelo e o registro de publicacao permitem recuperar uma substituicao incompleta na proxima abertura.
