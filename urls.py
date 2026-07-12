# -*- coding:utf-8 -*-


from django.urls import path

from .views import AutoResponseView

urlpatterns = [
    path("fields/auto.json", AutoResponseView.as_view(), name="django_select2_central_json"),
]
