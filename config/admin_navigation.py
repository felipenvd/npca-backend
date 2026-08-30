from typing import Any

from django.contrib import admin
from django.http import HttpRequest


def sidebar_navigation(request: HttpRequest) -> list[dict[str, Any]]:
    app_list = admin.site.get_app_list(request)
    preferred_order = {
        app_label: index
        for index, app_label in enumerate(
            (
                "accounts",
                "events",
                "news",
                "researchers",
                "projects",
                "publications",
                "courses",
                "labcompap",
            )
        )
    }
    ordered_apps = sorted(
        app_list,
        key=lambda app: preferred_order.get(app["app_label"], -1),
    )

    return [
        {
            "title": app["name"],
            "items": [
                {
                    "title": model["name"],
                    "link": model["admin_url"],
                }
                for model in app["models"]
                if model.get("admin_url")
            ],
        }
        for app in ordered_apps
    ]
