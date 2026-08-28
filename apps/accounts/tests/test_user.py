import pytest
from django.conf import settings
from django.urls import reverse

from apps.accounts.forms import AdminUserChangeForm, AdminUserCreationForm
from apps.accounts.models import User


@pytest.mark.django_db
def test_create_user_with_email() -> None:
    user = User.objects.create_user("Researcher@NPCA.example", "strong-password")

    assert user.email == "Researcher@npca.example"
    assert user.check_password("strong-password")
    assert user.username is None


@pytest.mark.django_db
def test_admin_login_uses_email(client) -> None:
    User.objects.create_superuser("admin@npca.example", "strong-password")

    response = client.post(
        reverse("admin:login"),
        {"username": "admin@npca.example", "password": "strong-password"},
    )

    assert response.status_code == 302
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_unfold_admin_uses_npca_branding(client) -> None:
    response = client.get(reverse("admin:login"))

    assert response.status_code == 200
    assert "NPCA Admin" in response.content.decode()
    assert settings.UNFOLD["COLORS"]["primary"]["500"] == "#00bab3"
    assert settings.UNFOLD["SITE_LOGO"](None) == "/static/npca/logo-npca.png"
    assert "THEME" not in settings.UNFOLD


@pytest.mark.django_db
def test_admin_user_creation_form_uses_email_without_username() -> None:
    form = AdminUserCreationForm(
        data={
            "email": "editor@npca.example",
            "password1": "a-secure-admin-password",
            "password2": "a-secure-admin-password",
            "usable_password": "true",
        }
    )

    assert form.is_valid(), form.errors
    user = form.save()
    assert user.email == "editor@npca.example"
    assert user.check_password("a-secure-admin-password")
    assert "username" not in form.fields


@pytest.mark.django_db
def test_admin_user_change_form_uses_email_without_username() -> None:
    user = User.objects.create_user("researcher@npca.example", "strong-password")
    form = AdminUserChangeForm(instance=user)

    assert "email" in form.fields
    assert "username" not in form.fields


@pytest.mark.django_db
def test_unfold_user_and_group_pages_are_available(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    client.force_login(admin_user)

    dashboard_response = client.get(reverse("admin:index"))
    user_add_response = client.get(reverse("admin:accounts_user_add"))
    group_response = client.get(reverse("admin:auth_group_changelist"))

    assert dashboard_response.status_code == 200
    assert user_add_response.status_code == 200
    assert group_response.status_code == 200
    assert b'name="email"' in user_add_response.content
    assert b'name="username"' not in user_add_response.content


@pytest.mark.django_db
def test_admin_can_change_user_password(client) -> None:
    admin_user = User.objects.create_superuser("admin@npca.example", "strong-password")
    user = User.objects.create_user("researcher@npca.example", "old-password")
    client.force_login(admin_user)

    response = client.post(
        reverse("admin:auth_user_password_change", args=[user.pk]),
        {
            "password1": "a-new-secure-password",
            "password2": "a-new-secure-password",
        },
    )

    user.refresh_from_db()
    assert response.status_code == 302
    assert user.check_password("a-new-secure-password")
