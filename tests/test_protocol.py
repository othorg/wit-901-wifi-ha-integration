from pathlib import Path

from custom_components.wit_901_wifi.protocol import (
    battery_percentage_from_raw,
    int16_signed,
    parse_streaming_frame,
)


def test_int16_signed_negative_conversion() -> None:
    assert int16_signed(0xBD, 0xFF) == -67


def test_parse_valid_streaming_frame(fixtures_dir: Path) -> None:
    frame = (fixtures_dir / "frame_valid.bin").read_bytes()
    parsed = parse_streaming_frame(frame)

    assert parsed is not None
    assert parsed["device_id"] == "WT5500001234"
    assert parsed["device_suffix"] == "00001234"
    assert parsed["roll_deg"] == 90.0
    assert parsed["pitch_deg"] == -45.0
    assert parsed["yaw_deg"] == 22.5
    assert parsed["temperature_c"] == 25.34
    assert parsed["battery_voltage_v"] == 3.85
    assert parsed["battery_percentage"] == 60
    assert parsed["rssi_dbm"] == -67
    assert parsed["version"] == 13011


def test_parse_invalid_header_returns_none(fixtures_dir: Path) -> None:
    frame = (fixtures_dir / "frame_invalid_header.bin").read_bytes()
    assert parse_streaming_frame(frame) is None


def test_parse_truncated_frame_returns_none(fixtures_dir: Path) -> None:
    frame = (fixtures_dir / "frame_truncated.bin").read_bytes()
    assert parse_streaming_frame(frame) is None


def test_battery_mapping_thresholds() -> None:
    assert battery_percentage_from_raw(397) == 100
    assert battery_percentage_from_raw(396) == 90
    assert battery_percentage_from_raw(388) == 75
    assert battery_percentage_from_raw(385) == 60
    assert battery_percentage_from_raw(339) == 0
