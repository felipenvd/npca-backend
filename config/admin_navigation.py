from typing import Any

from django.contrib import admin
from django.http import HttpRequest


def sidebar_navigation(request: HttpRequest) -> list[dict[str, Any]]:
    app_list = admin.site.get_app_list(request)
    ordered_apps = [app for app in app_list if app["app_label"] != "labcompap"]
    ordered_apps.extend(app for app in app_list if app["app_label"] == "labcompap")

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
