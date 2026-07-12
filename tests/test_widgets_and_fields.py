import json

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.utils.datastructures import MultiValueDict

from django_select2 import fields
from django_select2.widgets import (
    AutoHeavySelect2MultipleWidget,
    AutoHeavySelect2TagWidget,
    AutoHeavySelect2Widget,
    HeavySelect2MultipleWidget,
    HeavySelect2TagWidget,
    HeavySelect2Widget,
    MultipleSelect2HiddenInput,
    Select2MultipleWidget,
    Select2Widget,
)


def test_select2_widget_options_and_render(monkeypatch):
    monkeypatch.setattr("django_select2.widgets.RENDER_SELECT2_STATICS", True)
    widget = Select2Widget(
        attrs={"id": "id_choice"},
        choices=[("1", "One")],
        select2_options={"placeholder": 123, "closeOnSelect": True},
    )
    widget.is_required = False

    rendered = widget.render("choice", "1")
    options = widget.get_options()

    assert options["allowClear"] is True
    assert options["placeholder"] == "123"
    assert options["closeOnSelect"] is True
    assert 'value="1" selected' in rendered
    assert '<option value=""></option>' in rendered
    assert "/static/django_select2/js/select2.min.js" in rendered
    assert "$(hashedSelector).select2" in rendered


def test_select2_required_widget_disables_clear_and_keeps_existing_empty_choice():
    widget = Select2Widget(choices=[("", "Empty"), ("1", "One")])
    widget.is_required = True
    html = widget.render("choice", "", attrs={"id": "id_choice"})

    assert widget.get_options()["allowClear"] is False
    assert html.count('<option value="" selected>Empty</option>') == 1


def test_select2_multiple_widget_removes_single_value_options():
    widget = Select2MultipleWidget(choices=[("1", "One")])

    assert "multiple" not in widget.options
    assert "allowClear" not in widget.options
    assert "minimumResultsForSearch" not in widget.options


def test_multiple_hidden_input_render_data_and_change_detection():
    widget = MultipleSelect2HiddenInput()
    rendered = widget.render("items", ["1", "2"], attrs={"id": "id_items"})

    assert 'name="items"' in rendered
    assert 'multiple="multiple"' in rendered
    assert "django_select2.convertArrToStr" in rendered
    assert widget.value_from_datadict(MultiValueDict({"items": ["1", "2"]}), {}, "items") == ["1", "2"]
    assert widget.value_from_datadict({"items": "1"}, {}, "items") == "1"
    assert widget._has_changed(["1", "2"], ["2", "1"]) is False
    assert widget._has_changed(["1"], ["1", "2"]) is True
    assert widget.is_hidden is False


def test_heavy_widget_requires_data_source_and_renders_options():
    with pytest.raises(ValueError):
        HeavySelect2Widget()

    widget = HeavySelect2Widget(data_url="/choices/", choices=[("1", "One")])
    widget.field = None
    rendered = widget.render("heavy", "1", attrs={"id": "id_heavy"})

    assert widget.is_hidden is False
    assert '"url": "/choices/"' in rendered
    assert "django_select2.onInit" in rendered
    assert "$('#id_heavy').txt" in rendered
    assert "window.django_select2.id_heavy" in rendered


def test_heavy_widget_resolves_view_name(monkeypatch):
    widget = HeavySelect2Widget(data_view="django_select2_central_json")
    widget.field = None

    assert widget.url is None
    options = widget.get_options()
    assert options["ajax"]["url"] == "/fields/auto.json"


def test_heavy_multiple_and_tag_widgets_options_and_prefix_rendering():
    multiple = HeavySelect2MultipleWidget(data_url="/choices/")
    assert multiple.options["multiple"] is True
    assert "allowClear" not in multiple.options
    assert multiple.render_inner_js_code("__prefix__") == ""

    tag = HeavySelect2TagWidget(data_url="/choices/")
    assert tag.options["tags"] is True
    assert tag.options["tokenSeparators"] == [",", " "]
    assert "createSearchChoice" in tag.options
    assert tag.render_inner_js_code("__prefix__") == ""


def test_auto_heavy_widgets_force_central_view_and_prefix_rendering():
    for cls in (AutoHeavySelect2Widget, AutoHeavySelect2MultipleWidget, AutoHeavySelect2TagWidget):
        widget = cls()
        widget.field_id = "field-id"
        assert widget.view == "django_select2_central_json"
        assert widget.render_inner_js_code("__prefix__") == ""


