from __future__ import annotations

import socket
import time
import numbers
from dataclasses import dataclass
from typing import Mapping

from topgear_config import ProjectConfig


ACTION_PREFIX = "TGACT2"
STATE_PREFIX = "TGSTATE2"
MAX_MESSAGE_BYTES = 1_048_576
BRIDGE_REVISION = 5


class ProtocolError(RuntimeError):
    pass


class BridgeTimeout(ProtocolError):
    pass


def encode_message(prefix: str, fields: Mapping[str, object]) -> str:
    if any(ch in prefix for ch in "|=\r\n\x00") or not prefix:
        raise ProtocolError("Prefixo inválido")
    parts = [prefix]
    for key, value in fields.items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if not key_text or any(ch in key_text for ch in "=|\r\n"):
            raise ProtocolError(f"Chave inválida: {key!r}")
        if "|" in value_text or any(ord(ch) < 32 for ch in str(value)):
            raise ProtocolError(f"Valor inválido para {key_text}: {value_text!r}")
        parts.append(f"{key_text}={value_text}")
    return "|".join(parts)


def parse_message(text: str, expected_prefix: str) -> dict[str, str]:
    if any(ord(ch) < 32 for ch in text):
        raise ProtocolError("Caracter de controle no protocolo")
    raw = text.strip()
    if not raw:
        raise ProtocolError("Mensagem vazia")
    parts = raw.split("|")
    if parts[0] != expected_prefix:
        raise ProtocolError(
            f"Prefixo {parts[0]!r} incompatível; esperado {expected_prefix!r}"
        )
    result: dict[str, str] = {}
    for token in parts[1:]:
        if "=" not in token:
            raise ProtocolError(f"Campo sem '=': {token!r}")
        key, value = token.split("=", 1)
        if not key or key in result or not key.replace("_", "").isalnum():
            raise ProtocolError(f"Campo inválido ou duplicado: {key!r}")
        result[key] = value
    return result


def field_int(fields: Mapping[str, str], key: str) -> int:
    try:
        return int(fields[key], 0)
    except KeyError as exc:
        raise ProtocolError(f"Campo obrigatório ausente: {key}") from exc
    except ValueError as exc:
        raise ProtocolError(f"Campo {key} não é inteiro: {fields.get(key)!r}") from exc


def encode_frame(message: str) -> bytes:
    payload = message.encode("utf-8")
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ProtocolError("Mensagem excede o limite de segurança")
    return str(len(payload)).encode("ascii") + b" " + payload


def _recv_exact(connection: socket.socket, size: int, deadline: float | None = None) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        if deadline is not None:
            connection.settimeout(_remaining(deadline))
        chunk = connection.recv(remaining)
        if not chunk:
            raise ProtocolError("Conexão encerrada antes do fim da mensagem")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Prazo total da mensagem esgotado")
    return remaining


def recv_frame(connection: socket.socket, deadline: float | None = None) -> str:
    digits = bytearray()
    while True:
        if deadline is not None:
            connection.settimeout(_remaining(deadline))
        current = connection.recv(1)
        if not current:
            raise ProtocolError("Conexão encerrada antes do prefixo de tamanho")
        if current == b" ":
            break
        if current < b"0" or current > b"9" or len(digits) >= 10:
            raise ProtocolError("Prefixo de tamanho inválido")
        digits.extend(current)
    if not digits:
        raise ProtocolError("Prefixo de tamanho vazio")
    size = int(digits.decode("ascii"))
    if not 1 <= size <= MAX_MESSAGE_BYTES:
        raise ProtocolError("Mensagem recebida excede o limite de segurança")
    return _recv_exact(connection, size, deadline).decode("utf-8")


@dataclass(frozen=True)
class BridgeState:
    fields: dict[str, str]

    @property
    def status(self) -> str:
        return self.fields.get("status", "")

    @property
    def episode(self) -> int:
        return field_int(self.fields, "episode")

    @property
    def ack(self) -> int:
        return field_int(self.fields, "ack")

    @property
    def frame(self) -> int:
        return field_int(self.fields, "frame")


