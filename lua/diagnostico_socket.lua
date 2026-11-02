-- Diagnóstico isolado da API comm.socket* do BizHawk 2.11.1.
-- O BizHawk precisa ser iniciado com:
--   --socket-ip 127.0.0.1 --socket-port 55355
-- Execute o servidor Python antes de abrir o BizHawk.

local PREFIX = "TGSOCK1"

assert(comm, "API comm indisponivel")
assert(comm.socketServerIsConnected, "comm.socketServerIsConnected indisponivel")
assert(comm.socketServerSend, "comm.socketServerSend indisponivel")
assert(comm.socketServerResponse, "comm.socketServerResponse indisponivel")
assert(comm.socketServerSetTimeout, "comm.socketServerSetTimeout indisponivel")
assert(client and client.pause, "client.pause indisponivel")

client.pause()
comm.socketServerSetTimeout(10000)

assert(comm.socketServerIsConnected(),
  "Socket nao conectado. Feche o BizHawk e abra-o com --socket-ip e --socket-port")

console.log("Socket conectado; aguardando PING do Python com o jogo pausado")
local command = comm.socketServerResponse()
assert(command and command ~= "", "PING vazio ou timeout esperando o Python")
local nonce = command:match("^" .. PREFIX .. "|kind=ping|nonce=(%d+)$")
assert(nonce, "PING invalido: " .. tostring(command))

local sent = comm.socketServerSend(PREFIX .. "|status=ok|nonce=" .. nonce)
assert(sent and sent > 0, "Falha enviando ACK ao Python")
console.log("SUCESSO: Python -> Lua -> Python funcionou com o BizHawk pausado")
