from __future__ import annotations

import copy
import socket
import sys
import threading
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from protocol import (  # noqa: E402
    ACTION_PREFIX,
    STATE_PREFIX,
    BridgeClient,
    ProtocolError,
    encode_frame,
    encode_message,
    parse_message,
    recv_frame,
)
from topgear_config import ProjectConfig  # noqa: E402


def socket_test_config() -> ProjectConfig:
    base = ProjectConfig.load(ROOT)
    parser = copy.deepcopy(base.parser)
    parser.set("protocol", "socket_port", "0")
    parser.set("protocol", "startup_timeout_seconds", "1")
    parser.set("protocol", "timeout_seconds", "1")
    return replace(base, parser=parser)


def send_state(connection: socket.socket, **fields: object) -> None:
    cfg = ProjectConfig.load(ROOT)
    defaults = {'bridge_revision': 5, 'profile_crc': cfg.profile_crc, 'protocol_version': 2,
                'rom_hash': cfg.text('identity', 'rom_sha1'), 'domain_size': 131072}
    fields = {**defaults, **fields}
    connection.sendall(encode_frame(encode_message(STATE_PREFIX, fields)))


class ProtocolTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        text = encode_message(
            ACTION_PREFIX,
            {"episode": 2, "seq": 10, "kind": "step", "action": 3, "frames": 4},
        )
        fields = parse_message(text, ACTION_PREFIX)
        self.assertEqual(fields["episode"], "2")
        self.assertEqual(fields["action"], "3")

    def test_rejects_wrong_prefix_and_duplicates(self) -> None:
        with self.assertRaises(ProtocolError):
            parse_message("OLD|a=1", STATE_PREFIX)
        with self.assertRaises(ProtocolError):
            parse_message("TGSTATE2|a=1|a=2", STATE_PREFIX)

    def test_rejects_delimiter_in_value(self) -> None:
        with self.assertRaises(ProtocolError):
            encode_message(ACTION_PREFIX, {"kind": "bad|value"})

    def test_socket_frame_round_trip(self) -> None:
        left, right = socket.socketpair()
        try:
            message = "TGSTATE2|status=ação"
            left.sendall(encode_frame(message))
            self.assertEqual(recv_frame(right), message)
        finally:
            left.close()
            right.close()

    def test_wait_ready_reports_lua_startup_error_immediately(self) -> None:
        client = BridgeClient(socket_test_config())

        def fake_lua() -> None:
            with socket.create_connection(client.address, timeout=1) as connection:
                hello = parse_message(recv_frame(connection), ACTION_PREFIX)
                send_state(
                    connection,
                    status="error",
                    episode=hello["episode"],
                    ack=-1,
                    frame=10,
                    error="ROM_SHA1_incorreto",
                )

        worker = threading.Thread(target=fake_lua, daemon=True)
        worker.start()
        try:
            with self.assertRaisesRegex(ProtocolError, "ROM_SHA1_incorreto"):
                client.wait_ready()
        finally:
            client.close()
            worker.join(timeout=1)

    def test_client_waits_for_matching_ack_and_fixed_frames(self) -> None:
        client = BridgeClient(socket_test_config())
        errors: list[BaseException] = []

        def fake_lua() -> None:
            frame = 100
            try:
                with socket.create_connection(client.address, timeout=1) as connection:
                    while True:
                        command = parse_message(recv_frame(connection), ACTION_PREFIX)
                        kind = command["kind"]
                        episode = int(command["episode"])
                        seq = int(command["seq"])
                        reset_ok = 0
                        status = "ok"
                        if kind == "hello":
                            status = "ready"
                        elif kind == "reset":
                            frame = 50
                            reset_ok = 1
                        elif kind == "step":
                            frame += int(command["frames"])
                        elif kind == "close":
                            status = "closed"
                        send_state(
                            connection,
                            status=status,
                            episode=episode,
                            ack=seq,
                            frame=frame,
                            reset_ok=reset_ok,
                        )
                        if kind == "close":
                            break
            except BaseException as exc:  # encaminha falha da thread ao teste
                errors.append(exc)

        worker = threading.Thread(target=fake_lua, daemon=True)
        worker.start()
        try:
            ready = client.wait_ready()
            self.assertEqual(ready.frame, 100)
            reset_state = client.reset()
            self.assertEqual(reset_state.frame, 50)
            step_state = client.step(0, frames=4)
            self.assertEqual(step_state.frame, 54)
        finally:
            client.close()
            worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
