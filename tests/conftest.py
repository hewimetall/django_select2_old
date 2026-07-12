import django
from django.conf import settings


if not settings.configured:
    settings.configure(
        AUTO_RENDER_SELECT2_STATICS=True,
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        DEFAULT_AUTO_FIELD="django.db.models.AutoField",
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.staticfiles",
            "django_select2",
        ],
        ROOT_URLCONF="django_select2.urls",
        SECRET_KEY="test-secret",
        STATIC_URL="/static/",
        USE_TZ=True,
    )

django.setup()
