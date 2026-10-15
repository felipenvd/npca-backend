from typing import Any

from django.contrib import admin
from django.http import HttpRequest


def sidebar_navigation(request: HttpRequest) -> list[dict[str, Any]]:
    app_list = admin.site.get_app_list(request)
    apps = {app["app_label"]: app for app in app_list}
    groups = (
        (
            "Conteúdo do site",
            ("news", "researchers", "projects", "events", "publications", "courses"),
        ),
        ("LabCompAp", ("labcompap",)),
        ("Administração", ("accounts", "auth")),
    )

    navigation = []
    for title, app_labels in groups:
        items = [
            {"title": model["name"], "link": model["admin_url"]}
            for app_label in app_labels
            for model in apps.get(app_label, {}).get("models", [])
            if model.get("admin_url")
        ]
        if items:
            navigation.append({"title": title, "items": items})
    return navigation
