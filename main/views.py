from collections import defaultdict
import json
from itertools import combinations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .ahp import AHPNode
from .forms import CustomUserCreationForm
from .models import Answer, Draft, Questionnaire
from .services import (
    build_alternatives_groups,
    build_alternatives_groups2,
    build_comparison_groups,
    extract_ahpy_model,
    geometric_mean,
    parse_ahp_value,
)


def index(request: HttpRequest) -> HttpResponse:
    return render(request, "home.html")


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


def under_construction(request: HttpRequest):
    return render(request, "under_construction.html")


@login_required
def ahp_setup_view(request: HttpRequest):
    if request.method == "POST":
        action = request.POST.get("action")
        goal = request.POST.get("goal", "").strip()
        criteria_raw = request.POST.get("criteria_tree")
        alternatives_raw = request.POST.get("alternatives", "[]")
        answer_by = request.POST.get("answer_by", Questionnaire.AnswerBy.EVERYBODY)

        if not criteria_raw:
            messages.error(request, "Add at least one")
            return render(request, "ahp/create.html")

        try:
            criteria_tree = json.loads(criteria_raw)
        except (ValueError, TypeError):
            messages.error(request, "Add at least one")
            return render(request, "ahp/create.html")

        if not criteria_tree:
            messages.error(request, "Not empty")
            return render(request, "ahp/create.html")

        try:
            alternatives = json.loads(alternatives_raw)
        except (ValueError, TypeError):
            messages.error(request, "Invalid alternatives payload")
            return render(request, "ahp/create.html")

        if not isinstance(alternatives, list):
            messages.error(request, "Invalid alternatives payload")
            return render(request, "ahp/create.html")

        cleaned: list[str] = []
        seen: set[str] = set()
        for item in alternatives:
            if not isinstance(item, str):
                continue
            value = item.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            cleaned.append(value)

        status = (
            Questionnaire.QuestionStatus.IN_PROGRESS
            if action == "publish"
            else Questionnaire.QuestionStatus.DRAFT
        )

        questionJson = {
            "questions": criteria_tree,
            "alternatives": cleaned,
        }

        Questionnaire.objects.create(
            user=request.user,
            goal=goal or "No goal",
            questions=questionJson,
            has_alternatives=bool(cleaned),
            status=status,
            answer_by=answer_by,
        )

        return redirect("/")

    return render(request, "ahp/create.html")


def questionnaire_detail(request: HttpRequest, pk):
    questionnaire = get_object_or_404(Questionnaire, pk=pk)

    groups = build_comparison_groups(questionnaire.questions.get("questions", []))
    alternatives = build_alternatives_groups(
        groups, questionnaire.questions.get("alternatives", [])
    )
    draft = None
    if request.user.is_authenticated:
        draft = Draft.objects.filter(
            user=request.user, questionnaire=questionnaire
        ).first()

    alternatives_show = build_alternatives_groups2(
        questionnaire.questions.get("questions", []), alternatives
    )

    context = {
        "questionnaire": questionnaire,
        "groups": groups,
        "has_alternatives": questionnaire.has_alternatives,
        "alt_comparisons": alternatives,
        "draft": draft,
        "answers": draft.answers if draft else None,
        "alternatives_show": alternatives_show,
    }

    if request.user.is_anonymous and questionnaire.AnswerBy.LOGIN:
        messages.error(request, "Can't access it")
        return redirect("/")

    if (
        questionnaire.AnswerBy.LOGIN
        and request.user.is_authenticated
        and Answer.objects.filter(
            user=request.user, questionnaire=questionnaire
        ).exists()
    ):
        messages.error(request, "Already answered")
        return render(request, "under_construction.html")

    return render(request, "questionnaire_form.html", context)


def questionnaire_list(request: HttpRequest):
    questionnaires = Questionnaire.objects.filter(
        status=Questionnaire.QuestionStatus.IN_PROGRESS
    ).order_by("-created_at")
    if request.user.is_anonymous:
        questionnaires = questionnaires.filter(
            answer_by=Questionnaire.AnswerBy.EVERYBODY
        )
    return render(
        request, "questionnaire_list.html", {"questionnaires": questionnaires}
    )


@login_required
def my_questionnaire_list(request: HttpRequest) -> HttpResponse:
    user = request.user
    questionnaires = Questionnaire.objects.filter(user=user).order_by("-created_at")
    return render(
        request,
        "my_questionnaire_list.html",
        {"questionnaires": questionnaires},
    )


