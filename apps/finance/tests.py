from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AdminProfile
from apps.students.models import (
    StudentProfile, FinancialRecord, Payment
)
from apps.notifications.models import Notification
from apps.finance.services import FinancialService
from apps.finance.cache import DashboardCache
from apps.finance.tasks import recalculate_financial_status

from .models import Budget, Expense, ExpenseCategory, Income, MonthlyFinancialReport
from apps.students.admin import FinancialRecordAdmin, FinancialRecordInline


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
        self.record.tuition_paid = Decimal('0.00')
        self.record.tuition_balance = Decimal('25000.00')
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
        """Payment processing should not overwrite manually managed paid fields."""
        self.record.transport_paid = Decimal('1200.00')
        self.record.tuition_paid = Decimal('800.00')
        self.record.save(update_fields=['transport_paid', 'tuition_paid'])

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
        
        # Paid values remain finance-office controlled.
        self.record.refresh_from_db()
        self.assertEqual(self.record.transport_paid, Decimal('1200.00'))
        self.assertEqual(self.record.tuition_paid, Decimal('800.00'))
        self.assertEqual(self.record.transport_balance, Decimal('3800.00'))
        self.assertEqual(self.record.tuition_balance, Decimal('24200.00'))
        self.assertEqual(self.record.status, 'partial')
        self.assertEqual(self.record.payment_count, 1)
    
    def test_payment_reversal(self):
        """Payment reversal updates ledger metadata without changing paid summary values."""
        self.record.transport_paid = Decimal('1000.00')
        self.record.tuition_paid = Decimal('2000.00')
        self.record.save(update_fields=['transport_paid', 'tuition_paid'])

        # Create and process payment
        payment = Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('10000.00'),
            payment_method='cash',
            is_approved=True
        )
        FinancialService.process_payment(payment, self.admin)

        # Verify summary remains as entered by finance office.
        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('3000.00'))
        self.assertEqual(self.record.payment_count, 1)
        
        # Reverse payment
        result = FinancialService.reverse_payment(payment, self.admin, 'Test reversal')
        self.assertTrue(result['success'])
        
        # Check payment is marked reversed
        payment.refresh_from_db()
        self.assertTrue(payment.is_reversed)
        self.assertEqual(payment.status, 'reversed')
        
        # Financial summary fields remain unchanged; only payment metadata changes.
        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('3000.00'))
        self.assertEqual(self.record.total_balance, Decimal('27000.00'))
        self.assertEqual(self.record.payment_count, 0)
    
    def test_multiple_payments_single_record(self):
        """Multiple ledger payments should not mutate paid summary fields."""
        self.record.transport_paid = Decimal('500.00')
        self.record.tuition_paid = Decimal('1500.00')
        self.record.save(update_fields=['transport_paid', 'tuition_paid'])

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
        
        # Summary remains record-driven; payment count/date still synchronize.
        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('2000.00'))
        self.assertEqual(self.record.total_balance, Decimal('28000.00'))
        self.assertEqual(self.record.payment_count, 2)
    
    def test_overpayment_handling(self):
        """Overpayment remainder is computed from payment ledger capacity."""
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
        
        # Financial summary remains manually managed.
        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('0.00'))
        self.assertEqual(self.record.total_balance, Decimal('30000.00'))
        self.assertEqual(self.record.status, 'pending')

    def test_payment_update_recalculates_balances(self):
        """Updating payment amount should only refresh payment metadata."""
        self.record.transport_paid = Decimal('500.00')
        self.record.tuition_paid = Decimal('500.00')
        self.record.save(update_fields=['transport_paid', 'tuition_paid'])

        payment = Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('8000.00'),
            payment_method='cash',
            is_approved=True,
        )
        FinancialService.process_payment(payment, self.admin)

        payment.amount = Decimal('12000.00')
        payment.save(update_fields=['amount'])

        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('1000.00'))
        self.assertEqual(self.record.total_balance, Decimal('29000.00'))
        self.assertEqual(self.record.payment_count, 1)

    def test_pending_to_approved_payment_updates_record(self):
        """Approval transition should synchronize payment metadata only."""
        self.record.transport_paid = Decimal('250.00')
        self.record.tuition_paid = Decimal('750.00')
        self.record.save(update_fields=['transport_paid', 'tuition_paid'])

        payment = Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('6000.00'),
            payment_method='cash',
            is_approved=False,
            status='pending',
        )

        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('1000.00'))

        payment.is_approved = True
        payment.status = 'approved'
        payment.save(update_fields=['is_approved', 'status'])

        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('1000.00'))
        self.assertEqual(self.record.payment_count, 1)
        self.assertIsNotNone(self.record.last_payment_date)

    def test_payment_delete_recalculates_record(self):
        """Deleting a payment should recompute payment metadata only."""
        self.record.transport_paid = Decimal('1000.00')
        self.record.tuition_paid = Decimal('500.00')
        self.record.save(update_fields=['transport_paid', 'tuition_paid'])

        payment1 = Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('5000.00'),
            payment_method='cash',
            is_approved=True,
        )
        payment2 = Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('7000.00'),
            payment_method='bank_transfer',
            is_approved=True,
        )
        FinancialService.process_payment(payment1, self.admin)
        FinancialService.process_payment(payment2, self.admin)

        payment2.delete()

        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('1500.00'))
        self.assertEqual(self.record.total_balance, Decimal('28500.00'))
        self.assertEqual(self.record.payment_count, 1)

    @patch('apps.notifications.signals.send_notification_email.delay', side_effect=Exception('broker down'))
    @patch('apps.notifications.signals.send_notification_email')
    def test_payment_creation_succeeds_when_celery_is_unavailable(self, send_notification_email_mock, _delay_mock):
        self.record.transport_paid = Decimal('700.00')
        self.record.tuition_paid = Decimal('300.00')
        self.record.save(update_fields=['transport_paid', 'tuition_paid'])

        payment = Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('5000.00'),
            payment_method='cash',
            is_approved=True,
        )

        self.assertIsNotNone(payment.pk)
        self.record.refresh_from_db()
        self.assertEqual(self.record.total_paid, Decimal('1000.00'))
        self.assertEqual(self.record.payment_count, 1)
        self.assertTrue(send_notification_email_mock.called)


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
            transport_paid=Decimal('5000.00'),
            tuition_paid=Decimal('5000.00'),
        )
        
        record2 = FinancialRecord.objects.create(
            student=self.student1,
            term='term2',
            year=2024,
            transport_fee=Decimal('5000.00'),
            school_tuition=Decimal('25000.00'),
            transport_paid=Decimal('1000.00'),
            tuition_paid=Decimal('4000.00'),
        )
        
        summary = FinancialService.get_student_financial_summary(self.student1)
        
        self.assertEqual(summary['total_due'], Decimal('60000.00'))
        self.assertEqual(summary['total_paid'], Decimal('15000.00'))
        self.assertEqual(summary['total_balance'], Decimal('45000.00'))
        self.assertEqual(summary['record_count'], 2)
        self.assertEqual(summary['payment_count'], 0)

    def test_summary_uses_financial_record_paid_fields(self):
        """Financial summary totals are sourced from FinancialRecord paid fields."""
        record = FinancialRecord.objects.create(
            student=self.student1,
            term='term1',
            year=2025,
            transport_fee=Decimal('5000.00'),
            school_tuition=Decimal('25000.00'),
            transport_paid=Decimal('4000.00'),
            tuition_paid=Decimal('2000.00'),
        )

        approved = Payment.objects.create(
            student=self.student1,
            financial_record=record,
            amount=Decimal('4000.00'),
            payment_method='cash',
            is_approved=True,
            status='approved',
        )
        pending = Payment.objects.create(
            student=self.student1,
            financial_record=record,
            amount=Decimal('2000.00'),
            payment_method='cash',
            is_approved=False,
            status='pending',
        )
        reversed_payment = Payment.objects.create(
            student=self.student1,
            financial_record=record,
            amount=Decimal('1000.00'),
            payment_method='cash',
            is_approved=True,
            status='approved',
            is_reversed=True,
        )

        FinancialService.process_payment(approved, self.admin)

        summary = FinancialService.get_student_financial_summary(self.student1)
        self.assertEqual(summary['total_paid'], Decimal('6000.00'))
        self.assertEqual(summary['payment_count'], 1)

    def test_update_financial_record_allows_manual_paid_and_derives_balances(self):
        """Service update should accept paid fields and auto-derive balances."""
        record = FinancialRecord.objects.create(
            student=self.student1,
            term='term1',
            year=2025,
            transport_fee=Decimal('1000.00'),
            school_tuition=Decimal('5000.00'),
        )

        result = FinancialService.update_financial_record(
            record,
            self.admin,
            transport_fee=Decimal('1500.00'),
            tuition_paid=Decimal('2500.00'),
            tuition_balance=Decimal('1.00'),
            transport_paid=Decimal('500.00'),
            transport_balance=Decimal('2.00'),
        )

        self.assertTrue(result['success'])
        record.refresh_from_db()

        self.assertEqual(record.transport_fee, Decimal('1500.00'))
        self.assertEqual(record.transport_paid, Decimal('500.00'))
        self.assertEqual(record.transport_balance, Decimal('1000.00'))
        self.assertEqual(record.tuition_paid, Decimal('2500.00'))
        self.assertEqual(record.tuition_balance, Decimal('2500.00'))

    def test_update_financial_record_rejects_paid_above_fee(self):
        record = FinancialRecord.objects.create(
            student=self.student1,
            term='term2',
            year=2025,
            transport_fee=Decimal('800.00'),
            school_tuition=Decimal('1200.00'),
        )

        result = FinancialService.update_financial_record(
            record,
            self.admin,
            transport_paid=Decimal('900.00'),
        )

        self.assertFalse(result['success'])


