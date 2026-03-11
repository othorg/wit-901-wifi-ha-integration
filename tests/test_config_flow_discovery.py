from pathlib import Path

from custom_components.wit_901_wifi.config_flow import _extract_device_id_from_payload

EXPECTED_DEVICE_ID = "WT5500001234"


def _load_valid_frame(fixtures_dir: Path) -> bytes:
    return (fixtures_dir / "frame_valid.bin").read_bytes()


def test_extract_device_id_from_exact_frame(fixtures_dir: Path) -> None:
    payload = _load_valid_frame(fixtures_dir)
    assert _extract_device_id_from_payload(payload) == EXPECTED_DEVICE_ID


def test_extract_device_id_from_prefixed_payload(fixtures_dir: Path) -> None:
    payload = b"\x00\xffgarbage" + _load_valid_frame(fixtures_dir)
    assert _extract_device_id_from_payload(payload) == EXPECTED_DEVICE_ID


def test_extract_device_id_from_multi_frame_payload(fixtures_dir: Path) -> None:
    frame = _load_valid_frame(fixtures_dir)
    payload = b"xx" + frame + frame + b"yy"
    assert _extract_device_id_from_payload(payload) == EXPECTED_DEVICE_ID


def test_extract_device_id_returns_none_for_invalid_payload(fixtures_dir: Path) -> None:
    payload = (fixtures_dir / "frame_invalid_header.bin").read_bytes()
    assert _extract_device_id_from_payload(payload) is None
