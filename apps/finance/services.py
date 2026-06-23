"""
Financial Services for Aspire Academy Portal

Handles payment processing, balance updates, reversals, and synchronization
of all financial data across dashboards and reports.
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, F, Sum
from apps.students.models import FinancialRecord, Payment, StudentProfile
from apps.notifications.models import Notification
from django.contrib.auth.models import User


class FinancialService:
    """
    Centralized service for all financial operations.
    
    Ensures:
    - Atomic transactions
    - Proper balance calculations
    - Status synchronization
    - Notification creation
    - Dashboard cache invalidation
    """
    
    @staticmethod
    @transaction.atomic
    def process_payment(payment, user=None):
        """
        Process a payment and synchronize all affected records.
        
        Args:
            payment: Payment instance
            user: User making the payment (for audit trail)
            
        Returns:
            dict with result status and messages
        """
        from django.core.cache import cache
        
        if payment.is_reversed:
            return {
                'success': False,
                'message': 'Cannot process reversed payment',
                'status_code': 400
            }
        
        if not payment.financial_record:
            return {
                'success': False,
                'message': 'Payment must be linked to a financial record',
                'status_code': 400
            }
        
        try:
            # Step 1: Apply payment to financial record
            financial_record = payment.financial_record
            remainder = financial_record.apply_payment(payment.amount)
            
            # Step 2: Update payment metadata
            payment.approved_by = user
            payment.approved_at = timezone.now()
            payment.status = 'approved'
            payment.is_approved = True
            payment.save(update_fields=['approved_by', 'approved_at', 'status', 'is_approved'])
            
            # Step 3: Update financial record status and metadata
            financial_record.update_status()
            financial_record.last_payment_date = timezone.now()
            financial_record.payment_count = financial_record.payments.filter(
                is_reversed=False
            ).count()
            financial_record.updated_by = user
            financial_record.save(update_fields=[
                'status', 'last_payment_date', 'payment_count', 'updated_by', 'updated_at'
            ])
            
            # Step 4: Create notifications
            FinancialService._create_payment_notifications(payment, financial_record, remainder)
            
            # Step 5: Invalidate relevant caches
            FinancialService._invalidate_student_cache(payment.student)
            FinancialService._invalidate_dashboard_cache()
            
            return {
                'success': True,
                'message': 'Payment processed successfully',
                'remainder': remainder,
                'status_code': 200
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error processing payment: {str(e)}',
                'status_code': 500
            }
    
    @staticmethod
    @transaction.atomic
    def reverse_payment(payment, user, reason=''):
        """
        Reverse a previously processed payment.
        
        Args:
            payment: Payment to reverse
            user: User reversing the payment (for audit)
            reason: Reason for reversal
            
        Returns:
            dict with result status
        """
        from django.core.cache import cache
        
        if payment.is_reversed:
            return {
                'success': False,
                'message': 'Payment already reversed',
                'status_code': 400
            }
        
        if payment.financial_record is None:
            return {
                'success': False,
                'message': 'Cannot reverse payment not linked to a record',
                'status_code': 400
            }
        
        try:
            financial_record = payment.financial_record
            
            # Step 1: Reverse the balance changes
            financial_record.transport_paid -= payment.amount
            financial_record.tuition_paid -= payment.amount
            financial_record.transport_balance = financial_record.transport_fee - financial_record.transport_paid
            financial_record.tuition_balance = financial_record.school_tuition - financial_record.tuition_paid
            
            # Ensure no negative balances
            financial_record.transport_balance = max(financial_record.transport_balance, Decimal('0.00'))
            financial_record.tuition_balance = max(financial_record.tuition_balance, Decimal('0.00'))
            
            # Step 2: Update payment reversal status
            payment.is_reversed = True
            payment.status = 'reversed'
            payment.reversed_by = user
            payment.reversed_at = timezone.now()
            payment.reversal_reason = reason
            payment.save(update_fields=[
                'is_reversed', 'status', 'reversed_by', 'reversed_at', 'reversal_reason'
            ])
            
            # Step 3: Update financial record status
            financial_record.update_status()
            financial_record.payment_count = financial_record.payments.filter(
                is_reversed=False
            ).count()
            financial_record.updated_by = user
            financial_record.save(update_fields=[
                'transport_paid', 'tuition_paid', 'transport_balance', 'tuition_balance',
                'status', 'payment_count', 'updated_by', 'updated_at'
            ])
            
            # Step 4: Create reversal notification
            FinancialService._create_reversal_notification(payment, financial_record, reason)
            
            # Step 5: Invalidate caches
            FinancialService._invalidate_student_cache(payment.student)
            FinancialService._invalidate_dashboard_cache()
            
            return {
                'success': True,
                'message': f'Payment reversed successfully. Reason: {reason}',
                'status_code': 200
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error reversing payment: {str(e)}',
                'status_code': 500
            }
    
    @staticmethod
    @transaction.atomic
    def update_financial_record(financial_record, user, **updates):
        """
        Update a financial record and synchronize all dependent data.
        
        Args:
            financial_record: FinancialRecord to update
            user: User making the update
            **updates: Field updates (transport_fee, school_tuition, etc.)
            
        Returns:
            dict with result status
        """
        from django.core.cache import cache
        
        try:
            # Update the fields
            for field, value in updates.items():
                if hasattr(financial_record, field):
                    setattr(financial_record, field, value)
            
            # Update balance fields based on new fees
            if 'transport_fee' in updates:
                financial_record.transport_balance = max(
                    financial_record.transport_fee - financial_record.transport_paid,
                    Decimal('0.00')
                )
            
            if 'school_tuition' in updates:
                financial_record.tuition_balance = max(
                    financial_record.school_tuition - financial_record.tuition_paid,
                    Decimal('0.00')
                )
            
            # Update metadata
            financial_record.updated_by = user
            financial_record.update_status()
            financial_record.save()
            
            # Create notification for significant changes
            if 'transport_fee' in updates or 'school_tuition' in updates:
                FinancialService._create_record_update_notification(financial_record)
            
            # Invalidate caches
            FinancialService._invalidate_student_cache(financial_record.student)
            FinancialService._invalidate_dashboard_cache()
            
            return {
                'success': True,
                'message': 'Financial record updated and synchronized',
                'status_code': 200
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error updating financial record: {str(e)}',
                'status_code': 500
            }
    
    @staticmethod
    def get_student_financial_summary(student):
        """
        Get complete financial summary for a student.
        Used by dashboards to ensure consistency.
        
        Args:
            student: StudentProfile instance
            
        Returns:
            dict with summary data
        """
        records = student.financial_records.all()
        payments = student.payments.filter(is_reversed=False)
        
        total_due = records.aggregate(total=Sum('total_fee'))['total'] or Decimal('0.00')
        total_paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_balance = records.aggregate(total=Sum('total_balance'))['total'] or Decimal('0.00')
        
        overdue_count = records.filter(
            Q(status='overdue') | 
            (Q(due_date__lt=timezone.now().date()) & Q(total_balance__gt=0))
        ).count()
        
        return {
            'total_due': total_due,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'overdue_count': overdue_count,
            'record_count': records.count(),
            'payment_count': payments.count(),
            'last_payment_date': payments.order_by('-payment_date').first().payment_date 
                                if payments.exists() else None,
            'status': 'paid' if total_balance == 0 else 'overdue' if overdue_count > 0 else 'pending'
        }
    
    @staticmethod
    def get_financial_dashboard_summary():
        """
        Get dashboard summary for admin.
        
        Returns:
            dict with dashboard metrics
        """
        total_students = StudentProfile.objects.filter(approved=True).count()
        total_collected = Payment.objects.filter(is_reversed=False).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        outstanding_records = FinancialRecord.objects.filter(
            Q(transport_balance__gt=0) | Q(tuition_balance__gt=0)
        )
        total_outstanding = outstanding_records.aggregate(
            total=Sum(F('transport_balance') + F('tuition_balance'))
        )['total'] or Decimal('0.00')
        
        overdue_records = outstanding_records.filter(
            due_date__lt=timezone.now().date()
        )
        
        # Income breakdown by term
        term_income = FinancialRecord.objects.values('term', 'year').annotate(
            total_paid=Sum(F('transport_paid') + F('tuition_paid')),
            total_balance=Sum(F('transport_balance') + F('tuition_balance'))
        ).order_by('-year', 'term')[:6]
        
        return {
            'total_students': total_students,
            'total_collected': total_collected,
            'total_outstanding': total_outstanding,
            'overdue_count': overdue_records.count(),
            'term_income': list(term_income),
            'collection_rate': (
                (total_collected / (total_collected + total_outstanding) * 100) 
                if (total_collected + total_outstanding) > 0 
                else Decimal('0.00')
            )
        }
    
    @staticmethod
    def _create_payment_notifications(payment, financial_record, remainder):
        """Create notifications after payment processing"""
        from django.conf import settings
        from django.core.mail import send_mail
        
        # Notification to student
        student_msg = (
            f"Payment of {payment.amount:.2f} has been received for {financial_record.get_term_display()} {financial_record.year}. "
            f"Receipt: {payment.receipt_number}. "
            f"Remaining balance: {financial_record.total_balance:.2f}"
        )
        Notification.objects.create(
            recipient=payment.student.user,
            title='Payment Received',
            message=student_msg
        )
        
        # Email to student
        if payment.student.user.email:
            try:
                send_mail(
                    'Payment Received',
                    student_msg,
                    getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
                    [payment.student.user.email],
                    fail_silently=True
                )
            except Exception:
                pass
        
        # Notification to admin
        admin_msg = (
            f"{payment.student.user.username} paid {payment.amount:.2f} for {financial_record.get_term_display()} {financial_record.year}. "
            f"Receipt: {payment.receipt_number}. "
            f"New balance: {financial_record.total_balance:.2f}"
        )
        for admin in User.objects.filter(is_staff=True):
            Notification.objects.create(
                recipient=admin,
                title='Student Payment Recorded',
                message=admin_msg
            )
    
    @staticmethod
    def _create_reversal_notification(payment, financial_record, reason):
        """Create notifications after payment reversal"""
        # Student notification
        msg = f"Payment {payment.receipt_number} of {payment.amount:.2f} has been reversed. Reason: {reason}"
        Notification.objects.create(
            recipient=payment.student.user,
            title='Payment Reversed',
            message=msg
        )
        
        # Admin notification
        admin_msg = f"{payment.student.user.username}'s payment {payment.receipt_number} ({payment.amount:.2f}) has been reversed. Reason: {reason}"
        for admin in User.objects.filter(is_staff=True):
            Notification.objects.create(
                recipient=admin,
                title='Payment Reversed',
                message=admin_msg
            )
    
    @staticmethod
    def _create_record_update_notification(financial_record):
        """Create notification when financial record is updated"""
        msg = (
            f"Fee record for {financial_record.get_term_display()} {financial_record.year} has been updated. "
            f"New total due: {financial_record.total_fee:.2f}. "
            f"New balance: {financial_record.total_balance:.2f}"
        )
        Notification.objects.create(
            recipient=financial_record.student.user,
            title='Fee Record Updated',
            message=msg
        )
    
    @staticmethod
    def _invalidate_student_cache(student):
        """Invalidate cached data for a student"""
        from django.core.cache import cache
        cache_keys = [
            f'student_financial_summary_{student.id}',
            f'student_balance_{student.id}',
            f'student_dashboard_{student.id}'
        ]
        cache.delete_many(cache_keys)
    
    @staticmethod
    def _invalidate_dashboard_cache():
        """Invalidate all dashboard caches"""
        from django.core.cache import cache
        cache_keys = [
            'admin_financial_dashboard',
            'admin_dashboard_metrics',
            'financial_dashboard_summary'
        ]
        cache.delete_many(cache_keys)