class FinancialRecordAdminPolicyTests(TestCase):
    """Administrative UI should allow paid edits but keep balances read-only."""

    def test_financial_record_admin_marks_only_balance_fields_readonly(self):
        readonly = set(FinancialRecordAdmin.readonly_fields)
        self.assertIn('transport_balance', readonly)
        self.assertIn('tuition_balance', readonly)
        self.assertNotIn('transport_paid', readonly)
        self.assertNotIn('tuition_paid', readonly)


class FinancialRecordBusinessRuleRegressionTests(TestCase):
    """Explicit regression scenarios for fee, paid, and balance behavior."""

    def setUp(self):
        self.user = User.objects.create_user('scenario-student', 'scenario@example.com', 'password')
        self.student = StudentProfile.objects.create(
            user=self.user,
            student_id='STU777',
            current_class='Form 4',
            approved=True,
        )

    def test_scenario_1_tuition_balance_formula(self):
        record = FinancialRecord.objects.create(
            student=self.student,
            term='term1',
            year=2026,
            school_tuition=Decimal('550.00'),
            tuition_paid=Decimal('400.00'),
            transport_fee=Decimal('0.00'),
            transport_paid=Decimal('0.00'),
        )
        self.assertEqual(record.tuition_balance, Decimal('150.00'))

    def test_scenario_2_transport_balance_formula(self):
        record = FinancialRecord.objects.create(
            student=self.student,
            term='term1',
            year=2026,
            transport_fee=Decimal('80.00'),
            transport_paid=Decimal('30.00'),
            school_tuition=Decimal('0.00'),
            tuition_paid=Decimal('0.00'),
        )
        self.assertEqual(record.transport_balance, Decimal('50.00'))

    def test_scenario_3_edit_tuition_paid_updates_balance(self):
        record = FinancialRecord.objects.create(
            student=self.student,
            term='term1',
            year=2026,
            school_tuition=Decimal('550.00'),
            tuition_paid=Decimal('400.00'),
        )
        self.assertEqual(record.tuition_balance, Decimal('150.00'))

        record.tuition_paid = Decimal('500.00')
        record.save(update_fields=['tuition_paid'])
        record.refresh_from_db()
        self.assertEqual(record.tuition_balance, Decimal('50.00'))

    def test_scenario_4_edit_tuition_fee_updates_balance(self):
        record = FinancialRecord.objects.create(
            student=self.student,
            term='term1',
            year=2026,
            school_tuition=Decimal('550.00'),
            tuition_paid=Decimal('400.00'),
        )
        self.assertEqual(record.tuition_balance, Decimal('150.00'))

        record.school_tuition = Decimal('600.00')
        record.save(update_fields=['school_tuition'])
        record.refresh_from_db()
        self.assertEqual(record.tuition_balance, Decimal('200.00'))

    def test_scenario_5_multiple_payments_keep_history_and_summary_consistent(self):
        record = FinancialRecord.objects.create(
            student=self.student,
            term='term2',
            year=2026,
            school_tuition=Decimal('550.00'),
            tuition_paid=Decimal('400.00'),
            transport_fee=Decimal('80.00'),
            transport_paid=Decimal('30.00'),
        )

        payment1 = Payment.objects.create(
            student=self.student,
            financial_record=record,
            amount=Decimal('200.00'),
            payment_method='cash',
            is_approved=True,
            status='approved',
        )
        payment2 = Payment.objects.create(
            student=self.student,
            financial_record=record,
            amount=Decimal('150.00'),
            payment_method='cash',
            is_approved=True,
            status='approved',
        )
        payment3 = Payment.objects.create(
            student=self.student,
            financial_record=record,
            amount=Decimal('100.00'),
            payment_method='bank_transfer',
            is_approved=True,
            status='approved',
        )

        record.refresh_from_db()
        self.assertEqual(Payment.objects.filter(financial_record=record).count(), 3)
        self.assertEqual(record.tuition_balance, Decimal('150.00'))
        self.assertEqual(record.transport_balance, Decimal('50.00'))
        self.assertEqual(record.payment_count, 3)
        self.assertEqual(Payment.objects.filter(pk__in=[payment1.pk, payment2.pk, payment3.pk]).count(), 3)

    def test_financial_record_inline_marks_only_balance_fields_readonly(self):
        readonly = set(FinancialRecordInline.readonly_fields)
        self.assertIn('transport_balance', readonly)
        self.assertIn('tuition_balance', readonly)
        self.assertNotIn('transport_paid', readonly)
        self.assertNotIn('tuition_paid', readonly)


