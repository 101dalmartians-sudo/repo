"""Financial Synchronization Signals."""

from django.db.models.deletion import ProtectedError
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver

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
    if kwargs.get('raw'):
        return

    if not instance.financial_record:
        return

    if instance.is_reversed:
        FinancialService.synchronize_financial_record(instance.financial_record)
        FinancialService._invalidate_student_cache(instance.student)
        FinancialService._invalidate_dashboard_cache()
        FinancialService._invalidate_payment_period_cache(instance.payment_date)
        return

    if created and instance.is_approved:
        FinancialService.process_payment(instance)
        return

    if not created:
        # Generic update/approval path: fully recompute from effective payments.
        FinancialService.synchronize_financial_record(instance.financial_record)
        FinancialService._invalidate_student_cache(instance.student)
        FinancialService._invalidate_dashboard_cache()
        FinancialService._invalidate_payment_period_cache(instance.payment_date)


@receiver(post_delete, sender=Payment)
def synchronize_payment_deletion(sender, instance, **kwargs):
    """
    Synchronize all affected areas when a payment is deleted.
    
    Reverses all balance changes and updates dependent records.
    """
    if instance.financial_record:
        FinancialService.synchronize_financial_record(instance.financial_record)
        FinancialService._invalidate_student_cache(instance.student)
        FinancialService._invalidate_dashboard_cache()
        FinancialService._invalidate_payment_period_cache(instance.payment_date)


@receiver(post_save, sender=FinancialRecord)
def synchronize_financial_record_update(sender, instance, created, **kwargs):
    """
    Synchronize all affected areas when a financial record is created or updated.
    
    Triggers:
    - Status calculation
    - Notification to student (if created)
    - Dashboard cache invalidation
    """
    if kwargs.get('raw'):
        return

    sync_update_fields = {
        'transport_paid',
        'tuition_paid',
        'transport_balance',
        'tuition_balance',
        'payment_count',
        'last_payment_date',
        'status',
        'updated_by',
        'updated_at',
    }
    update_fields = kwargs.get('update_fields')
    if update_fields and set(update_fields).issubset(sync_update_fields):
        FinancialService._invalidate_student_cache(instance.student)
        FinancialService._invalidate_dashboard_cache()
        return

    FinancialService.synchronize_financial_record(instance)
    
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
    # Check if there are any active payments
    if instance.payments.filter(is_approved=True, status='approved', is_reversed=False).exists():
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
