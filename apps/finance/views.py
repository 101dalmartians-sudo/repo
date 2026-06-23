from calendar import month_name
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q, Sum
from django.db.utils import OperationalError, ProgrammingError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.students.models import Payment

from .exports import (
    export_annual_summary_workbook,
    export_budgets_workbook,
    export_expenses_workbook,
    export_monthly_reports_workbook,
    export_profit_and_loss_workbook,
)
from .forms import BudgetForm, ExpenseCategoryForm, ExpenseForm, IncomeForm
from .models import Budget, Expense, ExpenseCategory, Income, MonthlyFinancialReport


def _admin_guard(request):
    return hasattr(request.user, 'admin_profile') and request.user.admin_profile.approved and request.user.is_staff


def _status_meta(utilization):
    value = float(utilization or 0)
    if value > 100:
        return {'label': 'Over Budget', 'badge': 'bg-rose-900 text-white', 'accent': 'bg-rose-900', 'text': 'text-rose-900'}
    if value >= 96:
        return {'label': 'Critical', 'badge': 'bg-rose-100 text-rose-700', 'accent': 'bg-rose-600', 'text': 'text-rose-600'}
    if value >= 81:
        return {'label': 'Warning', 'badge': 'bg-amber-100 text-amber-700', 'accent': 'bg-amber-500', 'text': 'text-amber-600'}
    return {'label': 'On Track', 'badge': 'bg-emerald-100 text-emerald-700', 'accent': 'bg-emerald-500', 'text': 'text-emerald-600'}


def _safe_payment_total(year, month=None):
    queryset = Payment.objects.filter(
        payment_date__year=year,
        is_approved=True,
        status='approved',
        is_reversed=False,
    )
    if month is not None:
        queryset = queryset.filter(payment_date__month=month)
    try:
        return queryset.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    except (OperationalError, ProgrammingError):
        return Decimal('0.00')


def _safe_payment_feed(limit=25):
    try:
        return Payment.objects.select_related('student', 'student__user').filter(
            is_approved=True,
            status='approved',
            is_reversed=False,
        )[:limit]
    except (OperationalError, ProgrammingError):
        return []


