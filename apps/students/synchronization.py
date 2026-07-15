from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.calendarapp.models import CalendarEvent
from apps.notifications.models import Notification
from apps.students.models import AuditLog, StudentProfile


class PortalSynchronizationService:
    """Single source of truth synchronization for teacher-driven operations."""

    @staticmethod
    def _invalidate_student_related_caches(student):
        from apps.grades.services import AcademicService
        from apps.reports.services import BiWeeklyReportService

        AcademicService._invalidate_student_academic_cache(student)
        AcademicService._invalidate_admin_academic_cache()
        BiWeeklyReportService._invalidate_caches(student)

    @staticmethod
    @transaction.atomic
    def synchronize_grade_change(grade, *, created=False, deleted=False, actor=None):
        student = grade.student
        PortalSynchronizationService._invalidate_student_related_caches(student)

        if created:
            def _notify_grade_created():
                Notification.objects.create(
                    recipient=student.user,
                    title='Grade Recorded',
                    message=(
                        f'New grade recorded: {grade.subject} ({grade.term}) '
                        f'- {grade.percentage}% ({grade.cambridge_letter_grade}).'
                    ),
                )

            transaction.on_commit(_notify_grade_created)

        if deleted:
            def _notify_grade_deleted():
                Notification.objects.create(
                    recipient=student.user,
                    title='Grade Removed',
                    message=f'Your grade for {grade.subject} ({grade.term}) has been removed.',
                )

            transaction.on_commit(_notify_grade_deleted)

        AuditLog.objects.create(
            actor=actor,
            action='Grade synchronized',
            model_name='grade',
            object_repr=str(grade),
            changes={
                'student_id': student.id,
                'subject': grade.subject,
                'term': grade.term,
                'created': created,
                'deleted': deleted,
            },
        )

    @staticmethod
    @transaction.atomic
    def synchronize_attendance_change(attendance_record, *, actor=None):
        student = attendance_record.student
        PortalSynchronizationService._invalidate_student_related_caches(student)

        AuditLog.objects.create(
            actor=actor,
            action='Attendance synchronized',
            model_name='attendancerecord',
            object_repr=str(attendance_record),
            changes={
                'student_id': student.id,
                'date': str(attendance_record.date),
                'status': attendance_record.status,
            },
        )

    @staticmethod
    @transaction.atomic
    def synchronize_exam_schedule(exam, *, actor=None):
        event_description = exam.instructions or exam.description
        CalendarEvent.objects.update_or_create(
            title=f'Exam: {exam.exam_name or exam.subject}',
            start_date=exam.exam_date,
            end_date=exam.exam_date,
            target_class=exam.target_class,
            defaults={
                'description': event_description,
                'is_global': False,
            },
        )

        recipients = StudentProfile.objects.filter(approved=True)
        if exam.target_class:
            recipients = recipients.filter(current_class__icontains=exam.target_class)

        def _notify_students():
            Notification.objects.bulk_create([
                Notification(
                    recipient=student.user,
                    title='Exam Scheduled',
                    message=(
                        f'{exam.exam_name or exam.subject} ({exam.subject}) is scheduled for '
                        f'{exam.exam_date}.'
                    ),
                )
                for student in recipients.select_related('user')
            ])

        transaction.on_commit(_notify_students)

        AuditLog.objects.create(
            actor=actor,
            action='Exam schedule synchronized',
            model_name='examschedule',
            object_repr=str(exam),
            changes={
                'exam_id': exam.id,
                'target_class': exam.target_class,
                'exam_date': str(exam.exam_date),
            },
        )

    @staticmethod
    @transaction.atomic
    def synchronize_exam_result(result, *, actor=None):
        from apps.grades.models import Grade

        max_score = Decimal(str(result.exam.max_score or 0))
        percentage = Decimal('0.00')
        if max_score > 0:
            percentage = (Decimal(str(result.score)) / max_score) * Decimal('100')

        grade, _ = Grade.objects.update_or_create(
            student=result.student,
            subject=result.exam.subject,
            term=result.exam.term,
            defaults={'percentage': percentage},
        )

        PortalSynchronizationService._invalidate_student_related_caches(result.student)

        def _notify_exam_result():
            Notification.objects.create(
                recipient=result.student.user,
                title='Exam Result Updated',
                message=(
                    f'{result.exam.exam_name or result.exam.subject} score recorded: '
                    f'{result.score}/{result.exam.max_score}. Grade sync completed.'
                ),
            )

        transaction.on_commit(_notify_exam_result)

        AuditLog.objects.create(
            actor=actor,
            action='Exam result synchronized',
            model_name='examresult',
            object_repr=str(result),
            changes={
                'exam_id': result.exam_id,
                'student_id': result.student_id,
                'grade_id': grade.id,
            },
        )

    @staticmethod
    @transaction.atomic
    def synchronize_assignment_upload(assignment, *, actor=None):
        recipients = StudentProfile.objects.filter(approved=True, current_class=assignment.target_class).select_related('user')

        def _notify_students():
            Notification.objects.bulk_create([
                Notification(
                    recipient=student.user,
                    title=f'New assignment: {assignment.title}',
                    message=(
                        f'New assignment "{assignment.title}" for {assignment.subject} '
                        f'has been posted for class {assignment.target_class}. '
                        f'Due {assignment.due_date:%Y-%m-%d %H:%M}.'
                    ),
                )
                for student in recipients
            ])

        transaction.on_commit(_notify_students)

        AuditLog.objects.create(
            actor=actor,
            action='Assignment synchronized',
            model_name='assignment',
            object_repr=str(assignment),
            changes={
                'assignment_id': assignment.id,
                'target_class': assignment.target_class,
            },
        )

    @staticmethod
    @transaction.atomic
    def synchronize_reporting_period(period, *, actor=None):
        from apps.reports.services import BiWeeklyReportService

        if period.is_published:
            recipients = StudentProfile.objects.filter(approved=True).select_related('user')

            def _notify_period_published():
                Notification.objects.bulk_create([
                    Notification(
                        recipient=student.user,
                        title='New Reporting Period Available',
                        message=(
                            f'{period.name} ({period.start_date} to {period.end_date}) '
                            f'is now available in your report history.'
                        ),
                    )
                    for student in recipients
                ])

            transaction.on_commit(_notify_period_published)

        for report in period.reports.select_related('student'):
            BiWeeklyReportService._invalidate_caches(report.student)

        AuditLog.objects.create(
            actor=actor,
            action='Reporting period synchronized',
            model_name='reportingperiod',
            object_repr=str(period),
            changes={
                'period_id': period.id,
                'status': period.status,
                'is_published': period.is_published,
                'published_on': str(period.publish_date or timezone.now().date()),
            },
        )

    @staticmethod
    @transaction.atomic
    def synchronize_report_publication(report, *, actor=None):
        from apps.reports.services import BiWeeklyReportService

        BiWeeklyReportService._update_period_analytics(report.period)
        BiWeeklyReportService._invalidate_caches(report.student)
        PortalSynchronizationService._invalidate_student_related_caches(report.student)

        AuditLog.objects.create(
            actor=actor,
            action='Report publication synchronized',
            model_name='biweeklyreport',
            object_repr=str(report),
            changes={
                'report_id': report.id,
                'status': report.status,
            },
        )
