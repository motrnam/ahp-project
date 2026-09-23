from typing import ClassVar

from django.conf import settings
from django.db import models


class Questionnaire(models.Model):
    class QuestionStatus(models.TextChoices):
        DRAFT = "DRAFT", "draft"
        FINISHED = "FINISHED", "finished"
        IN_PROGRESS = "IN_PROGRESS", "in progress"
        STOPPED = "STOPPED", "stopped"

    class AnswerBy(models.TextChoices):
        EVERYBODY = "EVERYBODY", "everybody"
        LOGIN = "LOGIN", "login"

    status = models.CharField(
        max_length=15, choices=QuestionStatus.choices, default=QuestionStatus.DRAFT
    )
    answer_by = models.CharField(
        max_length=15, choices=AnswerBy.choices, default=AnswerBy.EVERYBODY
    )
    questions = models.JSONField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="question"
    )
    goal = models.CharField(max_length=100, default="HaHa")
    created_at = models.DateTimeField(auto_now_add=True)
    has_alternatives = models.BooleanField(default=False)


class Answer(models.Model):
    questionnaire = models.ForeignKey(
        Questionnaire,
        verbose_name="questionnaire",
        on_delete=models.CASCADE,
        related_name="answer",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="answer",
        null=True,
    )
    answers = models.JSONField(null=True)


class Draft(models.Model):
    questionnaire = models.ForeignKey(
        Questionnaire,
        verbose_name="questionnaire",
        on_delete=models.CASCADE,
        related_name="drafts",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="drafts",
    )
    answers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Partial answers keyed by input name (criteria_gX_rY_cZ / alt_X_...).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("questionnaire", "user")
        ordering: ClassVar = ["-updated_at"]

    def __str__(self):
        return f"Draft #{self.pk} — {self.user} / {self.questionnaire}"
