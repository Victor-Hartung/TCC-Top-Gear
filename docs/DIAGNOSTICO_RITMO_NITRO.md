# Ritmo, nitro e referência P2 — 15/09/2026

## O que sabemos

O controlador nativo de P2 calcula um corredor de trajetória, afasta-o do carro
vizinho, suaviza mudanças, compensa curva com velocidade e escreve uma magnitude
de direção interna. A evidência está em `PILOTO_AUTOMATICO_P2.md` e no disassembly
preservado em `runs/analysis/p2_rom_investigation/p2_control_flow.txt`. Não é uma
rede PPO nem o mesmo conjunto de dez botões mantidos por quatro frames de P1.
Não se demonstrou igualdade de todas as condições físicas entre esses controles.

A integração atual transporta dados e sugere alvo. Não copiou a suavização,
compensação e controle interno completos. O PPO precisa transformar a observação
em comandos adequados. Aviso de risco não equivale a uma manobra de desvio.

O relato de P2 vencer sem nitro é coerente com a importância de manter ritmo.
Esta revisão não mediu todo o uso de nitro de P2 nem demonstrou que nunca usa.
Uma vantagem de velocidade temporária não garante vitória se depois houver
freios, offtrack ou impactos. Não é possível concluir que bastam mais horas:
o modelo atual já reproduz freios em estados de liderança/corredor livre, e a
rede ancestral também os seleciona nas mesmas observações projetadas.

As duas corridas completas registradas em
`runs/jogando/jogando_20260915_191117_809517/corridas.jsonl` quando a revisão começou
terminaram em 6º e 7º, com 10 e 5 impactos, respectivamente, e zero nitro restante.
Isso é execução variada sem aprendizado, não nova evidência de melhoria por treino.
O segundo modelo descartado continua fora da seleção padrão e preservado em disco.

## Sequência automática preparada

Um modelo e um savestate, quatro corridas determinísticas sem atualizar pesos:

| Variante | Mudança aplicada sobre a ação proposta pelo mesmo ator |
|---|---|
| original | Nenhuma |
| diagnostic_without_brake | Freio vira aceleração; direção preservada |
| diagnostic_continuous_throttle | Freio/coast/direção sem acelerar passam a incluir aceleração; direção e pedido de turbo preservados |
| diagnostic_continuous_throttle_without_turbo | Igual à anterior, mas TURBO_ACCELERATE vira ACCELERATE |

A terceira não otimiza o momento de nitro: mantém os pedidos feitos pela política.
A quarta permite medir se esses pedidos estão ajudando nesta trajetória em
comparação com rodar sem nitro. As trajetórias divergem após a intervenção; a
diferença é o efeito total da regra em uma corrida, não o efeito local isolado de
uma única ação, nem uma conclusão sobre todas as pistas/saves.

As três variantes alteradas são **controles com intervenção**, não sucesso
autônomo do PPO. Cada substituição e o mapeamento usado são declarados no relatório.
O treino, o modo `jogar_continuo.py`, os pesos, os sensores e a recompensa não
foram alterados. O relatório resume chegada, posição, passos, velocidade bruta,
impactos, offtrack e nitro restante para orientar a próxima mudança.

Se retirar freio melhora sem aumentar offtrack/impactos, temos evidência para
uma correção de controle ou ajuste do ator preservado. Se a aceleração contínua
piora curvas, remover todos os freios permanentemente não é sustentado. Se a
variante sem nitro vence a correspondente com nitro, priorizamos o momento de
ativação; se ambas são lentas, turbo não é a primeira explicação a corrigir.
Não se inicia uma nova rede do zero nem um treino longo antes dessa comparação.

## Comando

Se `jogar_continuo.py` estiver rodando, encerre com Ctrl+C no terminal Python e
feche o BizHawk. O preflight atual permanece válido.

```powershell
Set-Location "C:\Users\luanb\Downloads\TCC-TopGear-RL_v3.0\TCC-TopGear-RL_v3.0"
.\.venv\Scripts\python.exe python\compare_race_policies_live.py --diagnose-pace
```

Quando aguardar conexão, em outro terminal:

```powershell
& "C:\Users\luanb\Downloads\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
```

Abra a ROM e apenas `lua\Top Gear (USA).lua` no Lua Console. As quatro corridas
reiniciam automaticamente na mesma conexão. Ao final, aparece `RESUMO DAS
CORRIDAS` e o caminho `runs/avaliacao_modelo/comparacao_correcao_*.json`.

Validação da implementação: dez testes focados passaram, incluindo quatro
variantes no mesmo ambiente com ponte simulada e verificação de todas as dez
ações em cada mapeamento. Não houve teste novo no BizHawk nesta revisão; os
resultados reais desta sequência estão pendentes. Arquivos anteriores foram
copiados para `runs/maintenance/pace_diagnosis_*` antes das mudanças.
