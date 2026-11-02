# Detector experimental de proximidade

Implementado em python/detect_proximity.py, exclusivamente para replay offline.
Nao e importado pela ponte, ambiente ou PPO. Nenhuma memoria nova foi validada.
Usa tabela existente e distancia circular; inclui lap=-1, frente, tras e lado a lado.
Acompanha IDs, nao indices de registros, e recusa frames descontinuos/tabelas invalidas.

Parametros exploratorios: raio 10% da volta; faixa longitudinal lado a lado +/-32;
aviso longitudinal <=100 e lateral <=4096, ou alinhamento longitudinal estimado
em ate 30 frames com a mesma faixa lateral. Derivada aceita ate100 unidades/frame.
Nao sao hitboxes medidas. Tempo estimado e de alinhamento longitudinal, nao de colisao.
Nao extrapola movimento lateral. Proximidade modular nao prova atividade/visibilidade
em outras voltas. Sensores nao identificam culpa, objetos ou cronometro.

## Replay realizado em 12/09/2026

- Coleta 081729:1601 frames, nenhum frame de aviso, nenhum pulso de impacto.
- Coleta 082010:4638 frames,484 com aviso. Nos60frames anteriores aos impactos
  6357 e8715 houve26frames com aviso em cada janela.
- Coleta 082719:2157 frames,464 com aviso. Nas janelas anteriores aos impactos
  7782 e7983 houve35 e39frames com aviso. Nos quatro instantes de impacto, o
  candidato mais proximo gerou aviso (IDs17,17,7,9); IDs nao confirmados visualmente.
- Na passagem rente relatada, frame7314, ID14, gap=-1/lateral4424:sem aviso naquele
  instante. Houve26frames com aviso nos60anteriores: o detector indica aproximacao
  que pode ser evitada, nao batida inevitavel. Nao declarar zero falsos positivos.

Mesmas capturas foram usadas para desenvolver e examinar o detector. Resultados
nao sao validacao independente nem taxa de acerto; quatro pulsos podem nao ser
quatro acidentes independentes. Cada JSON guarda hashes das fontes e limites;
CSV registra todos os candidatos no raio, com validated=False.

122 testes automatizados passaram, incluindo continuidade, IDs reordenados,
wrap, aproximacao traseira e separacao lateral. Modelos/logs originais preservados.

## Executar sem abrir BizHawk

Na raiz da v3.0:

```powershell
.\.venv\Scripts\python.exe python\detect_proximity.py --capture .\runs\diagnostics\contexto_20260912_082719_6017.csv
```

Saidas CSV/JSON unicas em runs/diagnostics. Proximo passo: coleta independente com
visualizacao dos candidatos para validar identidade, atividade, aproximacao e
avisos antes de qualquer incorporacao ao PPO. Nao escolher limiares pela taxa
aparente de acerto destas cenas.