class BridgeClient:
    """Ponte TCP síncrona: Python envia uma ação e aguarda o ack do Lua."""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self.host = config.text("protocol", "socket_host")
        self.port = config.integer("protocol", "socket_port")
        self.startup_timeout = config.number("protocol", "startup_timeout_seconds")
        self.timeout = config.number("protocol", "timeout_seconds")
        self.max_repeat = config.integer("protocol", "max_repeat_frames")
        self.episode = 0
        self._sequence = time.time_ns() // 1_000_000
        self._last_state: BridgeState | None = None
        self._connection: socket.socket | None = None
        self._closed = False
        self._broken = False

        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            option = getattr(socket, "SO_EXCLUSIVEADDRUSE", socket.SO_REUSEADDR)
            self._server.setsockopt(socket.SOL_SOCKET, option, 1)
            self._server.bind((self.host, self.port))
            self._server.listen(1)
        except OSError as exc:
            self._server.close()
            raise ProtocolError(
                f"Não foi possível abrir a ponte em {self.host}:{self.port}: {exc}"
            ) from exc

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.getsockname()[:2]
        return str(host), int(port)

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _accept(self, timeout: float) -> None:
        self._server.settimeout(timeout)
        try:
            connection, _ = self._server.accept()
        except TimeoutError as exc:
            raise BridgeTimeout(
                "BizHawk não conectou ao socket dentro do prazo. Inicie-o com "
                f"--socket-ip {self.host} --socket-port {self.port}."
            ) from exc
        except OSError as exc:
            raise ProtocolError(f"Falha aceitando conexão do BizHawk: {exc}") from exc
        self._connection = connection
        connection.settimeout(self.timeout)
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def _send_text(self, text: str) -> None:
        if self._connection is None:
            raise ProtocolError("BizHawk ainda não está conectado")
        try:
            self._connection.settimeout(self.timeout)
            self._connection.sendall(encode_frame(text))
        except OSError as exc:
            self._broken = True
            raise ProtocolError(f"Falha enviando comando ao BizHawk: {exc}") from exc

    def _receive_state(self, timeout: float) -> BridgeState:
        if self._connection is None:
            raise ProtocolError("BizHawk ainda não está conectado")
        self._connection.settimeout(timeout)
        try:
            text = recv_frame(self._connection, time.monotonic() + timeout)
        except TimeoutError as exc:
            raise BridgeTimeout(
                f"Lua não respondeu pelo socket dentro de {timeout:g} segundos"
            ) from exc
        except (OSError, UnicodeError) as exc:
            raise ProtocolError(f"Falha recebendo estado do BizHawk: {exc}") from exc
        return BridgeState(parse_message(text, STATE_PREFIX))

    def _command_text(
        self, *, kind: str, action: int, frames: int, episode: int, seq: int
    ) -> str:
        return encode_message(
            ACTION_PREFIX,
            {
                "episode": episode,
                "seq": seq,
                "kind": kind,
                "action": action,
                "frames": frames,
            },
        )

    def wait_ready(self, timeout: float | None = None) -> BridgeState:
        if self._closed or self._broken:
            raise ProtocolError("Ponte fechada ou estado causal perdido; reinicie a sessao")
        if self._last_state is not None:
            return self._last_state
        startup_timeout = self.startup_timeout if timeout is None else float(timeout)
        if self._connection is None:
            self._accept(startup_timeout)
        seq = self._next_sequence()
        self._send_text(
            self._command_text(
                kind="hello", action=0, frames=0, episode=self.episode, seq=seq
            )
        )
        state = self._receive_state(startup_timeout)
        if state.status == "error":
            raise ProtocolError(
                "Lua não pôde iniciar a ponte: "
                + state.fields.get("error", "erro não informado")
            )
        if state.episode != self.episode or state.ack != seq:
            raise ProtocolError(
                "Resposta inicial fora de sequência: "
                f"episode={state.episode}, ack={state.ack}; esperado "
                f"episode={self.episode}, ack={seq}"
            )
        if state.status != "ready" or state.frame < 0:
            raise ProtocolError(
                f"Estado inicial inválido: status={state.status!r}, frame={state.frame}"
            )
        if field_int(state.fields, "bridge_revision") != self.config.bridge_revision:
            raise ProtocolError("Lua incompatível: execute o script da pasta v3.0")
        if field_int(state.fields, "profile_crc") != self.config.profile_crc:
            raise ProtocolError("Lua e Python abriram perfis diferentes; escolha config/game_profile.ini da v3.0")
        if field_int(state.fields, "protocol_version") != 2:
            raise ProtocolError("Versao de protocolo divergente")
        if state.fields.get("rom_hash", "").lower() != self.config.text("identity", "rom_sha1").lower():
            raise ProtocolError("SHA-1 da ROM divergente")
        if field_int(state.fields, "domain_size") != 131072:
            raise ProtocolError("Tamanho WRAM divergente")
        self._last_state = state
        return state

    def _send(
        self,
        *,
        kind: str,
        action: int,
        frames: int,
        episode: int,
    ) -> tuple[int, BridgeState]:
        if self._closed or self._broken:
            raise ProtocolError("A ponte já foi fechada")
        if not 0 <= frames <= self.max_repeat:
            raise ProtocolError(f"frames fora do intervalo 0..{self.max_repeat}")
        if self._connection is None:
            raise ProtocolError("Chame wait_ready() antes de enviar comandos")
        seq = self._next_sequence()
        self._send_text(
            self._command_text(
                kind=kind,
                action=action,
                frames=frames,
                episode=episode,
                seq=seq,
            )
        )
        try:
            state = self._receive_state(self.timeout)
        except ProtocolError:
            self._broken = True
            raise
        if state.episode != episode or state.ack != seq:
            self._broken = True
            raise ProtocolError(
                "Ack fora de sequência: "
                f"episode={state.episode}, ack={state.ack}; esperado "
                f"episode={episode}, ack={seq}"
            )
        if state.status == "error":
            self._broken = True
            raise ProtocolError(
                "Lua recusou o comando: "
                + state.fields.get("error", "erro não informado")
            )
        expected_status = "closed" if kind == "close" else "ok"
        if state.status != expected_status:
            self._broken = True
            raise ProtocolError(
                f"Status inesperado: {state.status!r}; esperado {expected_status!r}"
            )
        if self.config.manual_transmission and kind in ("reset", "step"):
            from manual_transmission import validate_wire
            try:
                validate_wire(state.fields)
            except ProtocolError:
                self._broken = True
                raise
        if self.config.blue_auto_expected and kind in ("reset", "step"):
            from blue_auto import validate_wire
            try:
                validate_wire(state.fields)
            except ProtocolError:
                self._broken = True
                raise
        self._last_state = state
        return seq, state

    def reset(self) -> BridgeState:
        self.episode += 1
        _, state = self._send(kind="reset", action=0, frames=0, episode=self.episode)
        if field_int(state.fields, "reset_ok") != 1:
            self._broken = True
            raise ProtocolError("Lua respondeu ao reset sem confirmar reset_ok=1")
        return state

    def step(self, action: int, frames: int | None = None) -> BridgeState:
        if isinstance(action, bool) or not isinstance(action, numbers.Integral) or not 0 <= action < self.config.action_count:
            raise ProtocolError("Acao deve ser um inteiro pertencente ao espaco")
        repeat = self.config.frame_repeat if frames is None else frames
        if isinstance(repeat, bool) or not isinstance(repeat, numbers.Integral) or not 1 <= repeat <= self.max_repeat:
            raise ProtocolError("frames deve ser inteiro positivo no intervalo configurado")
        previous = self._last_state
        _, state = self._send(
            kind="step",
            action=int(action),
            frames=repeat,
            episode=self.episode,
        )
        if previous is not None and previous.episode == state.episode:
            if ('load_events' in previous.fields and 'load_events' in state.fields
                    and field_int(previous.fields, 'load_events') != field_int(state.fields, 'load_events')):
                self._broken = True
                raise ProtocolError("Savestate carregado fora do comando reset; sessao encerrada")
            delta = state.frame - previous.frame
            if delta != repeat:
                self._broken = True
                raise ProtocolError(
                    f"Delta de frames inválido: esperado {repeat}, recebido {delta}"
                )
        return state

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self._connection is not None and self._last_state is not None and not self._broken:
                try:
                    self._send(kind="close", action=0, frames=0, episode=self.episode)
                except ProtocolError:
                    pass
        finally:
            self._closed = True
            if self._connection is not None:
                try:
                    self._connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self._connection.close()
                self._connection = None
            self._server.close()
