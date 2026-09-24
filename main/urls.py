from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("questionnaires/", views.questionnaire_list, name="questionnaire_list"),
    path("form/questionnaire/<int:pk>/handle", views.handle_questions, name="handle"),
    path(
        "form/questionnaire/<int:pk>/print",
        views.print_questionnaire,
        name="print_questionnaire",
    ),
    path(
        "questionnaires/<int:pk>/",
        views.questionnaire_detail,
        name="questionnaire_detail",
    ),
]
