from django.contrib import admin
from django.db.models import Sum
from django.utils import timezone

from .exports import (
    export_annual_summary_workbook,
    export_budgets_workbook,
    export_expenses_workbook,
    export_monthly_reports_workbook,
    export_profit_and_loss_workbook,
)
from .models import Budget, Expense, ExpenseCategory, Income, MonthlyFinancialReport


@admin.action(description='Export selected expenses to Excel')
def export_expenses_action(modeladmin, request, queryset):
    return export_expenses_workbook(queryset, filename='admin-expenses.xlsx')


@admin.action(description='Export selected budgets to Excel')
def export_budgets_action(modeladmin, request, queryset):
    return export_budgets_workbook(queryset, filename='admin-budgets.xlsx')


@admin.action(description='Export selected monthly reports to Excel')
def export_reports_action(modeladmin, request, queryset):
    return export_monthly_reports_workbook(queryset, filename='admin-monthly-reports.xlsx')


@admin.action(description='Export profit/loss report (selected years)')
def export_profit_loss_action(modeladmin, request, queryset):
    years = sorted(set(queryset.values_list('date__year', flat=True)))
    target_year = years[-1] if years else timezone.now().year
    return export_profit_and_loss_workbook(target_year, filename=f'admin-profit-loss-{target_year}.xlsx')


@admin.action(description='Export annual summary (selected years)')
def export_annual_summary_action(modeladmin, request, queryset):
    years = sorted(set(queryset.values_list('year', flat=True)))
    target_year = years[-1] if years else timezone.now().year
    return export_annual_summary_workbook(target_year, filename=f'admin-annual-summary-{target_year}.xlsx')


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'allocated_budget', 'spent_amount', 'remaining_amount', 'utilization_percent')
    search_fields = ('name', 'description')
    list_filter = ('is_active',)

    def allocated_budget(self, obj):
        return obj.budgets.aggregate(total=Sum('amount'))['total'] or 0

    def spent_amount(self, obj):
        return obj.expenses.aggregate(total=Sum('amount'))['total'] or 0

    def remaining_amount(self, obj):
        return self.allocated_budget(obj) - self.spent_amount(obj)

    def utilization_percent(self, obj):
        budget = self.allocated_budget(obj)
        if not budget:
            return 0
        return round((self.spent_amount(obj) / budget) * 100, 2)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('date', 'category', 'description', 'amount', 'created_by')
    search_fields = ('description', 'category__name', 'created_by__username')
    list_filter = ('date', 'category', 'created_by')
    autocomplete_fields = ('category', 'created_by')
    actions = [export_expenses_action]


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('category', 'period_type', 'year', 'month', 'amount', 'expenses_total', 'remaining_budget', 'utilization_percentage', 'status')
    search_fields = ('category__name', 'notes')
    list_filter = ('period_type', 'year', 'month', 'category')
    autocomplete_fields = ('category', 'created_by')
    actions = [export_budgets_action]


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('date', 'source', 'amount', 'description', 'recorded_by')
    search_fields = ('description', 'recorded_by__username')
    list_filter = ('source', 'date', 'recorded_by')
    autocomplete_fields = ('recorded_by',)
    actions = [export_profit_loss_action]


@admin.register(MonthlyFinancialReport)
class MonthlyFinancialReportAdmin(admin.ModelAdmin):
    list_display = ('year', 'month', 'total_income', 'total_expenses', 'net_profit_loss', 'budget_utilization_percentage')
    list_filter = ('year', 'month')
    search_fields = ('year', 'month')
    autocomplete_fields = ('generated_by',)
    actions = [export_reports_action, export_annual_summary_action]
