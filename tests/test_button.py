"""Tests for reboot button entity."""

from __future__ import annotations

import inspect


def test_reboot_button_class_definition():
    """Verify button entity has correct class-level attribute declarations."""
    from custom_components.wit_901_wifi.button import WitRebootButton

    source = inspect.getsource(WitRebootButton)
    assert "ButtonDeviceClass.RESTART" in source
    assert "EntityCategory.CONFIG" in source
    assert '_attr_translation_key = "reboot"' in source
    assert "_attr_has_entity_name = True" in source


def test_reboot_button_unique_id_format():
    """Verify unique_id uses expected pattern."""
    from custom_components.wit_901_wifi.button import WitRebootButton

    source = inspect.getsource(WitRebootButton.__init__)
    assert "_{coordinator.device_id}_reboot" in source


def test_reboot_button_calls_async_reboot():
    """Verify async_press delegates to coordinator.async_reboot."""
    from custom_components.wit_901_wifi.button import WitRebootButton

    source = inspect.getsource(WitRebootButton.async_press)
    assert "self.coordinator.async_reboot()" in source
