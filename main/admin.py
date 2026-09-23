from django.contrib import admin

from .models import Answer, Draft, Questionnaire

# Register your models here.

admin.site.register(Questionnaire)
admin.site.register(Draft)
admin.site.register(Answer)
