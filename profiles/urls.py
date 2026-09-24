from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="index"), name="account_logout"),
    path("signup/", views.signup_view, name="signup"),
    path("ch1/", views.under_construction, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("draft/", views.under_construction, name="draft"),
]
