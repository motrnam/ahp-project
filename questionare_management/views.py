import json
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from main.ahp import AHPNode
from main.models import Answer, Questionnaire
from main.services import (
    extract_ahpy_model,
    geometric_mean,
    parse_ahp_value,
)


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
