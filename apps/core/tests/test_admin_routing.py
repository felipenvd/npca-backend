from urllib.parse import parse_qs, urlsplit

import pytest
from django.urls import reverse


@pytest.mark.parametrize("path", ("/admin", "/admin/", "/admin/login/", "/admin/jsi18n/"))
def test_old_admin_routes_return_404_without_redirect(client, path):
    response = client.get(path)

    assert response.status_code == 404
    assert "Location" not in response


def test_admin_reverse_and_login_redirect_use_new_path(client):
    assert reverse("admin:index") == "/gestao-npca/"
    assert reverse("admin:login") == "/gestao-npca/login/"

    response = client.get(reverse("admin:index"))
    destination = urlsplit(response["Location"])

    assert response.status_code == 302
    assert destination.path == "/gestao-npca/login/"
    assert parse_qs(destination.query)["next"] == ["/gestao-npca/"]
    assert client.get("/gestao-npca")["Location"] == "/gestao-npca/"


def test_admin_internal_links_and_forms_use_new_path(admin_client):
    response = admin_client.get(reverse("admin:researchers_researcher_add"))
    html = response.content.decode()

    assert response.status_code == 200
    assert 'href="/gestao-npca/' in html
    assert "/gestao-npca/jsi18n/" in html
    assert 'href="/admin/' not in html
    assert 'action="/admin/' not in html
