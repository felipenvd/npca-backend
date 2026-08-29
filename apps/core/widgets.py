from typing import Any

from unfold.widgets import UnfoldAdminDateWidget


class EnhancedAdminDateWidget(UnfoldAdminDateWidget):
    """Unfold date picker enhanced with direct month and year selectors."""

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        format: str | None = None,
    ) -> None:
        attrs = attrs or {}
        super().__init__(
            attrs={
                **attrs,
                "class": " ".join(
                    filter(
                        None,
                        (attrs.get("class", ""), "npca-enhanced-date-field"),
                    )
                ),
                "placeholder": attrs.get("placeholder", "dd/mm/aaaa"),
                "autocomplete": "off",
            },
            format=format,
        )

    class Media:
        css = {"all": ("core/admin/enhanced_date_picker.css",)}
        js = (
            "admin/js/core.js",
            "admin/js/calendar.js",
            "admin/js/admin/DateTimeShortcuts.js",
            "core/admin/enhanced_date_picker.js",
        )
