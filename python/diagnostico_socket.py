from __future__ import annotations

import argparse
import socket
import time


PREFIX = "TGSOCK1"
MAX_MESSAGE_BYTES = 1_048_576


class SocketDiagnosticError(RuntimeError):
    pass


def encode_frame(message: str) -> bytes:
    payload = message.encode("utf-8")
    if len(payload) > MAX_MESSAGE_BYTES:
        raise SocketDiagnosticError("Mensagem excede o limite de segurança")
    return str(len(payload)).encode("ascii") + b" " + payload


def _recv_exact(connection: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise SocketDiagnosticError("Conexão encerrada antes do fim da mensagem")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_frame(connection: socket.socket) -> str:
    digits = bytearray()
    while True:
        current = connection.recv(1)
        if not current:
            raise SocketDiagnosticError("Conexão encerrada antes do prefixo de tamanho")
        if current == b" ":
            break
        if current < b"0" or current > b"9" or len(digits) >= 10:
            raise SocketDiagnosticError("Prefixo de tamanho inválido")
        digits.extend(current)
    if not digits:
        raise SocketDiagnosticError("Prefixo de tamanho vazio")
    size = int(digits.decode("ascii"))
    if size > MAX_MESSAGE_BYTES:
        raise SocketDiagnosticError("Mensagem recebida excede o limite de segurança")
    return _recv_exact(connection, size).decode("utf-8")


def perform_handshake(connection: socket.socket, nonce: str) -> None:
    ping = f"{PREFIX}|kind=ping|nonce={nonce}"
    connection.sendall(encode_frame(ping))
    print("PING enviado ao BizHawk; aguardando ACK do Lua.")
    reply = recv_frame(connection)
    expected = f"{PREFIX}|status=ok|nonce={nonce}"
    if reply != expected:
        raise SocketDiagnosticError(
            f"Resposta inesperada: {reply!r}; esperada: {expected!r}"
        )


def run(
    host: str,
    port: int,
    accept_timeout: float,
    handshake_timeout: float,
) -> None:
    nonce = str(time.time_ns())
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        server.settimeout(accept_timeout)
        print(f"Servidor pronto em {host}:{port}.")
        print("Agora inicie o BizHawk com --socket-ip e --socket-port e execute")
        print("somente lua/diagnostico_socket.lua.")
        try:
            connection, address = server.accept()
        except TimeoutError as exc:
            raise SocketDiagnosticError(
                "Nenhuma conexão do BizHawk chegou dentro do prazo"
            ) from exc

        with connection:
            connection.settimeout(handshake_timeout)
            print(f"BizHawk conectado por {address[0]}:{address[1]}.")
            perform_handshake(connection, nonce)

    print("SUCESSO: Python -> Lua -> Python funcionou com o BizHawk pausado.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Valida a ponte TCP do BizHawk sem iniciar o treinamento"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55355)
    parser.add_argument("--accept-timeout", type=float, default=180.0)
    parser.add_argument("--handshake-timeout", type=float, default=180.0)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port deve estar entre 1 e 65535")
    if args.accept_timeout <= 0 or args.handshake_timeout <= 0:
        parser.error("os timeouts devem ser positivos")
    try:
        run(args.host, args.port, args.accept_timeout, args.handshake_timeout)
    except (OSError, UnicodeError, SocketDiagnosticError) as exc:
        raise SystemExit(f"FALHA: {exc}") from exc


if __name__ == "__main__":
    main()
