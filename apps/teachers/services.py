from django.db import transaction
from django.utils import timezone

from apps.students.models import AttendanceRecord, AttendanceSession, AuditLog, ExamResult, ExamSchedule, StudentProfile


class TeacherWorkspaceService:
    @staticmethod
    @transaction.atomic
    def create_attendance_session(*, teacher, title, date, term, year, class_stream, subject=''):
        session = AttendanceSession.objects.create(
            title=title,
            teacher=teacher,
            date=date,
            term=term,
            year=year,
            class_stream=class_stream,
            subject=subject,
        )
        AuditLog.objects.create(
            actor=teacher,
            action='Attendance session created',
            model_name='attendancesession',
            object_repr=str(session),
            changes={'session_id': session.id, 'class_stream': class_stream},
        )
        return session

    @staticmethod
    @transaction.atomic
    def save_attendance(*, teacher, session, entries):
        updated_records = []
        for entry in entries:
            student = StudentProfile.objects.get(pk=entry['student_id'])
            record, _ = AttendanceRecord.objects.update_or_create(
                student=student,
                term=session.term,
                year=session.year,
                date=session.date,
                defaults={
                    'status': entry['status'],
                    'note': entry.get('note', ''),
                    'session': session,
                    'recorded_by': teacher,
                },
            )
            updated_records.append(record)

        AuditLog.objects.create(
            actor=teacher,
            action='Attendance batch updated',
            model_name='attendancerecord',
            object_repr=f'Session #{session.id}',
            changes={'records': len(updated_records)},
        )
        return updated_records

    @staticmethod
    @transaction.atomic
    def create_exam(*, teacher, exam_name, subject, class_stream, term, year, exam_date, instructions=''):
        exam = ExamSchedule.objects.create(
            exam_name=exam_name,
            subject=subject,
            target_class=class_stream,
            term=term,
            year=year,
            exam_date=exam_date,
            instructions=instructions,
            description=instructions,
            created_by=teacher,
            published_at=timezone.now(),
        )

        AuditLog.objects.create(
            actor=teacher,
            action='Exam scheduled',
            model_name='examschedule',
            object_repr=str(exam),
            changes={'exam_id': exam.id, 'class_stream': exam.target_class},
        )
        return exam

    @staticmethod
    @transaction.atomic
    def save_exam_results(*, teacher, exam, entries):
        updated = []
        for entry in entries:
            student = StudentProfile.objects.get(pk=entry['student_id'])
            result, _ = ExamResult.objects.update_or_create(
                exam=exam,
                student=student,
                defaults={
                    'score': entry['score'],
                    'comments': entry.get('comments', ''),
                    'graded_by': teacher,
                },
            )
            updated.append(result)

        AuditLog.objects.create(
            actor=teacher,
            action='Exam results updated',
            model_name='examresult',
            object_repr=str(exam),
            changes={'exam_id': exam.id, 'results': len(updated)},
        )
        return updated
