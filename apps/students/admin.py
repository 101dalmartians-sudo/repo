from django.contrib import admin
from .models import StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'current_class', 'email_verified', 'approved')
    search_fields = ('user__username', 'student_id', 'current_class')
    list_filter = ('email_verified', 'approved')
