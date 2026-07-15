from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import AuditLog, AttendanceRecord, AttendanceSession, ExamResult, ExamSchedule, FinancialRecord, Payment
from .synchronization import PortalSynchronizationService


def create_audit_log(instance, action):
    AuditLog.objects.create(
        actor=None,
        action=action,
        model_name=instance._meta.model_name,
        object_repr=str(instance),
        changes={},
    )


@receiver(post_save, sender=FinancialRecord)
def record_financial_record_save(sender, instance, created, **kwargs):
    create_audit_log(instance, 'Created' if created else 'Updated')


@receiver(post_save, sender=Payment)
def record_payment_save(sender, instance, created, **kwargs):
    create_audit_log(instance, 'Payment created' if created else 'Payment updated')


@receiver(post_save, sender=AttendanceRecord)
def record_attendance_save(sender, instance, created, **kwargs):
    PortalSynchronizationService.synchronize_attendance_change(instance)
    create_audit_log(instance, 'Attendance recorded' if created else 'Attendance updated')


@receiver(post_save, sender=AttendanceSession)
def record_attendance_session_save(sender, instance, created, **kwargs):
    create_audit_log(instance, 'Attendance session created' if created else 'Attendance session updated')


@receiver(post_save, sender=ExamSchedule)
def record_exam_schedule_save(sender, instance, created, **kwargs):
    create_audit_log(instance, 'Exam scheduled' if created else 'Exam updated')


@receiver(post_save, sender=ExamResult)
def record_exam_result_save(sender, instance, created, **kwargs):
    create_audit_log(instance, 'Exam result created' if created else 'Exam result updated')


@receiver(post_delete, sender=FinancialRecord)
def record_financial_record_delete(sender, instance, **kwargs):
    create_audit_log(instance, 'Financial record deleted')


@receiver(post_delete, sender=Payment)
def record_payment_delete(sender, instance, **kwargs):
    create_audit_log(instance, 'Payment deleted')


@receiver(post_delete, sender=AttendanceRecord)
def record_attendance_delete(sender, instance, **kwargs):
    create_audit_log(instance, 'Attendance deleted')


@receiver(post_delete, sender=AttendanceSession)
def record_attendance_session_delete(sender, instance, **kwargs):
    create_audit_log(instance, 'Attendance session deleted')


@receiver(post_delete, sender=ExamSchedule)
def record_exam_schedule_delete(sender, instance, **kwargs):
    create_audit_log(instance, 'Exam schedule deleted')


@receiver(post_delete, sender=ExamResult)
def record_exam_result_delete(sender, instance, **kwargs):
    create_audit_log(instance, 'Exam result deleted')
