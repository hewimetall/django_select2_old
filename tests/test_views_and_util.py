import json
import threading

import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory

from django_select2 import util
from django_select2.fields import AutoViewFieldMixin
from django_select2.views import AutoResponseView, JSONResponseMixin, NO_ERR_RESP, Select2View


class ExampleView(Select2View):
    def get_results(self, request, term, page, context):
        return NO_ERR_RESP, page < 2, [
            ("1", "One"),
            ("2", "Two", {"group": "numbers"}),
        ]


class DeniedView(Select2View):
    def check_all_permissions(self, request, *args, **kwargs):
        raise PermissionDenied("blocked")


class MissingView(Select2View):
    def check_all_permissions(self, request, *args, **kwargs):
        raise Http404("missing")


class DummyAutoField(AutoViewFieldMixin):
    def security_check(self, request, *args, **kwargs):
        return getattr(self, "allowed", True)

    def get_results(self, request, term, page, context):
        return NO_ERR_RESP, False, [(self.field_id, "%s:%s" % (term, context))]


@pytest.fixture(autouse=True)
def reset_registry(monkeypatch):
    util.__dict__["__id_store"].clear()
    util.__dict__["__field_store"].clear()
    monkeypatch.setattr(util, "GENERATE_RANDOM_ID", False)


def body(response):
    return json.loads(response.content.decode("utf-8"))


def test_extract_some_key_val_keeps_present_values_only():
    assert util.extract_some_key_val({"a": 1, "b": None, "c": False}, ["a", "b", "c", "d"]) == {
        "a": 1,
        "c": False,
    }


def test_id_validation():
    assert util.is_valid_id("abc:123 +-.")
    assert not util.is_valid_id("bad/slash")


def test_synchronized_serializes_calls():
    calls = []

    @util.synchronized
    def append(value):
        calls.append(value)
        return len(calls)

    results = []
    threads = [threading.Thread(target=lambda val=i: results.append(append(val))) for i in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [1, 2, 3]
    assert sorted(calls) == [0, 1, 2]


def test_register_field_is_deterministic_and_retrievable():
    field = DummyAutoField(auto_id="example")

    assert util.get_field(field.field_id) is field
    assert util.register_field("example", field) == field.field_id


def test_register_field_rejects_invalid_type():
    with pytest.raises(ValueError):
        util.register_field("bad", object())


def test_random_registration_path(monkeypatch):
    monkeypatch.setattr(util, "GENERATE_RANDOM_ID", True)
    field = DummyAutoField(auto_id="random")

    assert field.field_id.startswith("0:")
    assert util.get_field(field.field_id) is field


def test_json_response_mixin_serializes_context():
    response = JSONResponseMixin().render_to_response({"ok": True})

    assert response["Content-Type"] == "application/json"
    assert body(response) == {"ok": True}


def test_select2_view_get_success_and_validation_errors():
    factory = RequestFactory()

    ok = ExampleView.as_view()(factory.get("/select2/", {"term": "o", "page": "1", "context": "ctx"}))
    assert body(ok) == {
        "err": NO_ERR_RESP,
        "more": True,
        "results": [
            {"id": "1", "text": "One"},
            {"id": "2", "text": "Two", "group": "numbers"},
        ],
    }

    missing_term = ExampleView.as_view()(factory.get("/select2/", {"page": "1"}))
    assert body(missing_term)["err"] == "missing term"

    bad_page = ExampleView.as_view()(factory.get("/select2/", {"term": "o", "page": "x"}))
    assert body(bad_page)["err"] == "bad page no."

    non_positive_page = ExampleView.as_view()(factory.get("/select2/", {"term": "o", "page": "0"}))
    assert body(non_positive_page)["err"] == "bad page no."


def test_select2_view_permission_exception_responses():
    factory = RequestFactory()

    denied = DeniedView.as_view()(factory.get("/select2/"))
    assert denied.status_code == 403
    assert body(denied)["err"] == "blocked"

    missing = MissingView.as_view()(factory.get("/select2/"))
    assert missing.status_code == 404
    assert body(missing)["err"] == "missing"


def test_select2_view_base_get_results_not_implemented():
    with pytest.raises(NotImplementedError):
        Select2View().get_results(None, "term", 1, None)


def test_auto_response_view_routes_to_registered_field():
    factory = RequestFactory()
    field = DummyAutoField(auto_id="route")

    response = AutoResponseView.as_view()(
        factory.get("/select2/", {"field_id": field.field_id, "term": "abc", "page": "1", "context": "ctx"})
    )

    assert body(response)["results"] == [{"id": field.field_id, "text": "abc:ctx"}]


def test_auto_response_view_rejects_missing_unknown_and_denied_fields():
    factory = RequestFactory()

    missing = AutoResponseView.as_view()(factory.get("/select2/", {"term": "abc", "page": "1"}))
    assert missing.status_code == 404
    assert body(missing)["err"] == "field_id not found or is invalid"

    unknown = AutoResponseView.as_view()(
        factory.get("/select2/", {"field_id": "abc", "term": "abc", "page": "1"})
    )
    assert unknown.status_code == 404
    assert body(unknown)["err"] == "field_id not found"

    field = DummyAutoField(auto_id="denied")
    field.allowed = False
    denied = AutoResponseView.as_view()(
        factory.get("/select2/", {"field_id": field.field_id, "term": "abc", "page": "1"})
    )
    assert denied.status_code == 403
    assert body(denied)["err"] == "permission denied"
