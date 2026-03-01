"""Minimal Django settings for the taxomesh test suite."""

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "taxomesh.contrib.django",
]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
