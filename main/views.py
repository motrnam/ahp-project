from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .ahp import AHPNode
from .models import Answer, Draft, Questionnaire
from .services import (
    build_alternatives_groups2,
    build_comparison_groups,
    extract_ahpy_model,
)


def index(request: HttpRequest) -> HttpResponse:
    return render(request, "home.html")


def under_construction(request: HttpRequest):
    return render(request, "under_construction.html")


def questionnaire_detail(request: HttpRequest, pk):
    questionnaire = get_object_or_404(Questionnaire, pk=pk)

    groups = build_comparison_groups(questionnaire.questions.get("questions", []))
    draft = None
    if request.user.is_authenticated:
        draft = Draft.objects.filter(
            user=request.user, questionnaire=questionnaire
        ).first()

    alternatives_show = build_alternatives_groups2(
        questionnaire.questions.get("questions", []),
        questionnaire.questions.get("alternatives", []),
    )

    context = {
        "questionnaire": questionnaire,
        "groups": groups,
        "has_alternatives": questionnaire.has_alternatives,
        "draft": draft,
        "answers": draft.answers if draft else None,
        "alternatives_show": alternatives_show,
    }

    if request.user.is_anonymous and questionnaire.AnswerBy.LOGIN:
        messages.error(request, "Can't access it")
        return redirect("/")

    if (
        request.user.is_authenticated
        and Answer.objects.filter(
            user=request.user, questionnaire=questionnaire
        ).exists()
    ):
        messages.error(request, "Already answered")
        return render(
            request,
            "already_answered.html",
            {"questionnaire": questionnaire},
        )

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


@require_POST
def handle_questions(request: HttpRequest, pk: int):
    questionnaire = get_object_or_404(Questionnaire, pk=pk)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if Answer.objects.filter(user=request.user, questionnaire=questionnaire).exists():
        if is_ajax:
            return JsonResponse(
                {"status": "error", "message": "login required"}, status=403
            )
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
            if is_ajax:
                return JsonResponse(
                    {"status": "error", "message": "login required"}, status=403
                )
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
                if is_ajax:
                    return JsonResponse(
                        {
                            "status": "error",
                            "message": "Some nodes are inconsistent:\n" + to_show,
                        }
                    )
            messages.error(request, "Some root are inconsistent" + to_show)
            return redirect("questionnaire_detail", pk=questionnaire.pk)
        try:
            Answer.objects.create(
                questionnaire=questionnaire,
                user=request.user if request.user.is_authenticated else None,
                answers=data,
            )

            if is_ajax:
                return JsonResponse({"status": "ok", "redirect": reverse("index")})

            messages.success(request, "پاسخ‌ها با موفقیت ثبت و محاسبه شدند.")
            return reverse("index")

        except Exception as e:
            if is_ajax:
                return JsonResponse(
                    {"status": "error", "message": f"خطا در پردازش AHP: {e!s}"}
                )
            messages.error(request, f"خطا در پردازش AHP: {e!s}")
            return redirect("questionnaire_detail", pk=questionnaire.pk)

    if is_ajax:
        return JsonResponse({"status": "error", "message": "Bad action"}, status=400)

    messages.error(request, "Bad action")
    return reverse("index")


@require_GET
def print_questionnaire(request: HttpRequest, pk):
    questionnaire = get_object_or_404(Questionnaire, pk=pk)

    groups = build_comparison_groups(questionnaire.questions.get("questions", []))

    alternatives = build_alternatives_groups2(
        groups, questionnaire.questions.get("alternatives", [])
    )

    context = {
        "questionnaire": questionnaire,
        "groups": groups,
        "has_alternatives": questionnaire.has_alternatives,
        "alt_comparisons": alternatives,
    }
    return render(request, "questionnaire_print.html", context)
