from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import AdminProfile

from .models import Budget, Expense, ExpenseCategory, Income, MonthlyFinancialReport


class FinanceViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='financeadmin', password='password123')
        self.user.is_staff = True
        self.user.save()
        AdminProfile.objects.create(user=self.user, approved=True, email_verified=True)
        permissions = Permission.objects.filter(content_type__app_label='finance')
        self.user.user_permissions.add(*permissions)
        self.client.login(username='financeadmin', password='password123')

        self.category, _ = ExpenseCategory.objects.get_or_create(name='Fuel', defaults={'sort_order': 1})
        Budget.objects.create(category=self.category, period_type=Budget.PERIOD_ANNUAL, year=2026, amount=Decimal('1000.00'), created_by=self.user)
        Expense.objects.create(category=self.category, date='2026-01-12', description='Bus fuel', amount=Decimal('250.00'), created_by=self.user)
        Income.objects.create(source=Income.SOURCE_OTHER, amount=Decimal('400.00'), date='2026-01-15', recorded_by=self.user)

    def test_finance_dashboard_renders_for_admin(self):
        response = self.client.get(reverse('finance:finance_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Finance Dashboard')
        self.assertContains(response, 'Fuel')

    def test_expense_create_records_current_user(self):
        response = self.client.post(reverse('finance:finance_expense_add'), {
            'date': '2026-02-02',
            'category': self.category.pk,
            'description': 'Emergency top-up',
            'amount': '55.00',
        })
        self.assertRedirects(response, reverse('finance:finance_expenses'))
        expense = Expense.objects.get(description='Emergency top-up')
        self.assertEqual(expense.created_by, self.user)

    def test_monthly_reports_page_materializes_reports(self):
        response = self.client.get(reverse('finance:finance_monthly_reports') + '?year=2026')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MonthlyFinancialReport.objects.filter(year=2026).count(), 12)

    def test_non_admin_cannot_access_finance_pages(self):
        self.client.logout()
        outsider = User.objects.create_user(username='teacherish', password='password123')
        self.client.login(username='teacherish', password='password123')
        response = self.client.get(reverse('finance:finance_dashboard'))
        self.assertIn(response.status_code, [302, 403, 404])
