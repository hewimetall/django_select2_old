from django.utils.safestring import SafeString
from django.conf import settings

from django_select2 import media
from django_select2.templatetags import django_select2_tags as tags


def test_static_paths_are_prefixed():
    assert media.django_select2_static("js/select2.js") == "/static/django_select2/js/select2.js"


def test_js_libs_switch_on_debug(monkeypatch):
    monkeypatch.setattr(media, "DEBUG", True)
    assert media.get_select2_js_libs() == ("/static/django_select2/js/select2.js",)
    assert media.get_select2_heavy_js_libs() == (
        "/static/django_select2/js/select2.js",
        "/static/django_select2/js/heavy_data.js",
    )

    monkeypatch.setattr(media, "DEBUG", False)
    assert media.get_select2_js_libs() == ("/static/django_select2/js/select2.min.js",)
    assert media.get_select2_heavy_js_libs() == (
        "/static/django_select2/js/select2.min.js",
        "/static/django_select2/js/heavy_data.min.js",
    )


def test_css_libs_cover_bootstrap_and_light_modes(monkeypatch):
    monkeypatch.setattr(media, "DEBUG", True)
    monkeypatch.setattr(media, "BOOTSTRAP", True)
    assert media.get_select2_css_libs(light=True) == [
        "/static/django_select2/css/select2.css",
        "/static/django_select2/css/select2-bootstrap.css",
    ]
    assert media.get_select2_css_libs(light=False) == [
        "/static/django_select2/css/select2.css",
        "/static/django_select2/css/extra.css",
        "/static/django_select2/css/select2-bootstrap.css",
    ]

    monkeypatch.setattr(media, "DEBUG", False)
    assert media.get_select2_css_libs(light=True) == [
        "/static/django_select2/css/select2-bootstrapped.min.css",
    ]
    assert media.get_select2_css_libs(light=False) == [
        "/static/django_select2/css/all-bootstrapped.min.css",
    ]

    monkeypatch.setattr(media, "BOOTSTRAP", False)
    monkeypatch.setattr(media, "DEBUG", True)
    monkeypatch.setattr(settings, "DEBUG", True)
    assert media.get_select2_css_libs(light=True) == [
        "/static/django_select2/css/select2.css",
    ]
    assert media.get_select2_css_libs(light=False) == [
        "/static/django_select2/css/select2.css",
        "/static/django_select2/css/extra.css",
    ]

    monkeypatch.setattr(media, "DEBUG", False)
    monkeypatch.setattr(settings, "DEBUG", False)
    assert media.get_select2_css_libs(light=True) == [
        "/static/django_select2/css/select2.min.css",
    ]
    assert media.get_select2_css_libs(light=False) == [
        "/static/django_select2/css/all.min.css",
    ]


def test_template_tags_return_safe_html():
    js = tags.import_js(light=1)
    css = tags.import_css(light=1)
    combined = tags.import_all(light=1)

    assert isinstance(js, SafeString)
    assert isinstance(css, SafeString)
    assert isinstance(combined, SafeString)
    assert '<script type="text/javascript" src="/static/django_select2/js/select2.min.js"></script>' in js
    assert "heavy_data.min.js" in tags.import_js(light=0)
    assert '<link href="/static/django_select2/css/select2.min.css" rel="stylesheet">' in css
    assert "\n" in combined
