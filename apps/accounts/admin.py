from django.contrib import admin
from .models import AdminProfile


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_verified', 'approved')
    search_fields = ('user__username', 'user__email')
    list_filter = ('email_verified', 'approved')

