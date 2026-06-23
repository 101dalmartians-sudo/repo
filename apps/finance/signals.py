"""
Financial Synchronization Signals

Handles automatic synchronization of financial data across dashboards,
reports, and notifications whenever financial records change.
"""

from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.db import transaction
from decimal import Decimal
from django.utils import timezone

from apps.students.models import Payment, FinancialRecord
from apps.finance.services import FinancialService


@receiver(post_save, sender=Payment)
def synchronize_payment_creation(sender, instance, created, **kwargs):
    """
    Synchronize all affected areas when a payment is created or updated.
    
    Triggers:
    - FinancialRecord balance update
    - Status synchronization
    - Dashboard cache invalidation
    - Notification creation
    """
    if created and instance.is_approved and not instance.is_reversed:
        # New payment - process it
        FinancialService.process_payment(instance)
    elif not created and instance.is_approved and not instance.is_reversed:
        # Payment updated - reprocess if status changed to approved
        if instance.financial_record:
            FinancialService.process_payment(instance)


@receiver(post_delete, sender=Payment)
def synchronize_payment_deletion(sender, instance, **kwargs):
    """
    Synchronize all affected areas when a payment is deleted.
    
    Reverses all balance changes and updates dependent records.
    """
    if instance.financial_record and not instance.is_reversed:
        # Treat deletion as reversal
        FinancialService.reverse_payment(instance, None, 'Record deleted')


@receiver(post_save, sender=FinancialRecord)
def synchronize_financial_record_update(sender, instance, created, **kwargs):
    """
    Synchronize all affected areas when a financial record is created or updated.
    
    Triggers:
    - Status calculation
    - Notification to student (if created)
    - Dashboard cache invalidation
    """
    from django.core.cache import cache
    
    # Update status based on current balances
    instance.update_status()
    
    if created:
        # New record - notify student
        from apps.notifications.models import Notification
        msg = (
            f"New fee record created for {instance.get_term_display()} {instance.year}. "
            f"Total due: {instance.total_fee:.2f}. "
            f"Due date: {instance.due_date or 'Not set'}"
        )
        Notification.objects.create(
            recipient=instance.student.user,
            title='New Fee Record',
            message=msg
        )
    
    # Invalidate caches
    FinancialService._invalidate_student_cache(instance.student)
    FinancialService._invalidate_dashboard_cache()


@receiver(pre_delete, sender=FinancialRecord)
def synchronize_financial_record_deletion(sender, instance, **kwargs):
    """
    Prevent deletion of financial records that have payments.
    Synchronize if deletion is allowed.
    """
    from django.core.exceptions import ProtectedError
    
    # Check if there are any payments
    if instance.payments.filter(is_reversed=False).exists():
        # Don't allow deletion - this maintains data integrity
        raise ProtectedError(
            "Cannot delete financial record that has payments. "
            "Reverse the payments first.",
            instance
        )
    
    # Notify student of deletion
    from apps.notifications.models import Notification
    msg = f"Fee record for {instance.get_term_display()} {instance.year} has been deleted."
    Notification.objects.create(
        recipient=instance.student.user,
        title='Fee Record Deleted',
        message=msg
    )
    
    # Invalidate caches
    FinancialService._invalidate_student_cache(instance.student)
    FinancialService._invalidate_dashboard_cache()
