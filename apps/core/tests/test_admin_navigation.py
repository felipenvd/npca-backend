import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission

from apps.accounts.models import User
from config.admin_navigation import sidebar_navigation


def test_sidebar_groups_content_lab_and_administration_without_losing_links(admin_client):
    response = admin_client.get("/gestao-npca/")
    request = response.wsgi_request

    navigation = sidebar_navigation(request)
    app_list = admin.site.get_app_list(request)

    assert response.status_code == 200
    assert [group["title"] for group in navigation] == [
        "Conteúdo do site",
        "LabCompAp",
        "Administração",
    ]
    assert [item["title"] for item in navigation[0]["items"]] == [
        "Notícias",
        "Pesquisadores",
        "Projetos",
        "Eventos",
        "Publicações",
        "Cursos e tutoriais",
    ]
    links = [item["link"] for group in navigation for item in group["items"]]
    expected_links = [
        model["admin_url"] for app in app_list for model in app["models"] if model.get("admin_url")
    ]
    assert sorted(links) == sorted(expected_links)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("app_label", "model", "group"),
    (
        ("news", "news", "Conteúdo do site"),
        ("labcompap", "labequipment", "LabCompAp"),
        ("accounts", "user", "Administração"),
    ),
)
def test_sidebar_only_includes_permitted_items_and_nonempty_groups(client, app_label, model, group):
    user = User.objects.create_user("reader@npca.example", "strong-password", is_staff=True)
    permission = Permission.objects.get(content_type__app_label=app_label, codename=f"view_{model}")
    user.user_permissions.add(permission)
    client.force_login(user)

    response = client.get("/gestao-npca/")
    navigation = sidebar_navigation(response.wsgi_request)

    assert response.status_code == 200
    assert [section["title"] for section in navigation] == [group]
    assert len(navigation[0]["items"]) == 1
    assert navigation[0]["items"][0]["link"] == f"/gestao-npca/{app_label}/{model}/"
