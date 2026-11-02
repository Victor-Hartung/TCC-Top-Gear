# Diagnóstico da ponte por socket

Este teste não inicia treinamento, não envia controles e não lê nem altera a
memória do jogo. Ele apenas comprova se o Python e o Lua conseguem trocar uma
mensagem enquanto o BizHawk está pausado. O Python inicia o diálogo enviando um
`PING`; o Lua responde com o `ACK`, na mesma direção de comando/resposta que será
usada pelo ambiente de treino.

## Procedimento no Windows

1. Feche completamente o BizHawk.
2. No terminal do VS Code, na pasta raiz do projeto, execute:

   ```powershell
   python python\diagnostico_socket.py
   ```

3. Deixe esse terminal aberto mostrando `Servidor pronto em 127.0.0.1:55355`.
4. Abra um **segundo PowerShell**. Inicie o BizHawk substituindo apenas o caminho
   abaixo pelo local real do seu `EmuHawk.exe`:

   ```powershell
   & "C:\CAMINHO\PARA\BizHawk-2.11.1-win-x64\EmuHawk.exe" --socket-ip 127.0.0.1 --socket-port 55355
   ```

5. No BizHawk, abra a ROM normalmente.
6. Abra `Tools > Lua Console` e execute **somente**
   `lua\diagnostico_socket.lua`.
7. O resultado correto no primeiro terminal termina com:

   ```text
   SUCESSO: Python -> Lua -> Python funcionou com o BizHawk pausado.
   ```

Depois que o BizHawk conecta, o diagnóstico aguarda até 180 segundos para que a
ROM seja carregada e o script Lua seja iniciado manualmente.

Se o Windows perguntar sobre acesso à rede, permita apenas em rede privada. A
ponte escuta exclusivamente em `127.0.0.1`, isto é, no próprio computador.
