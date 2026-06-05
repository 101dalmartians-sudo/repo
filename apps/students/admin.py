from django.contrib import admin
from .models import StudentProfile, FinancialRecord


class FinancialRecordInline(admin.TabularInline):
    model = FinancialRecord
    fields = ('term', 'year', 'due_date', 'transport_fee', 'transport_paid', 'transport_balance', 
              'school_tuition', 'tuition_paid', 'tuition_balance')
    extra = 1


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'current_class', 'email_verified', 'approved')
    search_fields = ('user__username', 'student_id', 'current_class')
    list_filter = ('email_verified', 'approved')
    inlines = [FinancialRecordInline]


@admin.register(FinancialRecord)
class FinancialRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'year', 'due_date', 'total_fee', 'total_paid', 'total_balance')
    list_filter = ('term', 'year')
    search_fields = ('student__student_id', 'student__user__username')
    fieldsets = (
        ('Student Information', {'fields': ('student',)}),
        ('Term & Due Date', {'fields': ('term', 'year', 'due_date')}),
        ('Transport Fee', {'fields': ('transport_fee', 'transport_paid', 'transport_balance')}),
        ('School Tuition', {'fields': ('school_tuition', 'tuition_paid', 'tuition_balance')}),
    )