@override_settings(
    CELERY_BROKER_URL='memory://',
    CELERY_RESULT_BACKEND='cache+memory://',
    CELERY_TASK_ALWAYS_EAGER=True,
)
class FinancialIntegritySignalsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('signalstudent', 'signalstudent@example.com', 'password')
        self.student = StudentProfile.objects.create(
            user=self.user,
            student_id='STU900',
            current_class='Form 2',
            approved=True,
        )
        self.record = FinancialRecord.objects.create(
            student=self.student,
            term='term1',
            year=2026,
            transport_fee=Decimal('1000.00'),
            school_tuition=Decimal('4000.00'),
            transport_balance=Decimal('1000.00'),
            tuition_balance=Decimal('4000.00'),
        )

    def test_delete_financial_record_with_active_payment_is_blocked(self):
        Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('500.00'),
            payment_method='cash',
            is_approved=True,
            status='approved',
        )

        with self.assertRaises(ProtectedError):
            self.record.delete()


@override_settings(
    CELERY_BROKER_URL='memory://',
    CELERY_RESULT_BACKEND='cache+memory://',
    CELERY_TASK_ALWAYS_EAGER=True,
)
class FinancialTasksSynchronizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('taskstudent', 'taskstudent@example.com', 'password')
        self.student = StudentProfile.objects.create(
            user=self.user,
            student_id='STU901',
            current_class='Form 3',
            approved=True,
        )
        self.record = FinancialRecord.objects.create(
            student=self.student,
            term='term2',
            year=2026,
            transport_fee=Decimal('2000.00'),
            school_tuition=Decimal('6000.00'),
            transport_balance=Decimal('2000.00'),
            tuition_balance=Decimal('6000.00'),
        )

    def test_recalculate_task_rebuilds_balances_from_fee_and_paid_fields(self):
        Payment.objects.create(
            student=self.student,
            financial_record=self.record,
            amount=Decimal('2500.00'),
            payment_method='cash',
            is_approved=True,
            status='approved',
        )

        # Intentionally corrupt balances while keeping paid values authoritative.
        self.record.transport_paid = Decimal('1200.00')
        self.record.tuition_paid = Decimal('700.00')
        self.record.transport_balance = Decimal('2000.00')  # should become 800
        self.record.tuition_balance = Decimal('6000.00')  # should become 5300
        self.record.status = 'pending'
        self.record.payment_count = 0
        self.record.last_payment_date = None
        self.record.save(update_fields=[
            'transport_paid',
            'tuition_paid',
            'transport_balance',
            'tuition_balance',
            'status',
            'payment_count',
            'last_payment_date',
        ])

        result = recalculate_financial_status()
        self.assertEqual(result['status'], 'success')

        self.record.refresh_from_db()
        self.assertEqual(self.record.transport_paid, Decimal('1200.00'))
        self.assertEqual(self.record.tuition_paid, Decimal('700.00'))
        self.assertEqual(self.record.transport_balance, Decimal('800.00'))
        self.assertEqual(self.record.tuition_balance, Decimal('5300.00'))
        self.assertEqual(self.record.payment_count, 1)
        self.assertIsNotNone(self.record.last_payment_date)
