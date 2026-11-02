# Freada após a curva enquanto liderava — 15/09/2026

Modelo selecionado para próximos testes: `models/hermes-ppo_20260915_031924_155890/final_10240_steps.zip`.
O modelo `interrupted_357820_steps.zip` foi retirado da seleção padrão; seu arquivo
e seus registros continuam preservados. Nenhum modelo foi retreinado ou sobrescrito.

## Evidência real e reprodução offline

A avaliação real `runs/avaliacao_modelo/comparacao_correcao_20260915_162243_909758.json`
terminou três voltas em 6º, com 12 impactos, 29 decisões com freio e 97 decisões
de direção sem aceleração. A outra avaliação terminou também em 6º, com sete
impactos e três cargas intactas. Essas duas corridas isoladas não demonstram que
o primeiro sempre desvia melhor; seguimos a escolha do usuário de usá-lo como base.

O trecho descrito pelo usuário foi localizado: no passo 336, frame anterior
6512, P1 estava em 1º, velocidade bruta 7519, lateral 6829, no asfalto, sem impacto
e sem bloqueios no corredor. A curva atual estava em 4 e as três antecipações em
zero. Escolheu `LEFT_BRAKE`. No passo 337, frame anterior 6516:

| Informação anterior à ação | Valor |
|---|---|
| Posição | 1º (rank bruto 0) |
| Velocidade bruta | 7354 |
| Lateral | 5622 |
| Fora da pista / superfície desconhecida / impacto | 0 / 0 / 0 |
| Curva atual e antecipações 512, 1024, 2048 | 0 / 0 / 0 / 0 |
| Navegação / alvo válidos | sim / sim |
| Bloqueadores no corredor | nenhum |
| Alvo lateral candidato | 0 |
| Carros publicados pelo detector nessa amostra | atrás, não à frente |
| Probabilidade LEFT_BRAKE | aproximadamente 60,1% |
| Probabilidade LEFT sem acelerar | aproximadamente 20,3% |
| Probabilidade LEFT_ACCELERATE | aproximadamente 10,2% |

As probabilidades são saídas da política, não estimativas da utilidade das ações
nem prova de uma intenção compreensível da rede. O avaliador determinístico
escolhe a ação de maior probabilidade; neste caso, esquerda com freio.

Há freios repetidos, intercalados com outras ações, até depois do passo 371.
Antes do passo 378 a velocidade era 2739, ainda em 1º. No passo 390 já estava em
2º. A velocidade bruta não é km/h. Nem todas as curvas futuras ficam em zero
durante todo esse intervalo: mais adiante aparece uma curva distante. Portanto,
o exemplo do passo 337 não deve ser generalizado para todas as 29 frenagens.

Na corrida, 21 das 29 decisões com freio tinham navegação válida, nenhum bloqueio
publicado, nenhum impacto e superfície conhecida/asfalto no instante anterior.
Isso não rotula automaticamente todas como desnecessárias: ainda existe a
dinâmica lateral, e obstáculos específicos não estão comprovadamente observados.

Reprocessar as observações gravadas no modelo original reproduziu exatamente
**1263 de 1263 ações**. O Lua associa ação 7 a Left + botão de freio configurado;
ação 3 a Left + acelerador. A navegação publica dados e não insere comandos de
freio. Não apareceu evidência de troca de botão ou interferência do novo objetivo
de recompensa na escolha destas ações: a avaliação não executa aprendizado.

Para investigar a origem, consultamos apenas offline o ator ancestral de 47
entradas, `hermes-ppo_20260913_194800_198463/final_112640_steps.zip`, usando as mesmas
primeiras 47 entradas das observações registradas. Os nomes e a ordem foram
conferidos no contrato. Ele também escolhe freio em 27 dos 29 estados em que o
ator atual freou, inclusive nos passos 336, 337 e 371. Isso apoia a hipótese de
um comportamento herdado e não exclusivamente criado pelas 14 novas entradas.
Não é replay da corrida no emulador nem prova de que o ancestral visitaria os
mesmos estados. Não foi restaurado código antigo nem substituído o ator atual.

Não é possível deduzir uma justificativa semântica exata de uma rede só olhando
as probabilidades. Ela aprendeu associações entre observações e ações, e o
objetivo anterior não eliminou esta preferência inadequada. Dizer que freou
porque viu carro/placa à frente não é sustentado pelos dados deste instante.

## Próximo experimento preparado

O comando abaixo compara **o mesmo modelo anterior** em duas corridas a partir
do mesmo savestate, sem aprendizado:

1. Política original, sem alterações nas ações.
2. Intervenção diagnóstica: freio vira acelerador, preservando a direção:
   2→1, 7→3 e 8→4. Coast, direção sem acelerar, turbo e demais ações permanecem.

Essa separação testa especificamente o freio; não confunde sua retirada com
forçar aceleração nas outras 97 decisões. O resultado da segunda corrida é
explicitamente marcado como **controle com intervenção**, não desempenho autônomo
do PPO. Todos os comandos propostos/substituídos são registrados por passo.

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\compare_race_policies_live.py --diagnose-braking
```

Feche antes o BizHawk atual. Quando Python aguardar conexão, abra em outro terminal:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Abra a ROM e somente `lua\Top Gear (USA).lua` no Lua Console. O último preflight
continua sendo exigido. Nenhum código crítico de ambiente/sensor/recompensa foi
alterado neste diagnóstico. O script executa ambas as corridas automaticamente,
salva o relatório em `runs/avaliacao_modelo/comparacao_correcao_*.json` e confere
que os arquivos dos modelos continuam intactos. Ctrl+C interrompe e salva o parcial.

O teste mede o efeito de retirar freios e a evolução subsequente da corrida;
não estima apenas o efeito isolado de um único passo, pois as trajetórias depois
da intervenção divergem. Será necessário comparar ritmo, término, posição,
impactos e offtrack. Se melhorar, a mudança permanente deve ser decidida entre
ajuste curto do ator preservado e uma assistência explicitamente declarada.
Não foi adicionada assistência silenciosa ao treino nem proibido freio no projeto.

Oito testes focados passaram após esta alteração, incluindo par de episódios com
ponte simulada, conservação da direção e preservação de turbo/coast. **A intervenção
ainda não foi testada no BizHawk real.** Evidência detalhada e script reproduzível:
`runs/analysis/braking_20260915/braking_audit.json` e `audit_braking.py`.
