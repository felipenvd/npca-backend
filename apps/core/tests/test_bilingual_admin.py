from html.parser import HTMLParser

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.accounts.models import User
from apps.researchers.models import Researcher, ResearcherTranslation
from apps.researchers.tests.test_admin import researcher_data


class FormValues(HTMLParser):
    """Collect the controls a browser submits, including hidden inline identities."""

    def __init__(self, html, form_id):
        super().__init__()
        self.form_id = form_id
        self.in_form = False
        self.values = {}
        self.select = None
        self.textarea = None
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "form":
            self.in_form = attrs.get("id") == self.form_id
        if not self.in_form or "disabled" in attrs:
            return
        name = attrs.get("name")
        if tag == "input" and name:
            if attrs.get("type") in {"file", "submit", "button"}:
                return
            if attrs.get("type") in {"checkbox", "radio"} and "checked" not in attrs:
                return
            self.values[name] = attrs.get("value", "on" if attrs.get("type") == "checkbox" else "")
        elif tag == "select" and name:
            self.select = name
        elif tag == "option" and self.select:
            if self.select not in self.values or "selected" in attrs:
                self.values[self.select] = attrs.get("value", "")
        elif tag == "textarea" and name:
            self.textarea = name
            self.values[name] = ""

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_form = False
        elif tag == "select":
            self.select = None
        elif tag == "textarea":
            self.textarea = None

    def handle_data(self, data):
        if self.textarea:
            self.values[self.textarea] += data


@pytest.mark.parametrize(
    ("route", "first", "second"),
    (
        ("researchers_researcher", "research_area", "biography_html"),
        ("news_news", "title", "summary"),
        ("projects_project", "title", "summary"),
        ("publications_publication", "title", "abstract"),
        ("events_event", "title", "summary"),
        ("courses_course", "title", "summary"),
    ),
)
def test_add_forms_pair_fields_and_defer_advanced_options(admin_client, route, first, second):
    response = admin_client.get(reverse(f"admin:{route}_add"))
    html = response.content.decode()

    assert response.status_code == 200
    assert '<select name="translations-0-language"' not in html
    assert '<select name="translations-1-language"' not in html
    assert "Tradução: #" not in html
    assert (
        html.index(f'for="id_translations-0-{first}"')
        < html.index(f'for="id_translations-1-{first}"')
        < html.index(f'for="id_translations-0-{second}"')
        < html.index(f'for="id_translations-1-{second}"')
    )
    assert html.count('name="translations-TOTAL_FORMS"') == 1
    assert "— Português" in html
    assert "— Inglês" in html
    advanced = html.index("<details")
    assert "open" not in html[advanced : html.index(">", advanced)]
    assert html.index(f'for="id_translations-1-{second}"') < advanced
    main_section = "Apresentação" if route == "news_news" else "Dados gerais"
    assert html.index(
        'for="id_is_active"' if "researchers" in route else 'for="id_status"'
    ) < html.index(main_section)
    if "courses" not in route:
        assert html.index('name="translations-0-seo_title"') > advanced
    assert 'for="id_created_at"' not in html


def test_change_form_pairs_existing_locales_and_preserves_urls_and_seo(admin_client):
    researcher = Researcher.objects.create(full_name="Ana Silva", academic_category="doctor")
    english = ResearcherTranslation.objects.create(
        researcher=researcher,
        language="en",
        slug="ana-profile",
        research_area="English area",
        biography_html="<p>Biography</p>",
        seo_title="Custom English SEO",
    )
    portuguese = ResearcherTranslation.objects.create(
        researcher=researcher,
        language="pt-br",
        slug="perfil-ana",
        research_area="Área portuguesa",
        biography_html="<p>Biografia</p>",
        seo_title="SEO em português",
    )
    url = reverse("admin:researchers_researcher_change", args=(researcher.pk,))
    html = admin_client.get(url).content.decode()
    # The queryset sorts English first, but Portuguese must still appear first.
    assert html.index('for="id_translations-1-research_area"') < html.index(
        'for="id_translations-0-research_area"'
    )
    values = FormValues(html, "researcher_form").values
    assert values["translations-0-id"] == str(english.pk)
    assert values["translations-1-id"] == str(portuguese.pk)
    values.update({"translations-1-research_area": "Área atualizada", "_save": "Salvar"})

    response = admin_client.post(url, values)

    assert response.status_code == 302
    english.refresh_from_db()
    portuguese.refresh_from_db()
    assert english.research_area == "English area"
    assert portuguese.research_area == "Área atualizada"
    assert english.slug == "ana-profile"
    assert portuguese.slug == "perfil-ana"
    assert english.seo_title == "Custom English SEO"
    assert portuguese.seo_title == "SEO em português"
    assert researcher.translations.count() == 2


def test_existing_portuguese_profile_can_add_english_from_paired_form(admin_client):
    researcher = Researcher.objects.create(full_name="Ana Silva", academic_category="doctor")
    ResearcherTranslation.objects.create(
        researcher=researcher,
        language="pt-br",
        slug="perfil-ana",
        research_area="Área",
        biography_html="<p>Biografia</p>",
    )
    url = reverse("admin:researchers_researcher_change", args=(researcher.pk,))
    html = admin_client.get(url).content.decode()
    values = FormValues(html, "researcher_form").values
    assert values["translations-1-language"] == "en"
    values.update(
        {
            "translations-1-research_area": "Research area",
            "translations-1-biography_html": "<p>Biography</p>",
            "is_active": "on",
            "_save": "Salvar",
        }
    )

    response = admin_client.post(url, values)

    assert response.status_code == 302
    researcher.refresh_from_db()
    assert researcher.is_active is True
    assert researcher.translations.get(language="en").slug == "ana-silva"
    assert researcher.translations.get(language="pt-br").slug == "perfil-ana"


def test_validation_keeps_entered_values_and_displays_hidden_locale_errors(admin_client):
    data = researcher_data(active=False)
    data.update(
        {
            "translations-0-language": "invalid",
            "translations-0-research_area": "Texto que não pode desaparecer",
            "translations-1-research_area": "Keep this English text",
        }
    )
    response = admin_client.post(reverse("admin:researchers_researcher_add"), data)
    html = response.content.decode()

    assert response.status_code == 200
    assert not Researcher.objects.exists()
    assert "Texto que não pode desaparecer" in html
    assert "Keep this English text" in html
    assert "invalid" in html
    assert "Faça uma escolha válida" in html


@pytest.mark.django_db
def test_view_only_staff_can_still_read_both_translations(client):
    user = User.objects.create_user("reader@npca.example", "strong-password", is_staff=True)
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="researchers",
            codename__in=("view_researcher", "view_researchertranslation"),
        )
    )
    researcher = Researcher.objects.create(full_name="Ana Silva", academic_category="doctor")
    for language, area in (("pt-br", "Área portuguesa"), ("en", "English area")):
        ResearcherTranslation.objects.create(
            researcher=researcher, language=language, research_area=area
        )
    client.force_login(user)

    response = client.get(reverse("admin:researchers_researcher_change", args=(researcher.pk,)))

    assert response.status_code == 200
    assert "Área portuguesa" in response.content.decode()
    assert "English area" in response.content.decode()
    assert 'name="translations-0-research_area"' not in response.content.decode()


@pytest.mark.parametrize("model", ("labequipment", "labgalleryimage"))
def test_labcompap_forms_group_locales_and_hide_display_order(admin_client, model):
    response = admin_client.get(reverse(f"admin:labcompap_{model}_add"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "português e inglês" in html
    assert html.index('name="display_order"') > html.index("<details")
