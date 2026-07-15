"""
Academic Synchronization Signals

Handles automatic synchronization of academic data (grades, exam results)
across dashboards, performance tracking, and notifications.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.grades.models import Grade
from apps.students.models import ExamResult, ExamSchedule
from apps.students.synchronization import PortalSynchronizationService


@receiver(post_save, sender=Grade)
def synchronize_grade_creation(sender, instance, created, **kwargs):
    """
    Synchronize all affected areas when a grade is created or updated.
    
    Triggers:
    - Student academic dashboard update
    - Admin analytics update
    - Performance rating update
    - Cache invalidation
    - Notification creation (if first grade)
    """
    PortalSynchronizationService.synchronize_grade_change(
        instance,
        created=created,
    )


@receiver(post_delete, sender=Grade)
def synchronize_grade_deletion(sender, instance, **kwargs):
    """
    Synchronize all affected areas when a grade is deleted.
    
    Updates:
    - Student academic summary
    - Performance rating
    - Admin analytics
    - Cache invalidation
    """
    PortalSynchronizationService.synchronize_grade_change(
        instance,
        deleted=True,
    )


@receiver(post_save, sender=ExamResult)
def synchronize_exam_result_creation(sender, instance, created, **kwargs):
    """
    Synchronize when exam result is recorded.
    
    Note: Actual grade creation happens via process_exam_results()
    This signal handles cache invalidation and notifications.
    """
    PortalSynchronizationService.synchronize_exam_result(instance)


@receiver(post_save, sender=ExamSchedule)
def synchronize_exam_schedule_update(sender, instance, created, **kwargs):
    """
    Synchronize when exam schedule changes, especially results_released.
    """
    if created:
        PortalSynchronizationService.synchronize_exam_schedule(instance)
