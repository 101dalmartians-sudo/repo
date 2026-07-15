import csv
import datetime
from decimal import Decimal

from django.contrib import admin
from django.http import HttpResponse
from openpyxl import Workbook

from .models import (
    StudentProfile,
    FinancialRecord,
    Payment,
    AttendanceSession,
    AttendanceRecord,
    ExamSchedule,
    ExamResult,
    AuditLog,
)


def export_to_csv(modeladmin, request, queryset):
    model = queryset.model
    field_names = [field.name for field in model._meta.fields]
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={model._meta.model_name}_export_{datetime.date.today()}.csv'
    writer = csv.writer(response)
    writer.writerow(field_names)
    for obj in queryset:
        writer.writerow([getattr(obj, field) for field in field_names])
    return response
export_to_csv.short_description = 'Export selected items to CSV'


def export_to_xlsx(modeladmin, request, queryset):
    model = queryset.model
    field_names = [field.name for field in model._meta.fields]
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(field_names)
    for obj in queryset:
        sheet.append([str(getattr(obj, field)) for field in field_names])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename={model._meta.model_name}_export_{datetime.date.today()}.xlsx'
    workbook.save(response)
    return response
export_to_xlsx.short_description = 'Export selected items to XLSX'


def export_to_json(modeladmin, request, queryset):
    from django.core import serializers
    response = HttpResponse(content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename={queryset.model._meta.model_name}_backup_{datetime.date.today()}.json'
    serializers.serialize('json', queryset, stream=response)
    return response
export_to_json.short_description = 'Export selected items as JSON backup'


class FinancialRecordInline(admin.TabularInline):
    model = FinancialRecord
    fields = (
        'term', 'year', 'due_date', 'transport_fee', 'transport_paid', 'transport_balance',
        'school_tuition', 'tuition_paid', 'tuition_balance',
    )
    readonly_fields = ('transport_balance', 'tuition_balance')
    extra = 1


class PaymentInline(admin.TabularInline):
    model = Payment
    fields = ('receipt_number', 'amount', 'payment_method', 'payment_date', 'financial_record')
    readonly_fields = ('receipt_number',)
    extra = 0


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'current_class', 'email_verified', 'approved')
    search_fields = ('user__username', 'student_id', 'current_class')
    list_filter = ('email_verified', 'approved')
    inlines = [FinancialRecordInline, PaymentInline]
    actions = [export_to_csv, export_to_xlsx, export_to_json]


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
    readonly_fields = ('transport_balance', 'tuition_balance')
    actions = [export_to_csv, export_to_xlsx, export_to_json]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('student', 'receipt_number', 'amount', 'payment_method', 'payment_date', 'financial_record')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('student__student_id', 'student__user__username', 'receipt_number')
    readonly_fields = ('receipt_number',)
    actions = [export_to_csv, export_to_xlsx, export_to_json]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'date', 'term', 'year', 'status', 'recorded_by')
    list_filter = ('term', 'year', 'status')
    search_fields = ('student__student_id', 'student__user__username')
    actions = [export_to_csv, export_to_xlsx, export_to_json]


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'class_stream', 'subject', 'teacher', 'term', 'year')
    list_filter = ('term', 'year', 'date', 'class_stream')
    search_fields = ('title', 'class_stream', 'subject', 'teacher__username')
    actions = [export_to_csv, export_to_xlsx, export_to_json]


@admin.register(ExamSchedule)
class ExamScheduleAdmin(admin.ModelAdmin):
    list_display = ('exam_name', 'subject', 'target_class', 'term', 'year', 'exam_date', 'results_released', 'created_by')
    list_filter = ('term', 'year', 'results_released', 'target_class')
    search_fields = ('exam_name', 'subject', 'target_class')
    actions = [export_to_csv, export_to_xlsx, export_to_json]


class ExamResultInline(admin.TabularInline):
    model = ExamResult
    extra = 1


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ('exam', 'student', 'score', 'graded_by', 'recorded_at')
    search_fields = ('student__student_id', 'student__user__username', 'exam__subject')
    list_filter = ('exam__term', 'exam__year')
    actions = [export_to_csv, export_to_xlsx, export_to_json]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('actor', 'action', 'model_name', 'object_repr', 'created_at')
    readonly_fields = ('actor', 'action', 'model_name', 'object_repr', 'changes', 'created_at')
    search_fields = ('actor__username', 'model_name', 'object_repr', 'action')
    list_filter = ('model_name', 'action')
    actions = [export_to_csv, export_to_xlsx]
