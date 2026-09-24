from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from main.models import Answer, Questionnaire

from .forms import CustomUserCreationForm


# Create your views here.
def index(request: HttpRequest) -> HttpResponse:
    return render(request, "home.html")


def under_construction(request: HttpRequest):
    return render(request, "under_construction.html")


def signup_view(request: HttpRequest):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Log the user in after signup
            login(request, user)
            messages.success(
                request, f"Account created successfully! Welcome {user.username}!"
            )
            return redirect("/")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CustomUserCreationForm()

    return render(request, "signup.html", {"form": form})


class CustomLoginView(LoginView):
    template_name = "login.html"

    def get_success_url(self):
        if self.request.user and self.request.user.is_staff:
            return reverse("admin:index")
        return reverse("index")


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    user = request.user

    # Questionnaires created by this user
    my_questionnaires = Questionnaire.objects.filter(user=user).order_by("-created_at")

    # Answers submitted by this user (joined with their questionnaire)
    my_answers = (
        Answer.objects.filter(user=user).select_related("questionnaire").order_by("-id")
    )

    # Drafts belonging to this user
    my_drafts = user.drafts.select_related("questionnaire").order_by("-updated_at")

    context = {
        "profile_user": user,
        "my_questionnaires": my_questionnaires,
        "my_answers": my_answers,
        "my_drafts": my_drafts,
        "counts": {
            "questionnaires": my_questionnaires.count(),
            "answers": my_answers.count(),
            "drafts": my_drafts.count(),
        },
    }
    return render(request, "profile.html", context)
