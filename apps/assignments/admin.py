from django.contrib import admin
from .models import Assignment


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'target_class', 'due_date', 'uploaded_by')
    search_fields = ('title', 'subject', 'target_class')
