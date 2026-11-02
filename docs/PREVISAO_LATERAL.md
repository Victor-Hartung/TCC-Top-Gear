# Previsao lateral experimental — 12/09/2026

Implementada em predict_proximity.py, comparada por compare_proximity.py.
Detector original detect_proximity.py preservado sem alteracao. Nao integrado ao PPO.
Nenhum novo endereco, hitbox ou causa de colisao foi validado.

## Metodo

Velocidade relativa longitudinal e lateral estimada sobre 3 frames, acompanhando
IDs. A janela reduz os zeros alternados observados entre atualizacoes da tabela.
Extrapolacao linear calcula se os intervalos de proximidade longitudinal (+/-100)
e lateral (+/-4096) se sobrepoem no mesmo instante em ate30frames. Sao raios de
proximidade exploratorios, nao dimensoes fisicas dos carros. Rejeita saltos acima
de100unidades/frame longitudinais ou4096laterais e frames nao consecutivos.
Nao usa observacoes futuras. Nao identifica atividade de sprite, pista/obstaculo,
culpa ou mudanca futura de direcao; assumicao linear pode falhar durante manobras.

## Comparacao nos registros existentes

Frames consecutivos com aviso imediatamente antes do pulso, para o ID candidato
mais proximo no instante do evento (identidade fisica ainda nao comprovada):

| Captura | Frame | Original | Previsao lateral |
|---|---:|---:|---:|
| 082010 | 6357 | 8 | 8 |
| 082010 | 8715 | 6 | 9 |
| 082719 | 7782 | 24 | 54 |
| 082719 | 7983 | 30 | 45 |
| 083426 | 6444 | 0 | 15 |
| 083426 | 7558 | 3 | 18 |
| 083426 | 7963 | 48 | 60* |
| 083426 | 9431 | 9 | 39 |

*Janela de analise limitada aos60frames anteriores; nao e necessariamente inicio.

Custo: a previsao avisou no instante das passagens sem impacto de frames7314
(082719) e6777(083426), onde o detector original nao avisava. Na captura083426,
avisos em qualquer candidato passaram de731 para1000frames entre4344. Na081729,
ambos ficaram sem avisos. Isso nao fornece taxa de falsos positivos: nao ha rotulos
sincronizados de todos os encontros e risco pode ser evitado por uma manobra.
A observacao mostra sensibilidade maior e possivel excesso de avisos.

Todas as quatro capturas agora sao desenvolvimento, inclusive a083426 previamente
reservada: usada para orientar esta mudanca. Nao chamar os resultados de validacao
independente. Nao ajustar limiares para forcar acerto nestes exemplos.

## Verificacao e uso

128 testes automatizados passaram. Casos incluem aproximacao lateral, afastamento,
intersecoes em instantes diferentes, saltos invalidos, historico novo, IDs e wrap.
Resultados unicos CSV/JSON ficam em runs/diagnostics/comparison_*. Cada JSON guarda
hashes das fontes e implementacoes. Arquivos anteriores, saves e modelos preservados.

```powershell
.\.venv\Scripts\python.exe python\compare_proximity.py --capture .\runs\diagnostics\contexto_20260912_083426_5369.csv
```

Nao precisa abrir BizHawk para replay. Nenhum comando acima executa treinamento.
Antes de uso no PPO, precisa validar identificacao fisica/avisos com cenas novas
rotuladas visualmente e decidir como representar risco continuo, sem tratar um
aviso como colisao inevitavel ou puni-lo como impacto ocorrido.
