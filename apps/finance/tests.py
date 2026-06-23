from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import Permission, User
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AdminProfile
from apps.students.models import (
    StudentProfile, FinancialRecord, Payment
)
from apps.notifications.models import Notification
from apps.finance.services import FinancialService
from apps.finance.cache import DashboardCache

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


# ============================================================================
# Financial Synchronization Tests
# ============================================================================


class FinancialRecordSynchronizationTests(TestCase):
    """Tests for FinancialRecord synchronization"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
        self.student = StudentProfile.objects.create(
            user=self.user,
            student_id='STU001',
            current_class='Form 1',
            approved=True
        )
        
        self.record = FinancialRecord.objects.create(
            student=self.student,
            term='term1',
            year=2024,
            transport_fee=Decimal('5000.00'),
            school_tuition=Decimal('25000.00'),
            transport_balance=Decimal('5000.00'),
            tuition_balance=Decimal('25000.00'),
            due_date=timezone.now().date() + timedelta(days=30)
        )
    
    def test_financial_record_status_calculation(self):
        """Test that status is calculated correctly"""
        self.record.update_status()
        self.assertEqual(self.record.status, 'pending')
        
        # Partially paid
        self.record.transport_paid = Decimal('2500.00')
        self.record.transport_balance = Decimal('2500.00')
        self.record.update_status()
        self.assertEqual(self.record.status, 'partial')
        
        # Fully paid
        self.record.transport_paid = Decimal('5000.00')
        self.record.transport_balance = Decimal('0.00')
        self.record.tuition_paid = Decimal('25000.00')
        self.record.tuition_balance = Decimal('0.00')
        self.record.update_status()
        self.assertEqual(self.record.status, 'paid')
        
        # Overdue
        self.record.due_date = timezone.now().date() - timedelta(days=1)
        self.record.transport_paid = Decimal('0.00')
        self.record.transport_balance = Decimal('5000.00')
        self.record.update_status()
        self.assertEqual(self.record.status, 'overdue')
    
    def test_total_calculations(self):
        """Test that total calculations are correct"""
        self.assertEqual(self.record.total_fee, Decimal('30000.00'))
        self.assertEqual(self.record.total_paid, Decimal('0.00'))
        self.assertEqual(self.record.total_balance, Decimal('30000.00'))


class PaymentSynchronizationTests(TransactionTestCase):
    """Tests for Payment synchronization"""
    
    def setUp(self):
        """Set up test data"""
        self.admin = User.objects.create_user('admin', 'admin@example.com', 'password')
        self.admin.is_staff = True
        self.admin.save()
        
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
        self.student = StudentProfile.objects.create(
            user=self.user,
            student_id='STU001',
            current_class='Form 1',
            approved=True
        )
        
        self.record = FinancialRecord.objects.create(
            student=self.student,
            term='term1',
            year=2024,
            transport_fee=Decimal('5000.00'),
            school_tuition=Decimal('25000.00'),
            transport_balance=Decimal('5000.00'),
            tuition_balance=Decimal('25000.00'),
            due_date=timezone.now().date() + timedelta(days=30)
        )
    
    def test_payment_creation_and_processing(self):
        """Test that payment creation triggers synchronization"""
        # Create payment
        payment = Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('10000.00'),
            payment_method='cash',
            is_approved=True
        )
        
        # Process payment through service
        result = FinancialService.process_payment(payment, self.admin)
        
        self.assertTrue(result['success'])
        
        # Check financial record was updated
        self.record.refresh_from_db()
        self.assertEqual(self.record.transport_paid, Decimal('5000.00'))
        self.assertEqual(self.record.tuition_paid, Decimal('5000.00'))
        self.assertEqual(self.record.transport_balance, Decimal('0.00'))
        self.assertEqual(self.record.tuition_balance, Decimal('20000.00'))
        self.assertEqual(self.record.status, 'partial')
        self.assertEqual(self.record.payment_count, 1)
    
    def test_payment_reversal(self):
        """Test that payment reversal works correctly"""
        # Create and process payment
        payment = Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('10000.00'),
            payment_method='cash',
            is_approved=True
        )
        FinancialService.process_payment(payment, self.admin)
        
        # Verify payment was applied
        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('10000.00'))
        
        # Reverse payment
        result = FinancialService.reverse_payment(payment, self.admin, 'Test reversal')
        self.assertTrue(result['success'])
        
        # Check payment is marked reversed
        payment.refresh_from_db()
        self.assertTrue(payment.is_reversed)
        self.assertEqual(payment.status, 'reversed')
        
        # Check financial record balances were reversed
        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('0.00'))
        self.assertEqual(self.record.total_balance, Decimal('30000.00'))
        self.assertEqual(self.record.status, 'pending')
    
    def test_multiple_payments_single_record(self):
        """Test multiple payments against single financial record"""
        # First payment
        payment1 = Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('10000.00'),
            payment_method='cash',
            is_approved=True
        )
        FinancialService.process_payment(payment1, self.admin)
        
        # Second payment
        payment2 = Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('15000.00'),
            payment_method='bank_transfer',
            is_approved=True
        )
        FinancialService.process_payment(payment2, self.admin)
        
        # Check cumulative balance
        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('25000.00'))
        self.assertEqual(self.record.total_balance, Decimal('5000.00'))
        self.assertEqual(self.record.payment_count, 2)
    
    def test_overpayment_handling(self):
        """Test that overpayment is handled correctly"""
        payment = Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('35000.00'),  # More than total_fee
            payment_method='cash',
            is_approved=True
        )
        
        result = FinancialService.process_payment(payment, self.admin)
        
        # Should have remainder
        self.assertEqual(result['remainder'], Decimal('5000.00'))
        
        # Record should show full payment
        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('30000.00'))
        self.assertEqual(self.record.total_balance, Decimal('0.00'))
        self.assertEqual(self.record.status, 'paid')


class FinancialServiceTests(TestCase):
    """Tests for FinancialService"""
    
    def setUp(self):
        """Set up test data"""
        self.admin = User.objects.create_user('admin', 'admin@example.com', 'password')
        self.admin.is_staff = True
        self.admin.save()
        
        self.user1 = User.objects.create_user('student1', 'student1@example.com', 'password')
        self.student1 = StudentProfile.objects.create(
            user=self.user1,
            student_id='STU001',
            current_class='Form 1',
            approved=True
        )
    
    def test_get_student_financial_summary(self):
        """Test retrieval of student financial summary"""
        # Create records
        record1 = FinancialRecord.objects.create(
            student=self.student1,
            term='term1',
            year=2024,
            transport_fee=Decimal('5000.00'),
            school_tuition=Decimal('25000.00'),
            transport_balance=Decimal('0.00'),
            tuition_balance=Decimal('20000.00')
        )
        
        record2 = FinancialRecord.objects.create(
            student=self.student1,
            term='term2',
            year=2024,
            transport_fee=Decimal('5000.00'),
            school_tuition=Decimal('25000.00'),
            transport_balance=Decimal('5000.00'),
            tuition_balance=Decimal('25000.00')
        )
        
        # Create payment
        Payment.objects.create(
            student=self.student1,
            financial_record=record1,
            amount=Decimal('5000.00'),
            payment_method='cash',
            is_approved=True
        )
        
        summary = FinancialService.get_student_financial_summary(self.student1)
        
        self.assertEqual(summary['total_due'], Decimal('60000.00'))
        self.assertEqual(summary['total_paid'], Decimal('5000.00'))
        self.assertEqual(summary['total_balance'], Decimal('55000.00'))
        self.assertEqual(summary['record_count'], 2)
        self.assertEqual(summary['payment_count'], 1)
