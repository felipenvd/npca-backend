from pathlib import Path

import environ
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(DJANGO_DEBUG=(bool, False))

if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-development-key")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts.apps.AccountsConfig",
    "apps.core.apps.CoreConfig",
    "apps.news.apps.NewsConfig",
    "apps.researchers.apps.ResearchersConfig",
    "apps.projects.apps.ProjectsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.middleware.ApiProblemDetailsMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Belem"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles")))
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
NINJA_DOCS_REQUIRE_STAFF = False


UNFOLD = {
    "SITE_TITLE": _("NPCA Admin"),
    "SITE_HEADER": _("NPCA"),
    "SITE_SUBHEADER": _("Núcleo de Pesquisa em Computação Aplicada"),
    "SITE_URL": "/",
    "SITE_LOGO": lambda _request: static("npca/logo-npca.png"),
    "SITE_SYMBOL": "science",
    "COLORS": {
        "primary": {
            "50": "#e6fffe",
            "100": "#bdfcf9",
            "200": "#7cf5f0",
            "300": "#42e4df",
            "400": "#1acec8",
            "500": "#00bab3",
            "600": "#009a96",
            "700": "#087b79",
            "800": "#0b6261",
            "900": "#0d5150",
            "950": "#003132",
        },
    },
}
