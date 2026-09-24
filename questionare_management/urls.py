from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("create-poll/", views.ahp_setup_view, name="create-ahp"),
    path(
        "my-questionnaires/", views.my_questionnaire_list, name="my_questionnaire_list"
    ),
    path(
        "my/<int:pk>/publish/",
        views.questionnaire_publish,
        name="questionnaire_publish",
    ),
    path(
        "my/<int:pk>/result/",
        views.get_result,
        name="questionnaire_result",
    ),
    path("my/<int:pk>/stop/", views.questionnaire_stop, name="questionnaire_stop"),
    path(
        "my/<int:pk>/finish/", views.questionnaire_finish, name="questionnaire_finish"
    ),
    path("my/<int:pk>/edit/", views.edit_questionnaire, name="questionnaire_edit"),
]