def _base_finance_context():
    today = timezone.now().date()
    year = today.year
    current_month = today.month
    categories = list(
        ExpenseCategory.objects.filter(is_active=True)
        .prefetch_related(
            Prefetch('budgets', queryset=Budget.objects.order_by('-year', '-month')),
            Prefetch('expenses', queryset=Expense.objects.order_by('-date')),
        )
    )
    total_annual_budget = Budget.objects.filter(period_type=Budget.PERIOD_ANNUAL, year=year).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_monthly_budget = Budget.objects.filter(period_type=Budget.PERIOD_MONTHLY, year=year, month=current_month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_budget = total_monthly_budget or total_annual_budget
    total_expenses = Expense.objects.filter(date__year=year).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    manual_income = Income.objects.filter(date__year=year).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    fee_income = _safe_payment_total(year)
    total_income = manual_income + fee_income
    remaining_budget = total_budget - total_expenses
    budget_utilization = Decimal('0.00') if total_budget == 0 else (total_expenses / total_budget) * Decimal('100')
    net_profit_loss = total_income - total_expenses

    category_cards = []
    alerts = []
    expense_breakdown = []
    budget_vs_actual = []
    for category in categories:
        annual_budget = category.budgets.filter(period_type=Budget.PERIOD_ANNUAL, year=year).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        monthly_budget = category.budgets.filter(period_type=Budget.PERIOD_MONTHLY, year=year, month=current_month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        category_budget = monthly_budget or annual_budget
        spent = category.expenses.filter(date__year=year).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        remaining = category_budget - spent
        utilization = Decimal('0.00') if category_budget == 0 else (spent / category_budget) * Decimal('100')
        status = _status_meta(utilization)
        if utilization >= 80:
            alerts.append({
                'category': category.name,
                'message': f'{category.name} is at {utilization:.0f}% utilization.',
                'status': status,
            })
        category_cards.append({
            'category': category,
            'budget': category_budget,
            'spent': spent,
            'remaining': remaining,
            'utilization': utilization,
            'status': status,
        })
        expense_breakdown.append({'label': category.name, 'value': float(spent)})
        budget_vs_actual.append({'label': category.name, 'budget': float(category_budget), 'spent': float(spent)})

    monthly_trend = []
    for month in range(1, 13):
        income_total = (
            (Income.objects.filter(date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
            +
            _safe_payment_total(year, month)
        )
        expense_total = Expense.objects.filter(date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        monthly_trend.append({
            'label': month_name[month],
            'income': float(income_total),
            'expenses': float(expense_total),
            'profit': float(income_total - expense_total),
        })

    return {
        'finance_summary': {
            'total_budget': total_budget,
            'total_expenses': total_expenses,
            'remaining_budget': remaining_budget,
            'total_income': total_income,
            'net_profit_loss': net_profit_loss,
            'budget_utilization': budget_utilization,
            'profit_status_class': 'text-emerald-600' if net_profit_loss >= 0 else 'text-rose-600',
            'budget_status': _status_meta(budget_utilization),
        },
        'category_cards': category_cards,
        'alerts': alerts,
        'expense_breakdown': expense_breakdown,
        'budget_vs_actual': budget_vs_actual,
        'monthly_trend': monthly_trend,
        'finance_year': year,
        'finance_month': current_month,
    }


@login_required
@permission_required('finance.view_expense', raise_exception=True)
def finance_dashboard(request):
    if not _admin_guard(request):
        raise Http404
    context = _base_finance_context()
    context['active_finance_tab'] = 'dashboard'
    return render(request, 'finance/dashboard.html', context)


@login_required
@permission_required('finance.view_expense', raise_exception=True)
def expense_list(request):
    if not _admin_guard(request):
        raise Http404

    expenses = Expense.objects.select_related('category', 'created_by').all()
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    user = request.GET.get('user', '').strip()
    month = request.GET.get('month', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    min_amount = request.GET.get('min_amount', '').strip()
    max_amount = request.GET.get('max_amount', '').strip()

    if query:
        expenses = expenses.filter(Q(description__icontains=query) | Q(category__name__icontains=query))
    if category:
        expenses = expenses.filter(category_id=category)
    if user:
        expenses = expenses.filter(created_by_id=user)
    if month:
        try:
            month_value = int(month)
            expenses = expenses.filter(date__month=month_value)
        except ValueError:
            pass
    if start_date:
        expenses = expenses.filter(date__gte=start_date)
    if end_date:
        expenses = expenses.filter(date__lte=end_date)
    if min_amount:
        expenses = expenses.filter(amount__gte=min_amount)
    if max_amount:
        expenses = expenses.filter(amount__lte=max_amount)

    paginator = Paginator(expenses, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    edit_expense = None
    edit_form = None
    edit_id = request.GET.get('edit')
    if edit_id:
        edit_expense = get_object_or_404(Expense.objects.select_related('category', 'created_by'), pk=edit_id)
        edit_form = ExpenseForm(instance=edit_expense)

    context = _base_finance_context()
    context.update({
        'active_finance_tab': 'expenses',
        'page_obj': page_obj,
        'expense_form': ExpenseForm(),
        'edit_expense': edit_expense,
        'edit_form': edit_form,
        'categories': ExpenseCategory.objects.filter(is_active=True),
        'expense_users': Expense.objects.exclude(created_by__isnull=True).select_related('created_by').values('created_by_id', 'created_by__username').distinct(),
        'filters': {
            'q': query,
            'category': category,
            'user': user,
            'month': month,
            'start_date': start_date,
            'end_date': end_date,
            'min_amount': min_amount,
            'max_amount': max_amount,
        },
    })
    return render(request, 'finance/expenses.html', context)


@login_required
@permission_required('finance.add_expense', raise_exception=True)
def expense_create(request):
    if not _admin_guard(request):
        raise Http404

    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            expense.save()
            messages.success(request, 'Expense recorded successfully.')
        else:
            messages.error(request, 'Please correct the expense form errors.')
    return redirect('finance:finance_expenses')


@login_required
@permission_required('finance.change_expense', raise_exception=True)
def expense_update(request, pk):
    if not _admin_guard(request):
        raise Http404
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully.')
        else:
            messages.error(request, 'Unable to update expense.')
    return redirect('finance:finance_expenses')


@login_required
@permission_required('finance.delete_expense', raise_exception=True)
def expense_delete(request, pk):
    if not _admin_guard(request):
        raise Http404
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully.')
    return redirect('finance:finance_expenses')


@login_required
@permission_required('finance.view_budget', raise_exception=True)
def budget_management(request):
    if not _admin_guard(request):
        raise Http404

    budget_form = BudgetForm(prefix='budget')
    category_form = ExpenseCategoryForm(prefix='category')
    edit_budget = None
    edit_budget_form = None
    if request.method == 'POST':
        if 'save_budget' in request.POST:
            budget_form = BudgetForm(request.POST, prefix='budget')
            if budget_form.is_valid():
                budget = budget_form.save(commit=False)
                budget.created_by = request.user
                budget.save()
                messages.success(request, 'Budget saved successfully.')
                return redirect('finance:finance_budget_management')
        elif 'save_category' in request.POST:
            category_form = ExpenseCategoryForm(request.POST, prefix='category')
            if category_form.is_valid():
                category_form.save()
                messages.success(request, 'Expense category saved successfully.')
                return redirect('finance:finance_budget_management')

    edit_budget_id = request.GET.get('edit')
    if edit_budget_id:
        edit_budget = get_object_or_404(Budget.objects.select_related('category', 'created_by'), pk=edit_budget_id)
        edit_budget_form = BudgetForm(instance=edit_budget, prefix='edit_budget')

    budgets = Budget.objects.select_related('category', 'created_by').all()
    context = _base_finance_context()
    context.update({
        'active_finance_tab': 'budget',
        'budget_form': budget_form,
        'category_form': category_form,
        'edit_budget': edit_budget,
        'edit_budget_form': edit_budget_form,
        'budgets': budgets,
    })
    return render(request, 'finance/budget_management.html', context)


@login_required
@permission_required('finance.change_budget', raise_exception=True)
def budget_update(request, pk):
    if not _admin_guard(request):
        raise Http404
    budget = get_object_or_404(Budget, pk=pk)
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=budget, prefix='edit_budget')
        if form.is_valid():
            updated_budget = form.save(commit=False)
            if updated_budget.created_by is None:
                updated_budget.created_by = request.user
            updated_budget.save()
            messages.success(request, 'Budget updated successfully.')
        else:
            messages.error(request, 'Unable to update budget.')
    return redirect('finance:finance_budget_management')


@login_required
@permission_required('finance.view_income', raise_exception=True)
def income_management(request):
    if not _admin_guard(request):
        raise Http404

    form = IncomeForm(prefix='income')
    if request.method == 'POST':
        form = IncomeForm(request.POST, prefix='income')
        if form.is_valid():
            income = form.save(commit=False)
            income.recorded_by = request.user
            income.save()
            messages.success(request, 'Income recorded successfully.')
            return redirect('finance:finance_income_management')

    manual_income = Income.objects.select_related('recorded_by').all()[:25]
    school_fee_income = _safe_payment_feed(limit=25)
    context = _base_finance_context()
    context.update({
        'active_finance_tab': 'income',
        'income_form': form,
        'manual_income': manual_income,
        'school_fee_income': school_fee_income,
    })
    return render(request, 'finance/income_management.html', context)


@login_required
@permission_required('finance.view_income', raise_exception=True)
def profit_and_loss(request):
    if not _admin_guard(request):
        raise Http404

    year = int(request.GET.get('year', timezone.now().year))
    monthly_rows = []
    quarter_map = defaultdict(lambda: {'income': Decimal('0.00'), 'expenses': Decimal('0.00')})
    annual_income = Decimal('0.00')
    annual_expenses = Decimal('0.00')
    for month in range(1, 13):
        income_total = (
            (Income.objects.filter(date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
            +
            _safe_payment_total(year, month)
        )
        expense_total = Expense.objects.filter(date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        profit = income_total - expense_total
        monthly_rows.append({'label': month_name[month], 'income': income_total, 'expenses': expense_total, 'profit': profit})
        quarter = ((month - 1) // 3) + 1
        quarter_map[quarter]['income'] += income_total
        quarter_map[quarter]['expenses'] += expense_total
        annual_income += income_total
        annual_expenses += expense_total

    quarter_rows = []
    for quarter, values in sorted(quarter_map.items()):
        quarter_rows.append({
            'label': f'Q{quarter}',
            'income': values['income'],
            'expenses': values['expenses'],
            'profit': values['income'] - values['expenses'],
        })

    context = _base_finance_context()
    context.update({
        'active_finance_tab': 'profit',
        'selected_year': year,
        'monthly_rows': monthly_rows,
        'quarter_rows': quarter_rows,
        'annual_totals': {
            'income': annual_income,
            'expenses': annual_expenses,
            'profit': annual_income - annual_expenses,
        },
    })
    return render(request, 'finance/profit_and_loss.html', context)


@login_required
@permission_required('finance.view_monthlyfinancialreport', raise_exception=True)
def monthly_reports(request):
    if not _admin_guard(request):
        raise Http404

    today = timezone.now().date()
    year = int(request.GET.get('year', today.year))
    reports = []
    for month in range(1, 13):
        report, _ = MonthlyFinancialReport.objects.get_or_create(
            year=year,
            month=month,
            defaults={'generated_by': request.user},
        )
        if report.generated_by is None:
            report.generated_by = request.user
            report.save(update_fields=['generated_by', 'generated_at'])
        reports.append(report)

    report_rows = []
    for report in reports:
        budget_total = Budget.objects.filter(
            period_type=Budget.PERIOD_MONTHLY,
            year=report.year,
            month=report.month,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        if budget_total == 0:
            budget_total = Budget.objects.filter(
                period_type=Budget.PERIOD_ANNUAL,
                year=report.year,
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        expense_items = list(
            Expense.objects.filter(date__year=report.year, date__month=report.month)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        income_items = list(
            Income.objects.filter(date__year=report.year, date__month=report.month)
            .values('source')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        fee_income = _safe_payment_total(report.year, report.month)
        income_breakdown_text = ', '.join(
            [f"{item['source'].replace('_', ' ').title()}: {item['total']:.2f}" for item in income_items]
            + ([f'School Fees: {fee_income:.2f}'] if fee_income else [])
        ) or 'No income'
        expense_breakdown_text = ', '.join(
            [f"{item['category__name']}: {item['total']:.2f}" for item in expense_items]
        ) or 'No expenses'

        budget_variance = budget_total - report.total_expenses
        profitability = 'Profitable' if report.net_profit_loss >= 0 else 'Operating at a loss'
        report_rows.append({
            'report': report,
            'month_name': month_name[report.month],
            'income_breakdown': income_breakdown_text,
            'expense_breakdown': expense_breakdown_text,
            'budget_variance': budget_variance,
            'profitability': profitability,
        })

    context = _base_finance_context()
    context.update({
        'active_finance_tab': 'reports',
        'selected_year': year,
        'reports': reports,
        'report_rows': report_rows,
    })
    return render(request, 'finance/monthly_reports.html', context)


@login_required
def export_excel(request, report_type):
    if not _admin_guard(request):
        raise Http404
    if report_type == 'expenses':
        queryset = Expense.objects.select_related('category', 'created_by').all()
        category_id = request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return export_expenses_workbook(queryset, filename='finance-expenses.xlsx', title='Finance Expense Report')
    if report_type == 'budgets':
        queryset = Budget.objects.select_related('category', 'created_by').all()
        return export_budgets_workbook(queryset, filename='finance-budgets.xlsx', title='Budget Management Report')
    if report_type == 'reports':
        queryset = MonthlyFinancialReport.objects.all()
        return export_monthly_reports_workbook(queryset, filename='monthly-finance-reports.xlsx')
    if report_type == 'profit-loss':
        year = int(request.GET.get('year', timezone.now().year))
        return export_profit_and_loss_workbook(year, filename=f'profit-loss-{year}.xlsx')
    if report_type == 'annual-summary':
        year = int(request.GET.get('year', timezone.now().year))
        return export_annual_summary_workbook(year, filename=f'annual-financial-summary-{year}.xlsx')
    raise Http404
