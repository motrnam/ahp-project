from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="index"), name="account_logout"),
    path("signup/", views.signup_view, name="signup"),
    path("ch1/", views.under_construction, name="dashboard"),
    path("ch3/", views.under_construction, name="profile"),
    path("create-poll/", views.ahp_setup_view, name="create-ahp"),
    path("draft/", views.under_construction, name="draft"),
    path("questionnaires/", views.questionnaire_list, name="questionnaire_list"),
    path(
        "questionnaires/<int:pk>/",
        views.questionnaire_detail,
        name="questionnaire_detail",
    ),
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
    path("form/questionnaire/<int:pk>/handle", views.handle_questions, name="handle"),
    path(
        "form/questionnaire/<int:pk>/print",
        views.print_questionnaire,
        name="print_questionnaire",
    ),
]
