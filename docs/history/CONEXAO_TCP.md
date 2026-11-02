# Conexão TCP principal

A ordem é obrigatória porque o Python funciona como servidor e o BizHawk se
conecta a ele durante a inicialização.

## Teste causal da ponte

1. Feche completamente o BizHawk.
2. No terminal do VS Code, na raiz do projeto, execute:

   ```powershell
   python python\test_connection.py --steps 3
   ```

3. Deixe o terminal em `Servidor da ponte pronto`.
4. Em outro PowerShell, abra o BizHawk usando o caminho real do executável:

   ```powershell
   & "C:\CAMINHO\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
   ```

5. Carregue a ROM Top Gear (USA) com SHA-1
   `F686806C676A4B087A3627BABBE3555D3704E3B1`.
6. Abra `Tools > Lua Console` e execute somente `lua\Top Gear (USA).lua`.
7. O terminal deve mostrar `ack neutro 1`, `ack neutro 2`, `ack neutro 3` e:

   ```text
   OK: sequência, ack e delta fixo de frames estão corretos.
   ```

Esse primeiro teste não carrega o savestate. Depois de aprovado, repita todo o
procedimento desde o passo 1 usando:

```powershell
python python\test_connection.py --reset --steps 3
```

O slot 1 precisa conter o savestate correto da largada.

Durante a sessão, cada frame usa `client.unpause() + emu.yield()`, conforme a
orientação da API do BizHawk 2.11.1. O contador do emulador confirma uma unidade
por iteração. Entre comandos, a recepção TCP bloqueia o loop principal; portanto,
somente os frames pedidos pelo Python são executados. Ao receber `CLOSE`, o Lua
neutraliza os botões e pausa o emulador.

## Regras operacionais

- Execute o comando Python antes de abrir o BizHawk.
- Use sempre a mesma porta configurada em `config/game_profile.ini`.
- Não execute dois scripts Lua ao mesmo tempo.
- Depois que um comando Python termina, feche e reabra o BizHawk antes de
  iniciar outro teste ou o treinamento; a conexão pertence ao processo Python
  que a criou.
- A ponte escuta somente em `127.0.0.1` e não aceita conexões externas.
