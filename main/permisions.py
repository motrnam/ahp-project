from .models import Answer, Questionnaire


def _can_user_answer(questionnaire, user):
    """Return (allowed, reason)."""
    if questionnaire.AnswerBy(questionnaire.answer_by) == Questionnaire.AnswerBy.LOGIN:
        if not user.is_authenticated:
            return False, "برای پاسخ به این پرسشنامه باید وارد شوید."
        if Answer.objects.filter(questionnaire=questionnaire, user=user).exists():
            return False, "شما قبلاً به این پرسشنامه پاسخ داده‌اید."
    return True, None
