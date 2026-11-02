# Rodar o TCC v3.0 em outro computador Windows

Pacote de compartilhamento preparado em 06/10/2026. Ele contem o projeto
v3.0 atual, modelos, logs, diagnosticos, evidencias, a ROM existente no projeto,
BizHawk 2.11.1 e os saves atuais. A pasta `archive` e evidencia historica;
nao deve ser usada como codigo operacional.

O perfil azul automatico usa o save 3, 61 observacoes, 10 acoes e a recompensa
experimental `road_v6_outcome`/11. As alteracoes de recompensa e GAE passaram
por testes offline; ainda precisam de novo preflight real e avaliacao de
aprendizado. Os modelos existentes nao foram retreinados com essa recompensa.
Os recibos antigos registram a maquina de origem e nao validam este novo PC.

A revisao de 12/10 aumentou a multa por imobilidade e o premio por nova melhor
colocacao. Em 14/10, a multa por posicao perdida passa de -0,50 para -1,00.
Os comandos e o cerebro fixo continuam iguais: a retomada dos contratos
conhecidos 8 e 10 preserva pesos, critico, Adam e contador, com registro da revisao.
Repita o preflight real antes de usar os arquivos atuais.
[Detalhes da perda de colocacao](docs/PERDA_COLOCACAO_20261014.md).

## 1. Extrair e instalar

Use Windows 10/11 de 64 bits, Python 3.11 de 64 bits e uma conexao com a internet
para instalar as bibliotecas. O emulador exige .NET Framework 4.8, conforme seu
arquivo `EmuHawk.exe.config`. Se Windows indicar DLL/prerequisito ausente, instale
os prerequisitos oficiais do BizHawk 2.11.1 e repita; nao substitua o core SNES.

Extraia o ZIP inteiro para uma pasta local, por exemplo
`C:\TCC\TCC-TopGear-RL_v3.0`. Nao execute diretamente de dentro do ZIP.
A raiz correta e a pasta que contem `README.md`, `python`, `config` e `scripts`.
A `.venv` precisa ser criada nesse PC; ambientes virtuais copiados de outra
instalacao nao sao portaveis. A instalacao abaixo nao precisa de CUDA.

Abra essa pasta no VS Code e, no terminal PowerShell:

```powershell
Set-Location 'C:\TCC\TCC-TopGear-RL_v3.0'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Se `py -3.11` nao for encontrado, instale Python 3.11 x64, reabra o terminal
e repita. Espere `INSTALACAO OK` e os testes terminarem em `OK`.
No VS Code, selecione o interpretador `.venv\Scripts\python.exe` desta pasta.
Os scripts usam o caminho relativo da propria v3.0; nao e necessario usar
`C:\Users\luanb` nem ativar a `.venv` no terminal.

## 2. Preflight real do azul automatico

No terminal 1, na raiz do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_azul_automatico.ps1 -Modo Preflight
```

Quando o servidor estiver aguardando, abra outro terminal na MESMA pasta:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\abrir_bizhawk_pacote.ps1
```

Esse comando abre a ROM do pacote e inicializa o socket `127.0.0.1:55355`.
No BizHawk, confira o core **BSNESv115+**, usado pelos savestates fornecidos.
Em **Tools > Lua Console**, abra somente
`lua\Top Gear Azul Automatico (USA).lua`. Quando pedir o perfil, selecione
`config\game_profile_blue_auto.ini` da pasta extraida. O reset carrega o
save 3 automaticamente; nao grave outro save por cima dele.

Espere `PREFLIGHT OK`. Se houver falha, consulte o JSON indicado no terminal
antes de treinar. O teste verifica comunicacao, reset, controles e telemetria;
nao demonstra aprendizado. A ROM esperada tem SHA-1
`F686806C676A4B087A3627BABBE3555D3704E3B1`.

## 3. Somente assistir, sem aprendizado

Depois do preflight, feche o BizHawk e rode no terminal 1:

```powershell
$env:TOPGEAR_PROFILE = 'game_profile_blue_auto.ini'
.\.venv\Scripts\python.exe python\jogar_continuo.py --modo fiel --corridas 3
```

Abra o emulador pelo comando do terminal 2 e carregue novamente o Lua azul.
Esse modo usa o ator automatico anterior, sob transferencia explicita validada,
e joga tres corridas sem alterar pesos. O comportamento desse ator no carro
azul ainda deve ser avaliado; o pacote nao promete vitorias. Para decisoes
variadas da politica aprendida, use `--modo variado`. `Ctrl+C` encerra.

## 4. Piloto de treinamento, apenas apos PREFLIGHT OK

Feche o BizHawk, execute no terminal 1:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\treino_azul_automatico.ps1 -Modo Treinar -Passos 24576 -ImportarAtor '.\models\hermes-ppo_20260915_031924_155890\final_10240_steps.zip'
```

Abra o emulador pelo comando do terminal 2 e carregue o Lua azul.
O ator e importado; critico, otimizador e contador sao novos. Modelos e logs
novos vao para pastas novas. Para continuar um checkpoint criado com o contrato
v6 identico, use `-Retomar 'caminho_do_novo_modelo.zip'` em lugar de
`-ImportarAtor`. O parametro `-Passos` escolhe os passos adicionais; PPO completa
blocos de 2048. Compare o piloto antes de iniciar treinamento longo.

## 5. TensorBoard e erros comuns

```powershell
.\.venv\Scripts\python.exe -m tensorboard.main --logdir .\runs --port 6006
```

Abra `http://127.0.0.1:6006/` no navegador. Logs de objetivos diferentes nao
devem ser comparados somente pela recompensa total.

- **Socket nao inicializado:** abra BizHawk pelo script do pacote, depois de
  iniciar o servidor Python. Evite abrir `EmuHawk.exe` por duplo clique.
- **Conexao recusada:** o servidor Python nao esta aguardando em 55355.
- **Novo processo Python:** feche e reabra BizHawk pelo script para criar nova
  conexao, e carregue novamente o Lua.
- **Save/identidade divergentes:** confira core, ROM, save 3 e perfil selecionado.
- **Modelo incompativel:** preserve o `.zip` e seu `.zip.json` juntos; nao remova
  a validacao. Modelos manuais e automaticos possuem contratos diferentes.
- Os caminhos absolutos em relatorios antigos sao historicos. Para comandos
  atuais, siga este guia e use a pasta extraida.
