import json

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils.datastructures import MultiValueDict

from django_select2 import fields
from django_select2.models import KeyMap
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


def test_select2_widget_without_id_and_without_media(monkeypatch):
    monkeypatch.setattr("django_select2.widgets.RENDER_SELECT2_STATICS", False)
    widget = Select2Widget(choices=[("1", "One")])
    widget.set_placeholder("Pick one")

    rendered = widget.render("choice", "1")

    assert widget.get_options()["placeholder"] == "Pick one"
    assert "<script" not in rendered
    assert widget.render_js_code(None) == ""


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
    assert widget._has_changed(None, None) is False
    assert widget.is_hidden is False

    assert "initMultipleHidden" not in widget.render("items", ["1"])


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


def test_heavy_widget_empty_value_and_media_branches(monkeypatch):
    monkeypatch.setattr("django_select2.widgets.RENDER_SELECT2_STATICS", False)
    widget = HeavySelect2Widget(data_url="/choices/")
    widget.field = forms.CharField(required=False)

    assert widget.render_texts_for_value("id_heavy", "", []) is None
    assert widget.media.render() == ""
    assert widget.render_inner_js_code("__prefix__", "name", "value") == ""

    monkeypatch.setattr("django_select2.widgets.RENDER_SELECT2_STATICS", True)
    assert "heavy_data.min.js" in widget.media.render()


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

    multiple.field = None
    tag.field = None
    assert 'django_select2.id_items("id_items", "id_items")' in multiple.render_inner_js_code(
        "id_items", "items", ["1"]
    )
    assert 'django_select2.id_tags("id_tags", "id_tags")' in tag.render_inner_js_code(
        "id_tags", "tags", ["1"]
    )


def test_heavy_multiple_render_texts_for_value():
    widget = HeavySelect2MultipleWidget(data_url="/choices/", choices=[("1", "One")])
    widget.field = None

    assert widget.render_texts_for_value("id_items", ["1"], []) == '$("#id_items").txt(["One"]);'
    assert widget.render_texts_for_value("id_items", [], []) is None


def test_auto_heavy_widgets_force_central_view_and_prefix_rendering():
    for cls in (AutoHeavySelect2Widget, AutoHeavySelect2MultipleWidget, AutoHeavySelect2TagWidget):
        widget = cls()
        widget.field_id = "field-id"
        assert widget.view == "django_select2_central_json"
        assert widget.render_inner_js_code("__prefix__") == ""
        assert '"field-id"' in widget.render_inner_js_code("id_auto", "name", "value")


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


def test_render_texts_returns_none_without_matches(caplog):
    widget = HeavySelect2Widget(data_url="/choices/", choices=[])
    widget.field = object()

    assert widget.render_texts(["missing"], []) is None
    assert "not a valid choice" in caplog.text