@login_required
def edit_questionnaire(request: HttpRequest, pk: int) -> HttpResponse:
    questionnaire = get_object_or_404(Questionnaire, pk=pk, user=request.user)

    # Prevent editing published or finalized questionnaires
    if questionnaire.status != Questionnaire.QuestionStatus.DRAFT:
        return HttpResponseForbidden("Cannot edit questionnaire in its current state.")

    if request.method == "POST":
        action = request.POST.get("action")
        goal = request.POST.get("goal", "").strip()
        criteria_raw = request.POST.get("criteria_tree")
        alternatives_raw = request.POST.get("alternatives", "[]")
        answer_by = request.POST.get("answer_by", Questionnaire.AnswerBy.EVERYBODY)

        if not criteria_raw:
            messages.error(request, "Add at least one criterion.")
            return render(request, "ahp/edit.html", {"questionnaire": questionnaire})

        try:
            criteria_tree = json.loads(criteria_raw)
        except (ValueError, TypeError):
            messages.error(request, "Invalid criteria payload.")
            return render(request, "ahp/edit.html", {"questionnaire": questionnaire})

        if not criteria_tree:
            messages.error(request, "Criteria cannot be empty.")
            return render(request, "ahp/edit.html", {"questionnaire": questionnaire})

        try:
            alternatives = json.loads(alternatives_raw)
        except (ValueError, TypeError):
            messages.error(request, "Invalid alternatives payload.")
            return render(request, "ahp/edit.html", {"questionnaire": questionnaire})

        if not isinstance(alternatives, list):
            messages.error(request, "Invalid alternatives payload.")
            return render(request, "ahp/edit.html", {"questionnaire": questionnaire})

        cleaned: list[str] = []
        seen: set[str] = set()
        for item in alternatives:
            if not isinstance(item, str):
                continue
            value = item.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            cleaned.append(value)

        status = (
            Questionnaire.QuestionStatus.IN_PROGRESS
            if action == "publish"
            else Questionnaire.QuestionStatus.DRAFT
        )

        # Update existing record
        questionnaire.goal = goal or "No goal"
        questionnaire.questions = {
            "questions": criteria_tree,
            "alternatives": cleaned,
        }
        questionnaire.has_alternatives = bool(cleaned)
        questionnaire.status = status
        questionnaire.answer_by = answer_by
        questionnaire.save()

        messages.success(request, "Questionnaire updated successfully.")
        return redirect("/")

    return render(request, "ahp/edit.html", {"questionnaire": questionnaire})


@login_required
@require_POST
def questionnaire_publish(request: HttpRequest, pk: int) -> HttpResponse:
    """DRAFT or STOPPED -> IN_PROGRESS"""
    q = get_object_or_404(Questionnaire, pk=pk, user=request.user)
    if q.status not in (
        Questionnaire.QuestionStatus.DRAFT,
        Questionnaire.QuestionStatus.STOPPED,
    ):
        return HttpResponseForbidden("Cannot publish in current state.")
    q.status = Questionnaire.QuestionStatus.IN_PROGRESS
    q.save(update_fields=["status"])
    return redirect("my_questionnaire_list")


@login_required
@require_POST
def questionnaire_stop(request: HttpRequest, pk: int) -> HttpResponse:
    """IN_PROGRESS -> STOPPED"""
    q = get_object_or_404(Questionnaire, pk=pk, user=request.user)
    if q.status != Questionnaire.QuestionStatus.IN_PROGRESS:
        return HttpResponseForbidden("Cannot stop in current state.")
    q.status = Questionnaire.QuestionStatus.STOPPED
    q.save(update_fields=["status"])
    return redirect("my_questionnaire_list")


@login_required
@require_POST
def questionnaire_finish(request: HttpRequest, pk: int) -> HttpResponse:
    """IN_PROGRESS -> FINISHED"""
    q = get_object_or_404(Questionnaire, pk=pk, user=request.user)
    if q.status != Questionnaire.QuestionStatus.IN_PROGRESS:
        return HttpResponseForbidden("Cannot finish in current state.")
    q.status = Questionnaire.QuestionStatus.FINISHED
    q.save(update_fields=["status"])
    return redirect("my_questionnaire_list")



