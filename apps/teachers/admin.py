from django.contrib import admin
from .models import TeacherProfile


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'email_verified', 'approved')
    search_fields = ('user__username', 'department')
    list_filter = ('email_verified', 'approved')
