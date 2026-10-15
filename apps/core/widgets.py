from typing import Any

from django import forms
from unfold.widgets import DATETIME_CLASSES


class PickerMedia:
    css = {"all": ("core/admin/date_time_picker.css",)}
    js = ("core/admin/date_time_picker.js",)


def picker_attrs(attrs: dict[str, Any] | None, kind: str, placeholder: str) -> dict[str, Any]:
    attrs = attrs or {}
    return {
        **attrs,
        "class": " ".join(
            [*DATETIME_CLASSES, attrs.get("class", ""), f"npca-enhanced-{kind}-field"]
        ),
        "data-npca-picker": kind,
        "placeholder": attrs.get("placeholder", placeholder),
        "autocomplete": "off",
        "inputmode": "none",
        "readonly": True,
        "role": "combobox",
        "aria-haspopup": "dialog",
        "aria-expanded": "false",
    }


class EnhancedAdminDateWidget(forms.DateInput):
    """Brazilian date input with an accessible, inline calendar popover."""

    template_name = "core/widgets/picker.html"
    Media = PickerMedia

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        format: str | None = None,
    ) -> None:
        super().__init__(
            attrs=picker_attrs(attrs, "date", "dd/mm/aaaa"), format=format or "%d/%m/%Y"
        )


class EnhancedAdminTimeWidget(forms.TimeInput):
    """24-hour input with separate hour and minute controls."""

    template_name = "core/widgets/picker.html"
    Media = PickerMedia

    def __init__(self, attrs: dict[str, Any] | None = None, format: str | None = None) -> None:
        super().__init__(attrs=picker_attrs(attrs, "time", "hh:mm"), format=format or "%H:%M")
