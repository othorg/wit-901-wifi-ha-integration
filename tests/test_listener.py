"""Tests for UDP/TCP listener protocol handlers."""

from pathlib import Path

from custom_components.wit_901_wifi.listener import WitTcpProtocol, WitUdpProtocol

EXPECTED_DEVICE_ID = "WT5500001234"


def test_udp_processes_valid_frame(fixtures_dir: Path) -> None:
    frames: list[dict] = []
    proto = WitUdpProtocol(EXPECTED_DEVICE_ID, frames.append)
    frame = (fixtures_dir / "frame_valid.bin").read_bytes()
    proto.datagram_received(frame, ("192.168.1.100", 12345))
    assert len(frames) == 1
    assert frames[0]["device_id"] == EXPECTED_DEVICE_ID
    assert frames[0]["source_ip"] == "192.168.1.100"


def test_udp_ignores_wrong_device(fixtures_dir: Path) -> None:
    frames: list[dict] = []
    proto = WitUdpProtocol("WT5599999999", frames.append)
    frame = (fixtures_dir / "frame_valid.bin").read_bytes()
    proto.datagram_received(frame, ("192.168.1.100", 12345))
    assert len(frames) == 0


def test_udp_ignores_invalid_frame() -> None:
    frames: list[dict] = []
    proto = WitUdpProtocol(EXPECTED_DEVICE_ID, frames.append)
    proto.datagram_received(b"garbage", ("192.168.1.100", 12345))
    assert len(frames) == 0


def test_tcp_processes_complete_frame(fixtures_dir: Path) -> None:
    frames: list[dict] = []
    proto = WitTcpProtocol(EXPECTED_DEVICE_ID, frames.append)
    frame = (fixtures_dir / "frame_valid.bin").read_bytes()

    # Simulate connection_made with peername
    class FakeTransport:
        def get_extra_info(self, key):
            if key == "peername":
                return ("192.168.1.200", 54321)
            return None

    proto.connection_made(FakeTransport())
    proto.data_received(frame)
    assert len(frames) == 1
    assert frames[0]["device_id"] == EXPECTED_DEVICE_ID
    assert frames[0]["source_ip"] == "192.168.1.200"


def test_tcp_handles_split_frame(fixtures_dir: Path) -> None:
    frames: list[dict] = []
    proto = WitTcpProtocol(EXPECTED_DEVICE_ID, frames.append)
    frame = (fixtures_dir / "frame_valid.bin").read_bytes()
    proto.data_received(frame[:30])
    assert len(frames) == 0
    proto.data_received(frame[30:])
    assert len(frames) == 1


def test_tcp_skips_garbage_prefix(fixtures_dir: Path) -> None:
    frames: list[dict] = []
    proto = WitTcpProtocol(EXPECTED_DEVICE_ID, frames.append)
    frame = (fixtures_dir / "frame_valid.bin").read_bytes()
    proto.data_received(b"\x00\x01\x02" + frame)
    assert len(frames) == 1


def test_tcp_filters_wrong_device_id(fixtures_dir: Path) -> None:
    frames: list[dict] = []
    proto = WitTcpProtocol("WT5599999999", frames.append)
    frame = (fixtures_dir / "frame_valid.bin").read_bytes()
    proto.data_received(frame)
    assert len(frames) == 0


def test_tcp_handles_multiple_consecutive_frames(fixtures_dir: Path) -> None:
    frames: list[dict] = []
    proto = WitTcpProtocol(EXPECTED_DEVICE_ID, frames.append)
    frame = (fixtures_dir / "frame_valid.bin").read_bytes()
    proto.data_received(frame + frame + frame)
    assert len(frames) == 3


def test_tcp_handles_garbage_between_frames(fixtures_dir: Path) -> None:
    frames: list[dict] = []
    proto = WitTcpProtocol(EXPECTED_DEVICE_ID, frames.append)
    frame = (fixtures_dir / "frame_valid.bin").read_bytes()
    proto.data_received(frame + b"\xff\xfe" + frame)
    assert len(frames) == 2
