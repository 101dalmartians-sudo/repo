"""
Financial Background Tasks for Celery

Handles periodic synchronization, report generation, and data consistency checks.
"""

from celery import shared_task
from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Q, F, Sum
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from apps.students.models import (
    FinancialRecord, Payment, StudentProfile, AuditLog, AttendanceRecord
)
from apps.finance.models import MonthlyFinancialReport, Income, Expense, Budget
from apps.notifications.models import Notification
from apps.finance.services import FinancialService
from apps.finance.cache import DashboardCache


@shared_task
def recalculate_financial_status():
    """
    Recalculate status for all financial records based on current balances.
    Runs periodically to ensure status is always accurate.
    """
    try:
        records = FinancialRecord.objects.all()
        updated_count = 0
        
        for record in records:
            old_status = record.status
            record.update_status()
            
            if record.status != old_status:
                record.save(update_fields=['status', 'updated_at'])
                updated_count += 1
                
                # Notify if status changed to overdue
                if record.status == 'overdue':
                    msg = f"Your fee record for {record.get_term_display()} {record.year} is now overdue. Please settle payment."
                    Notification.objects.create(
                        recipient=record.student.user,
                        title='Fee Payment Overdue',
                        message=msg
                    )
        
        # Invalidate caches
        DashboardCache.invalidate_admin_dashboard()
        
        return {
            'status': 'success',
            'records_updated': updated_count,
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def check_overdue_accounts():
    """
    Check for overdue accounts and send notifications.
    Runs daily.
    """
    try:
        today = timezone.now().date()
        
        # Find overdue records
        overdue = FinancialRecord.objects.filter(
            Q(due_date__lt=today) & 
            (Q(transport_balance__gt=0) | Q(tuition_balance__gt=0))
        ).exclude(status='overdue')
        
        notifications_sent = 0
        
        for record in overdue:
            record.status = 'overdue'
            record.save(update_fields=['status', 'updated_at'])
            
            msg = (
                f"Your fee record for {record.get_term_display()} {record.year} is overdue. "
                f"Due date: {record.due_date}. "
                f"Outstanding: {record.total_balance:.2f}. "
                f"Please settle payment immediately."
            )
            Notification.objects.create(
                recipient=record.student.user,
                title='URGENT: Fee Payment Overdue',
                message=msg
            )
            notifications_sent += 1
        
        # Invalidate cache
        DashboardCache.invalidate_admin_dashboard()
        
        return {
            'status': 'success',
            'overdue_accounts': overdue.count(),
            'notifications_sent': notifications_sent,
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def generate_monthly_financial_reports():
    """
    Generate monthly financial reports for all active months.
    Runs at month-end (28th-30th).
    """
    try:
        today = timezone.now().date()
        year = today.year
        month = today.month
        
        # Check if report already exists
        existing = MonthlyFinancialReport.objects.filter(year=year, month=month).exists()
        
        if existing:
            return {
                'status': 'skipped',
                'message': 'Report already generated for this month',
                'timestamp': timezone.now().isoformat()
            }
        
        # Calculate metrics
        income_qs = Income.objects.filter(date__year=year, date__month=month)
        expense_qs = Expense.objects.filter(date__year=year, date__month=month)
        
        total_income = income_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        school_fee_income = Payment.objects.filter(
            payment_date__year=year,
            payment_date__month=month,
            is_approved=True,
            status='approved',
            is_reversed=False,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_income += school_fee_income
        total_expenses = expense_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Create report
        report = MonthlyFinancialReport.objects.create(
            year=year,
            month=month,
        )
        
        # Notify admin
        for admin in StudentProfile.objects.filter(user__is_staff=True):
            msg = (
                f"Monthly financial report generated for {year}-{month:02d}. "
                f"Total income: {total_income:.2f}. "
                f"Total expenses: {total_expenses:.2f}. "
                f"Net profit/loss: {(total_income - total_expenses):.2f}"
            )
            Notification.objects.create(
                recipient=admin.user,
                title='Monthly Financial Report Generated',
                message=msg
            )
        
        return {
            'status': 'success',
            'report_id': report.id,
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def generate_student_financial_statements(student_id):
    """
    Generate financial statement for a specific student.
    Used when requested or periodically.
    
    Args:
        student_id: StudentProfile ID
    """
    try:
        student = StudentProfile.objects.get(id=student_id)
        
        # Get all records and payments
        records = student.financial_records.all().order_by('-year', 'term')
        payments = student.payments.filter(
            is_approved=True,
            status='approved',
            is_reversed=False,
        ).order_by('-payment_date')
        
        statement = {
            'student': str(student),
            'student_id': student.student_id,
            'generated_at': timezone.now().isoformat(),
            'records': [],
            'payments': [],
            'summary': FinancialService.get_student_financial_summary(student)
        }
        
        for record in records:
            statement['records'].append({
                'term': record.get_term_display(),
                'year': record.year,
                'due_date': str(record.due_date),
                'total_fee': float(record.total_fee),
                'total_paid': float(record.total_paid),
                'balance': float(record.total_balance),
                'status': record.status
            })
        
        for payment in payments:
            statement['payments'].append({
                'receipt': payment.receipt_number,
                'amount': float(payment.amount),
                'method': payment.get_payment_method_display(),
                'date': payment.payment_date.isoformat(),
                'record': str(payment.financial_record) if payment.financial_record else 'N/A'
            })
        
        return {
            'status': 'success',
            'student_id': student_id,
            'statement': statement,
            'timestamp': timezone.now().isoformat()
        }
    except StudentProfile.DoesNotExist:
        return {
            'status': 'error',
            'message': f'Student {student_id} not found',
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def refresh_dashboard_cache():
    """
    Refresh all dashboard caches.
    Runs periodically (e.g., every 5 minutes).
    """
    try:
        # Invalidate and regenerate main dashboard cache
        DashboardCache.invalidate_admin_dashboard()
        dashboard_data = DashboardCache.get_admin_financial_dashboard()
        
        # Invalidate all student caches to be regenerated on next access
        from apps.students.models import StudentProfile
        for student in StudentProfile.objects.filter(approved=True):
            DashboardCache.invalidate_student_dashboard(student.id)
        
        return {
            'status': 'success',
            'caches_refreshed': 'admin_dashboard + student_dashboards',
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def audit_financial_consistency():
    """
    Audit financial data for consistency issues.
    Runs daily to detect anomalies.
    """
    try:
        issues = []
        
        # Check for negative balances
        negative_balance = FinancialRecord.objects.filter(
            Q(transport_balance__lt=0) | Q(tuition_balance__lt=0)
        )
        if negative_balance.exists():
            issues.append({
                'type': 'NEGATIVE_BALANCE',
                'count': negative_balance.count(),
                'records': [str(r) for r in negative_balance[:5]]
            })
        
        # Check for orphaned payments
        orphaned_payments = Payment.objects.filter(
            financial_record__isnull=True,
            is_reversed=False
        )
        if orphaned_payments.exists():
            issues.append({
                'type': 'ORPHANED_PAYMENTS',
                'count': orphaned_payments.count(),
                'records': [p.receipt_number for p in orphaned_payments[:5]]
            })
        
        # Check for missing status updates
        inconsistent_status = []
        for record in FinancialRecord.objects.all()[:100]:  # Sample check
            record.update_status()
            if record.status == 'pending' and record.total_balance == 0:
                inconsistent_status.append(str(record))
        
        if inconsistent_status:
            issues.append({
                'type': 'INCONSISTENT_STATUS',
                'count': len(inconsistent_status),
                'records': inconsistent_status
            })
        
        # Log issues
        if issues:
            for admin in StudentProfile.objects.filter(user__is_staff=True):
                msg = f"Financial consistency audit found {len(issues)} issue(s):\n"
                for issue in issues:
                    msg += f"\n- {issue['type']}: {issue['count']} issues"
                Notification.objects.create(
                    recipient=admin.user,
                    title='Financial Audit Alert',
                    message=msg
                )
        
        return {
            'status': 'success',
            'issues_found': len(issues),
            'details': issues,
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }


# Scheduled tasks configuration in settings.py should include:
"""
CELERY_BEAT_SCHEDULE = {
    'recalculate-financial-status': {
        'task': 'apps.finance.tasks.recalculate_financial_status',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
    },
    'check-overdue-accounts': {
        'task': 'apps.finance.tasks.check_overdue_accounts',
        'schedule': crontab(minute=0, hour=9),  # Daily at 9 AM
    },
    'generate-monthly-reports': {
        'task': 'apps.finance.tasks.generate_monthly_financial_reports',
        'schedule': crontab(day_of_month='28,29,30'),  # Near month-end
    },
    'refresh-dashboard-cache': {
        'task': 'apps.finance.tasks.refresh_dashboard_cache',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'audit-financial-consistency': {
        'task': 'apps.finance.tasks.audit_financial_consistency',
        'schedule': crontab(minute=0, hour=0),  # Daily at midnight
    },
}
"""
