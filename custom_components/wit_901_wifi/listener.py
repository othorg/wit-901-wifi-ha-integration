"""UDP/TCP listener for WIT 901 WIFI streaming frames."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from .const import FRAME_HEADER, FRAME_LENGTH, PROTOCOL_TCP, PROTOCOL_UDP
from .protocol import parse_streaming_frame

_LOGGER = logging.getLogger(__name__)


class WitUdpProtocol(asyncio.DatagramProtocol):
    """Handle incoming UDP datagrams containing WT901WIFI frames."""

    def __init__(
        self, device_id: str, on_frame: Callable[[dict[str, Any]], None]
    ) -> None:
        self._device_id = device_id
        self._on_frame = on_frame

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        parsed = parse_streaming_frame(data)
        if parsed is None:
            return
        if parsed["device_id"] != self._device_id:
            _LOGGER.debug(
                "Ignoring frame from %s (expected %s)",
                parsed["device_id"],
                self._device_id,
            )
            return
        self._on_frame(parsed)

    def error_received(self, exc: Exception) -> None:
        _LOGGER.warning("UDP listener error: %s", exc)


class WitTcpProtocol(asyncio.Protocol):
    """Handle incoming TCP stream and extract WT901WIFI frames."""

    def __init__(
        self, device_id: str, on_frame: Callable[[dict[str, Any]], None]
    ) -> None:
        self._device_id = device_id
        self._on_frame = on_frame
        self._buffer = bytearray()

    def data_received(self, data: bytes) -> None:
        self._buffer.extend(data)
        self._process_buffer()

    def _process_buffer(self) -> None:
        while len(self._buffer) >= FRAME_LENGTH:
            idx = self._buffer.find(FRAME_HEADER)
            if idx < 0:
                self._buffer.clear()
                return
            if idx > 0:
                del self._buffer[:idx]
            if len(self._buffer) < FRAME_LENGTH:
                return
            frame = bytes(self._buffer[:FRAME_LENGTH])
            del self._buffer[:FRAME_LENGTH]
            parsed = parse_streaming_frame(frame)
            if parsed is None:
                continue
            if parsed["device_id"] != self._device_id:
                _LOGGER.debug("Ignoring frame from %s", parsed["device_id"])
                continue
            self._on_frame(parsed)

    def connection_lost(self, exc: Exception | None) -> None:
        _LOGGER.debug("TCP connection lost: %s", exc)


class WitListener:
    """Manage a UDP or TCP listener for WT901WIFI frames."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        protocol_type: str,
        host: str,
        port: int,
        device_id: str,
        on_frame: Callable[[dict[str, Any]], None],
    ) -> None:
        self._loop = loop
        self._protocol_type = protocol_type
        self._host = host
        self._port = port
        self._device_id = device_id
        self._on_frame = on_frame
        self._transport: asyncio.BaseTransport | None = None
        self._server: asyncio.AbstractServer | None = None

    async def async_start(self) -> None:
        """Start the listener."""
        if self._protocol_type == PROTOCOL_UDP:
            transport, _ = await self._loop.create_datagram_endpoint(
                lambda: WitUdpProtocol(self._device_id, self._on_frame),
                local_addr=(self._host, self._port),
            )
            self._transport = transport
            _LOGGER.info("UDP listener started on %s:%s", self._host, self._port)
        elif self._protocol_type == PROTOCOL_TCP:
            self._server = await self._loop.create_server(
                lambda: WitTcpProtocol(self._device_id, self._on_frame),
                self._host,
                self._port,
            )
            _LOGGER.info("TCP listener started on %s:%s", self._host, self._port)
        else:
            raise ValueError(f"Unsupported protocol: {self._protocol_type}")

    async def async_stop(self) -> None:
        """Stop the listener and release resources."""
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        _LOGGER.info("Listener stopped on %s:%s", self._host, self._port)