def test_choice_fields_use_select2_widgets_and_validate():
    assert fields.Select2ChoiceField.widget is Select2Widget
    assert fields.Select2MultipleChoiceField.widget is Select2MultipleWidget
    assert fields.ModelSelect2Field.widget is Select2Widget
    assert fields.ModelSelect2MultipleField.widget is Select2MultipleWidget

    field = fields.HeavyChoiceField(choices=[("1", "One")])
    assert field.clean("1") == "1"
    assert field.clean("missing") == "missing"

    class StrictField(fields.HeavyChoiceField):
        def validate_value(self, value):
            return False

    with pytest.raises(ValidationError):
        StrictField().clean("missing")

    class PermissiveField(fields.HeavyChoiceField):
        def validate_value(self, value):
            return value == "external"

        def get_val_txt(self, value):
            return "External"

    permissive = PermissiveField()
    assert permissive.clean("external") == "external"
    assert permissive._get_val_txt("external") == "External"
    assert fields.AutoViewFieldMixin().security_check(None) is True


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
    assert multiple.clean(["missing"]) == ["missing"]

    class StrictMultiple(fields.HeavyMultipleChoiceField):
        def validate_value(self, value):
            return False

    with pytest.raises(ValidationError):
        StrictMultiple().clean(["missing"])

    class TagField(fields.HeavySelect2TagField):
        def validate_value(self, value):
            return value == "1"

        def create_new_value(self, value):
            return "created-%s" % value

    tag = TagField(widget=HeavySelect2TagWidget(data_url="/choices/"), choices=[("1", "One")])
    cleaned = tag.clean(["1", "new"])
    assert cleaned == ["1", "created-new"]

    class RejectingTagField(fields.HeavySelect2TagField):
        def validate_value(self, value):
            return False

    with pytest.raises(NotImplementedError):
        RejectingTagField(
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

    class UnpagedSearchField(fields.ModelResultJsonMixin, forms.Field):
        queryset = QuerySetLike([Item(1, "One")])
        search_fields = ["name__icontains"]

    assert UnpagedSearchField().get_results(None, "o", 1, None) == (
        "nil",
        False,
        [(1, "One", {})],
    )


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
        def all(self):
            return self

    holder = QuerysetHolder()

    class CustomAuto(fields.AutoModelSelect2Field):
        queryset = holder
        search_fields = ["name__icontains"]

    instance = CustomAuto()

    assert instance.queryset is holder


@pytest.fixture
def keymap_rows():
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(KeyMap)
    try:
        KeyMap.objects.create(key="one", value="One")
        KeyMap.objects.create(key="two", value="Two")
        yield
    finally:
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(KeyMap)


def test_model_choice_fields_use_filterable_choices_and_placeholder(keymap_rows):
    field = fields.ModelSelect2Field(
        queryset=KeyMap.objects.all(),
        empty_label="Pick",
        required=False,
        to_field_name="key",
    )

    assert field.get_pk_field_name() == "key"
    assert field.widget.options["placeholder"] == "Pick"
    assert isinstance(field.choices, fields.FilterableModelChoiceIterator)

    choices = list(field.choices)
    assert choices[0] == ("", "Pick")
    assert any(choice[0].value == "one" and str(choice[1]) == "one => One" for choice in choices[1:])

    iterator = field.choices
    iterator.set_extra_filter(key="one")
    assert [choice[0] for choice in iterator] == ["", "one"]
    iterator.set_extra_filter()
    assert [choice[0] for choice in iterator] == ["", "one", "two"]

    field.choices = (("manual", "Manual"),)
    assert field.choices == [("manual", "Manual")]


def test_heavy_model_fields_wire_widgets_to_fields(keymap_rows):
    choice = fields.HeavyModelSelect2ChoiceField(
        data_url="/choices/",
        queryset=KeyMap.objects.all(),
        required=False,
        to_field_name="key",
    )
    multiple = fields.HeavyModelSelect2MultipleChoiceField(
        data_url="/choices/",
        queryset=KeyMap.objects.all(),
        required=False,
        to_field_name="key",
    )

    assert choice.widget.field is choice
    assert multiple.widget.field is multiple
    assert choice.get_pk_field_name() == "key"
    assert multiple.get_pk_field_name() == "key"


def test_heavy_model_tag_field_creates_and_cleans_values(keymap_rows):
    class TagField(fields.HeavyModelSelect2TagField):
        def get_model_field_values(self, value):
            return {"key": value, "value": value.title()}

    field = TagField(
        data_url="/choices/",
        queryset=KeyMap.objects.all(),
        required=False,
        to_field_name="key",
    )

    assert field.to_python(None) is None
    assert field.to_python("one").key == "one"
    assert field.to_python("three") == "three"
    assert KeyMap.objects.get(key="three").value == "Three"

    with pytest.raises(ValidationError):
        TagField(
            data_url="/choices/",
            queryset=KeyMap.objects.all(),
            required=True,
            to_field_name="key",
        ).clean([])

    assert field.clean([]) == []
    with pytest.raises(ValidationError):
        field.clean("one")

    result = field.clean(["one", "four"])
    assert set(result.values_list("key", flat=True)) == {"one", "four"}
    assert KeyMap.objects.get(key="four").value == "Four"


def test_heavy_model_tag_field_value_error_and_not_implemented(keymap_rows):
    class FakeQueryset:
        class Model:
            class DoesNotExist(Exception):
                pass

        model = Model

        def all(self):
            return self

        def filter(self, **kwargs):
            if "pk__in" in kwargs:
                return []
            raise ValueError("bad value")

        def create(self, **kwargs):
            obj = type("Obj", (), kwargs)()
            obj.pk = kwargs.get("pk", "created")
            return obj

    class TagField(fields.HeavyModelSelect2TagField):
        def get_model_field_values(self, value):
            return {"pk": "created-%s" % value}

    field = TagField(
        widget=HeavySelect2TagWidget(data_url="/choices/"),
        queryset=FakeQueryset(),
        required=False,
    )
    values = ["bad"]

    result = field.clean(values)

    assert result == []
    assert values == ["created-bad"]

    with pytest.raises(NotImplementedError):
        fields.HeavyModelSelect2TagField(
            widget=HeavySelect2TagWidget(data_url="/choices/"),
            queryset=FakeQueryset(),
            required=False,
        ).create_new_value("x")


def test_auto_field_sets_widget_field_id(keymap_rows):
    class AutoChoice(fields.AutoModelSelect2Field):
        search_fields = ["value__icontains"]

    field = AutoChoice(queryset=KeyMap.objects.all(), required=False, auto_id="auto-choice")

    assert field.widget.field_id == field.field_id
    assert field.widget.attrs["data-select2-id"] == field.field_id
    assert field.widget.field is field
