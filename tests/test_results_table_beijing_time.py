from __future__ import annotations

from sn_manager.gui.main_window import format_display_timestamp


def test_format_display_timestamp_passthrough_when_utc() -> None:
    raw = "2026-07-31T01:02:03Z"
    assert format_display_timestamp(raw, use_beijing=False) == raw


def test_format_display_timestamp_beijing_from_z() -> None:
    # UTC 01:02:03 → 北京 09:02:03
    assert (
        format_display_timestamp("2026-07-31T01:02:03Z", use_beijing=True)
        == "2026-07-31 09:02:03"
    )


def test_format_display_timestamp_beijing_from_offset() -> None:
    assert (
        format_display_timestamp("2026-07-31T01:02:03+00:00", use_beijing=True)
        == "2026-07-31 09:02:03"
    )


def test_format_display_timestamp_invalid_passthrough() -> None:
    raw = "not-a-timestamp"
    assert format_display_timestamp(raw, use_beijing=True) == raw