@login_required
@require_GET
def get_result(request: HttpRequest, pk: int) -> HttpResponse:
    """Aggregate all answers into a single AHP model and show the result."""
    q = get_object_or_404(Questionnaire, pk=pk, user=request.user)

    if q.status != Questionnaire.QuestionStatus.FINISHED:
        messages.error(request, "First you should finish the questionnaire.")
        return redirect("my_questionnaire_list")

    answers = Answer.objects.filter(questionnaire=q)
    if not answers.exists():
        messages.error(request, "No answers to compute a result from.")
        return redirect("my_questionnaire_list")

    # 1. Aggregate every pairwise field across all respondents using
    #    the geometric mean (standard AHP aggregation for group decisions).
    grouped: dict[str, list[float]] = defaultdict(list)
    for ans in answers:
        if not ans.answers:
            continue
        for key, raw_val in ans.answers.items():
            parsed = parse_ahp_value(raw_val)
            if parsed is not None:
                grouped[key].append(parsed)

    aggregated: dict[str, float] = {
        key: geometric_mean(vals) for key, vals in grouped.items()
    }

    # 2. Build the model from the aggregated values (NOT request.POST —
    #    this is a GET view and we want the *combined* judgement).
    model = extract_ahpy_model(
        post_data=aggregated,
        questionnaire=q,
    )

    root: AHPNode = model["root"]
    inconsistent_nodes: list[AHPNode] = model["inconsistent_nodes"]

    # 3. Extract everything the template needs.
    ranked = root.rank_alternatives()
    criteria_weights = root.target_weights

    context = {
        "questionnaire": q,
        "root": root,
        "ranked_alternatives": ranked,
        "criteria_weights": criteria_weights,
        "inconsistent_nodes": inconsistent_nodes,
        "num_answers": answers.count(),
        "max_score": max(ranked.values()) if ranked else 0,
    }
    return render(request, "questionnaire_result.html", context)

@require_POST
def handle_questions(request: HttpRequest, pk: int):
    questionnaire = get_object_or_404(Questionnaire, pk=pk)
    if Answer.objects.filter(user=request.user, questionnaire=questionnaire).exists():
        messages.error(request, "Already answered this!")
        return render(request, "home.html")
    action = request.POST.get("action", "unknown")
    data = {
        k: v
        for k, v in request.POST.items()
        if k not in ("csrfmiddlewaretoken", "action")
    }
    if action == "save_draft":
        if not request.user.is_authenticated:
            return HttpResponse("login required", status=403)

        Draft.objects.update_or_create(
            questionnaire=questionnaire,
            user=request.user,
            defaults={"answers": data},
        )
        return HttpResponse("draft saved")

    if action == "submit":
        if request.user.is_authenticated:
            Draft.objects.update_or_create(
                questionnaire=questionnaire,
                user=request.user,
                defaults={"answers": data},
            )
        root_node = extract_ahpy_model(
            post_data=request.POST,
            questionnaire=questionnaire,
        )

        inconsistent_nodes: list[AHPNode] = root_node["inconsistent_nodes"]

        if len(inconsistent_nodes) != 0:
            to_show = ""
            for bad_node in inconsistent_nodes:
                to_show += f"{bad_node.name} is bad with {bad_node.consistency_ratio}\n"
            messages.error(request, "Some root are inconsistent" + to_show)
            return redirect("questionnaire_detail", pk=questionnaire.pk)
        try:
            Answer.objects.create(
                questionnaire=questionnaire,
                user=request.user if request.user.is_authenticated else None,
                answers=data,
            )

            messages.success(request, "پاسخ‌ها با موفقیت ثبت و محاسبه شدند.")
            return reverse("index")

        except Exception as e:
            messages.error(request, f"خطا در پردازش AHP: {e!s}")
            return redirect("questionnaire_detail", pk=questionnaire.pk)

    messages.error(request, "Bad action")
    return reverse("index")


@require_GET
def print_questionnaire(request: HttpRequest, pk):
    questionnaire = get_object_or_404(Questionnaire, pk=pk)

    groups = build_comparison_groups(questionnaire.questions.get("questions", []))

    alternatives = build_alternatives_groups(
        groups, questionnaire.questions.get("alternatives", [])
    )

    context = {
        "questionnaire": questionnaire,
        "groups": groups,
        "has_alternatives": questionnaire.has_alternatives,
        "alt_comparisons": alternatives,
    }
    return render(request, "questionnaire_print.html", context)
