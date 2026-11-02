# Revisao do detector apos preflight real — 12/09/2026

## Resultado real recebido

preflight_20260912_172230_881840.json passou com ponte4 e observacao schema8.
Os445pacotes tinham historicos corretos;380eram anteriores a lap0. Reset inicial
frame5172, lateral-7680, progress21856. Todas as cinco largadas se repetiram.
Nessa coleta somente o grupo frontal teve candidatos: nao demonstra cobertura
traseira/lateral ao vivo. Cenas anteriores com video sustentam exemplos dessas
posicoes, nao validacao universal.

## Falha encontrada e correcao

Na versao anterior, as coordenadas/velocidades eram do mais proximo no grupo,
mas o risco era o maximo entre todos. Em140pacotes o risco pertencia a outro
carro: associacao ambigua para a rede. Exemplos de outras capturas tambem existem.

Agora todas as7features de cada grupo descrevem o MESMO carro: maior risco,
desempate por distancia absoluta e ID. Sem risco, escolhe o mais proximo.
Cada candidato registrado inclui selected_for_observation. Nao adiciona acao
nem recompensa; nao transforma risco em colisao inevitavel. Preditor linear,
limiares e pacote Lua nao mudaram. Continua47features, observation_schema9,
detector_version2, bridge_revision4. Modelos incompatíveis continuam recusados.

## Verificacoes

136 testes automatizados passaram. Novos testes exercitam associacao entre
posicao/risco para frente, tras e lado a lado, incluindo carro mais proximo sem
risco e outro mais distante com risco. O fallback de reset mantem validade0.
Auditoria dos445pacotes recebidos conferiu continuidade por frame, reset e
consistencia das features corrigidas. Relatorio separado detector_review_*;
recibo latest.json nao foi convertido em nova aprovacao.

Repetida equivalencia das previsoes por carro nas cinco capturas:128555
comparacoes; validade, aviso e tempo de entrada permaneceram iguais. Esse teste
nao afirma equivalencia da observacao antiga com a nova: a selecao foi corrigida.
Arquivos de modelo, save, video e evidencias originais foram preservados.

## Proximo passo obrigatorio para treino

Novo preflight real com esta observacao schema9. Primeiro execute na raiz:

```powershell
.\.venv\Scripts\python.exe python\preflight_live.py
```

Reinicie somente lua/Top Gear (USA).lua com servidor Python aguardando.
A seguir, apos analisar o novo resultado, piloto de4096passos com modelo novo.
Treino longo fica para apos confirmar reset, logs, sensores e estabilidade do
piloto. O detector continua experimental; nao foram comprovadas taxa de erro,
hitboxes universais, carros de outras voltas ou origem de toda colisao.
