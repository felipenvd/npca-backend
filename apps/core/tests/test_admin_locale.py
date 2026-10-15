import pytest
from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import translation

from apps.core.middleware import AdminLocaleMiddleware


@pytest.mark.parametrize("path", ("/gestao-npca", "/gestao-npca/", "/gestao-npca/jsi18n/"))
def test_admin_middleware_uses_pt_br_despite_browser_and_cookie(path):
    request = RequestFactory().get(path, HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")
    request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = "pt"
    middleware = AdminLocaleMiddleware(lambda request: HttpResponse())

    with translation.override("en"):
        response = middleware(request)
        assert request.LANGUAGE_CODE == "pt-br"
        assert translation.get_language() == "pt-br"
        assert response["Content-Language"] == "pt-br"
        assert settings.LANGUAGE_COOKIE_NAME not in response.cookies


@pytest.mark.parametrize(
    "path", ("/api/v1/news", "/gestao-npca-extra/", "/admin/", "/media/photo.webp")
)
def test_other_routes_keep_normal_language_negotiation(path):
    request = RequestFactory().get(path, HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")
    middleware = AdminLocaleMiddleware(lambda request: HttpResponse())

    with translation.override("pt-br"):
        response = middleware(request)
        assert request.LANGUAGE_CODE == "en"
        assert response["Content-Language"] == "en"


@pytest.mark.django_db
@pytest.mark.parametrize("language", ("en", "pt", "pt-br"))
def test_admin_groups_and_navigation_are_brazilian_portuguese(admin_client, language):
    admin_client.cookies[settings.LANGUAGE_COOKIE_NAME] = language
    response = admin_client.get("/gestao-npca/auth/group/", HTTP_ACCEPT_LANGUAGE=language)
    html = response.content.decode()

    assert response.status_code == 200
    assert response["Content-Language"] == "pt-br"
    assert 'lang="pt-br"' in html
    assert 'placeholder="Digite para buscar"' in html
    assert "Nenhum resultado encontrado" in html
    assert "Adicione um novo item ou limpe os filtros." in html
    assert "Usuários" in html
    assert "Alterar senha" in html
    assert "Claro" in html
    assert "Escuro" in html
    assert "Sistema" in html
    assert "No results found" not in html
    assert "Utilizadores" not in html


@pytest.mark.django_db
def test_login_and_forms_use_project_translations(client, admin_client):
    login = client.get("/gestao-npca/login/", HTTP_ACCEPT_LANGUAGE="en")
    assert login.status_code == 200
    assert "Bem-vindo ao" in login.content.decode()
    assert "Voltar ao site" in login.content.decode()

    form = admin_client.get("/gestao-npca/accounts/user/add/", HTTP_ACCEPT_LANGUAGE="en")
    assert form.status_code == 200
    assert (
        "Após criar o usuário, você poderá editar outras opções da conta." in form.content.decode()
    )

    javascript = admin_client.get("/gestao-npca/jsi18n/", HTTP_ACCEPT_LANGUAGE="en")
    assert javascript.status_code == 200
    assert javascript["Content-Language"] == "pt-br"


@pytest.mark.django_db
def test_api_language_is_not_stuck_in_admin_locale(admin_client):
    admin_client.get("/gestao-npca/", HTTP_ACCEPT_LANGUAGE="en")
    response = admin_client.get("/api/v1/news", {"lang": "en"}, HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 200
    assert response["Content-Language"] == "en"


def test_unfold_catalogues_include_formatted_messages_and_plurals():
    with translation.override("pt-br"):
        assert translation.gettext("Type to search") == "Digite para buscar"
        assert translation.gettext("Select action") == "Selecionar ação"
        assert translation.gettext("Choose file to upload") == "Selecione um arquivo para enviar"
        assert translation.gettext("Toggle password visibility") == "Mostrar ou ocultar senha"
        assert translation.gettext("Add row") == "Adicionar linha"
        source = "impersonate %(username)s"
        assert translation.gettext(source) % {"username": "Teste"} == "Acessar como Teste"
        singular = "\n                    Export %(len)s selected item.\n                "
        plural = "\n                    Export %(len)s selected items.\n                "
        assert "Exportar 1 item selecionado" in (
            translation.ngettext(singular, plural, 1) % {"len": 1}
        )
        assert "Exportar 2 itens selecionados" in (
            translation.ngettext(singular, plural, 2) % {"len": 2}
        )
