from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
NINJA_DOCS_REQUIRE_STAFF = False

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