def test_render_texts_uses_choices_and_field_fallback():
    class FieldFallback:
        def get_pk_field_name(self):
            return "pk"

        def _get_val_txt(self, value):
            return "Fallback %s" % value

    widget = HeavySelect2MultipleWidget(data_url="/choices/", choices=[("1", "One")])
    widget.field = FieldFallback()

    rendered = widget.render_texts(["1", "2"], [("3", "Three")])
    assert json.loads(rendered) == ["One", "Fallback 1", "Fallback 2"]


def test_choice_fields_use_select2_widgets_and_validate():
    assert fields.Select2ChoiceField.widget is Select2Widget
    assert fields.Select2MultipleChoiceField.widget is Select2MultipleWidget
    assert fields.ModelSelect2Field.widget is Select2Widget
    assert fields.ModelSelect2MultipleField.widget is Select2MultipleWidget

    field = fields.HeavyChoiceField(choices=[("1", "One")])
    assert field.clean("1") == "1"
    with pytest.raises(ValidationError):
        field.clean("missing")

    class PermissiveField(fields.HeavyChoiceField):
        def validate_value(self, value):
            return value == "external"

        def get_val_txt(self, value):
            return "External"

    permissive = PermissiveField()
    assert permissive.clean("external") == "external"
    assert permissive._get_val_txt("external") == "External"


def test_heavy_choice_field_handles_coercion_errors():
    class IntField(fields.HeavyChoiceField):
        def coerce_value(self, value):
            return int(value)

    with pytest.raises(ValidationError):
        IntField().clean("not-int")

    assert IntField()._get_val_txt("not-int") is None


def test_heavy_multiple_choice_and_tag_validation():
    multiple = fields.HeavyMultipleChoiceField(required=True, choices=[("1", "One")])
    assert multiple.clean(["1"]) == ["1"]
    with pytest.raises(ValidationError):
        multiple.clean("1")
    with pytest.raises(ValidationError):
        multiple.clean([])
    with pytest.raises(ValidationError):
        multiple.clean(["missing"])

    class TagField(fields.HeavySelect2TagField):
        def create_new_value(self, value):
            return "created-%s" % value

    tag = TagField(widget=HeavySelect2TagWidget(data_url="/choices/"), choices=[("1", "One")])
    cleaned = tag.clean(["1", "new"])
    assert cleaned == ["1", "created-new"]

    with pytest.raises(NotImplementedError):
        fields.HeavySelect2TagField(
            widget=HeavySelect2TagWidget(data_url="/choices/"),
            choices=[],
        ).clean(["new"])


def test_model_result_json_mixin_uses_queryset_like_object():
    class Item:
        def __init__(self, pk, name):
            self.pk = pk
            self.name = name

        def __str__(self):
            return self.name

    class QuerySetLike:
        model = Item

        def __init__(self, items):
            self.items = list(items)
            self.filters = []

        def __deepcopy__(self, memo):
            return QuerySetLike(self.items)

        def filter(self, *args, **kwargs):
            self.filters.append((args, kwargs))
            return self

        def distinct(self):
            return self

        def __getitem__(self, value):
            if isinstance(value, slice):
                return self.items[value]
            return self.items[value]

        def __iter__(self):
            return iter(self.items)

    class SearchField(fields.ModelResultJsonMixin, forms.Field):
        queryset = QuerySetLike([Item(1, "One"), Item(2, "Two"), Item(3, "Three")])
        search_fields = ["name__icontains"]
        max_results = 2

        def extra_data_from_instance(self, obj):
            return {"slug": obj.name.lower()}

    field = SearchField()
    err, has_more, results = field.get_results(None, "o", 1, None)

    assert err == "nil"
    assert has_more is True
    assert results == [(1, "One", {"slug": "one"}), (2, "Two", {"slug": "two"})]

    params = field.prepare_qs_params(None, "o", ["name__icontains", "slug__icontains"])
    assert params["and"] == {}
    assert len(params["or"]) == 1


def test_model_result_json_mixin_requires_queryset_and_search_fields():
    class NoQueryset(fields.ModelResultJsonMixin, forms.Field):
        queryset = None
        search_fields = ["name__icontains"]

    with pytest.raises(ValueError):
        NoQueryset().get_queryset()

    class NoSearch(fields.ModelResultJsonMixin, forms.Field):
        queryset = []

    with pytest.raises(ValueError):
        NoSearch().get_results(None, "x", 1, None)


def test_unhideable_queryset_metaclass_moves_class_queryset_to_constructor():
    class QuerysetHolder:
        pass

    holder = QuerysetHolder()

    class CustomAuto(fields.AutoModelSelect2Field):
        queryset = holder
        search_fields = ["name__icontains"]

    instance = CustomAuto()

    assert instance.queryset is holder
