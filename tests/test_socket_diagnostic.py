from __future__ import annotations

import socket
import sys
import threading
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
PYTHON_DIR = PROJECT_DIR / "python"
sys.path.insert(0, str(PYTHON_DIR))

from diagnostico_socket import (
    PREFIX,
    SocketDiagnosticError,
    encode_frame,
    perform_handshake,
    recv_frame,
)


class SocketDiagnosticTests(unittest.TestCase):
    def test_round_trip_uses_bizhawk_length_prefix(self) -> None:
        left, right = socket.socketpair()
        try:
            payload = "TGSOCK1|texto=ação"
            sender = threading.Thread(
                target=lambda: left.sendall(encode_frame(payload)), daemon=True
            )
            sender.start()
            self.assertEqual(recv_frame(right), payload)
            sender.join(timeout=1)
        finally:
            left.close()
            right.close()

    def test_rejects_invalid_length_prefix(self) -> None:
        left, right = socket.socketpair()
        try:
            left.sendall(b"x mensagem")
            with self.assertRaises(SocketDiagnosticError):
                recv_frame(right)
        finally:
            left.close()
            right.close()

    def test_python_initiates_ping_and_accepts_lua_ack(self) -> None:
        left, right = socket.socketpair()
        nonce = "123456"

        def lua_side() -> None:
            ping = recv_frame(right)
            self.assertEqual(ping, f"{PREFIX}|kind=ping|nonce={nonce}")
            right.sendall(encode_frame(f"{PREFIX}|status=ok|nonce={nonce}"))

        responder = threading.Thread(target=lua_side, daemon=True)
        try:
            responder.start()
            perform_handshake(left, nonce)
            responder.join(timeout=1)
            self.assertFalse(responder.is_alive())
        finally:
            left.close()
            right.close()


if __name__ == "__main__":
    unittest.main()
