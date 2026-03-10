"""WT901WIFI streaming frame parser."""

from __future__ import annotations

from typing import Any

from .const import BATTERY_THRESHOLDS, FRAME_FOOTER, FRAME_HEADER, FRAME_LENGTH


def int16_signed(low: int, high: int) -> int:
    """Convert little-endian bytes to a signed int16."""
    value = (high << 8) | low
    if value >= 0x8000:
        value -= 0x10000
    return value


def uint16_unsigned(low: int, high: int) -> int:
    """Convert little-endian bytes to an unsigned int16."""
    return (high << 8) | low


def battery_percentage_from_raw(raw_bat: int) -> int:
    """Map battery register raw value to percentage using vendor thresholds."""
    if raw_bat > 396:
        return 100
    if raw_bat <= 340:
        return 0

    for threshold, percent in BATTERY_THRESHOLDS:
        if raw_bat > threshold:
            return percent
    return 0


def _is_ascii_digits(raw: bytes) -> bool:
    return all(0x30 <= b <= 0x39 for b in raw)


def parse_streaming_frame(frame: bytes | bytearray) -> dict[str, Any] | None:
    """Parse a WT901WIFI 54-byte streaming frame.

    Returns parsed dict for valid streaming frame, or None when frame is invalid.
    """
    if not isinstance(frame, (bytes, bytearray)):
        return None
    if len(frame) != FRAME_LENGTH:
        return None
    if frame[0:4] != FRAME_HEADER:
        return None
    if frame[52:54] != FRAME_FOOTER:
        return None

    id_digits = bytes(frame[4:12])
    if not _is_ascii_digits(id_digits):
        return None

    def s16(index: int) -> int:
        return int16_signed(frame[index], frame[index + 1])

    def u16(index: int) -> int:
        return uint16_unsigned(frame[index], frame[index + 1])

    device_suffix = id_digits.decode("ascii")
    device_id = f"WT55{device_suffix}"

    raw_bat = s16(46)

    return {
        "device_id": device_id,
        "device_suffix": device_suffix,
        "time": {
            "year": 2000 + frame[12],
            "month": frame[13],
            "day": frame[14],
            "hour": frame[15],
            "minute": frame[16],
            "second": frame[17],
            "millisecond": u16(18),
        },
        "acc_x_g": round(s16(20) / 32768.0 * 16.0, 3),
        "acc_y_g": round(s16(22) / 32768.0 * 16.0, 3),
        "acc_z_g": round(s16(24) / 32768.0 * 16.0, 3),
        "gyro_x_dps": round(s16(26) / 32768.0 * 2000.0, 3),
        "gyro_y_dps": round(s16(28) / 32768.0 * 2000.0, 3),
        "gyro_z_dps": round(s16(30) / 32768.0 * 2000.0, 3),
        "mag_x_ut": round(s16(32) * 100.0 / 1024.0, 3),
        "mag_y_ut": round(s16(34) * 100.0 / 1024.0, 3),
        "mag_z_ut": round(s16(36) * 100.0 / 1024.0, 3),
        "roll_deg": round(s16(38) / 32768.0 * 180.0, 2),
        "pitch_deg": round(s16(40) / 32768.0 * 180.0, 2),
        "yaw_deg": round(s16(42) / 32768.0 * 180.0, 2),
        "temperature_c": round(s16(44) / 100.0, 2),
        "battery_raw": raw_bat,
        "battery_voltage_v": round(raw_bat / 100.0, 2),
        "battery_percentage": battery_percentage_from_raw(raw_bat),
        "rssi_dbm": s16(48),
        "version": u16(50),
    }
