"""
Academic Synchronization Signals

Handles automatic synchronization of academic data (grades, exam results)
across dashboards, performance tracking, and notifications.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction

from apps.grades.models import Grade
from apps.students.models import ExamResult, ExamSchedule
from apps.grades.services import AcademicService


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
    from django.core.cache import cache
    
    # Invalidate caches
    AcademicService._invalidate_student_academic_cache(instance.student)
    AcademicService._invalidate_admin_academic_cache()
    
    if created:
        # Notify student of first grade
        AcademicService._notify_grade_recorded(instance.student, instance)


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
    from apps.notifications.models import Notification
    from django.core.cache import cache
    
    student = instance.student
    
    # Notify student
    msg = f"Your grade for {instance.subject} ({instance.term}) has been removed."
    Notification.objects.create(
        recipient=student.user,
        title='Grade Removed',
        message=msg
    )
    
    # Invalidate caches
    AcademicService._invalidate_student_academic_cache(student)
    AcademicService._invalidate_admin_academic_cache()


@receiver(post_save, sender=ExamResult)
def synchronize_exam_result_creation(sender, instance, created, **kwargs):
    """
    Synchronize when exam result is recorded.
    
    Note: Actual grade creation happens via process_exam_results()
    This signal handles cache invalidation and notifications.
    """
    if created:
        from apps.notifications.models import Notification
        
        # Notify student that result was recorded (before release)
        msg = (
            f"Your {instance.exam.subject} exam has been scored. "
            f"Score: {instance.score}/{instance.exam.max_score}. "
            f"Results will be released soon."
        )
        Notification.objects.create(
            recipient=instance.student.user,
            title='Exam Scored',
            message=msg
        )
        
        # Invalidate caches
        AcademicService._invalidate_student_academic_cache(instance.student)
        AcademicService._invalidate_admin_academic_cache()


@receiver(post_save, sender=ExamSchedule)
def synchronize_exam_schedule_update(sender, instance, created, **kwargs):
    """
    Synchronize when exam schedule changes, especially results_released.
    """
    if created:
        from apps.notifications.models import Notification
        
        # Notify students about new exam
        from apps.students.models import StudentProfile
        students = StudentProfile.objects.filter(current_class=instance.term[:5])  # Approximate
        
        for student in students:
            msg = (
                f"New exam scheduled: {instance.subject} "
                f"on {instance.exam_date} ({instance.term})"
            )
            Notification.objects.create(
                recipient=student.user,
                title='Exam Scheduled',
                message=msg
            )
    
    elif instance.results_released:
        # Results just released
        from apps.notifications.models import Notification
        
        for result in instance.results.all():
            msg = (
                f"Your {instance.subject} exam results are now available! "
                f"Score: {result.score}/{instance.max_score}"
            )
            Notification.objects.create(
                recipient=result.student.user,
                title='Exam Results Released',
                message=msg
            )
