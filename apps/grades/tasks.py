"""
Academic Background Tasks for Celery

Handles periodic synchronization of academic data, performance report generation,
and analytics updates.
"""

from celery import shared_task
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from apps.grades.models import Grade
from apps.students.models import StudentProfile, ExamSchedule, ExamResult, AuditLog
from apps.notifications.models import Notification
from apps.grades.services import AcademicService


@shared_task
def calculate_class_performance():
    """
    Calculate class-wide performance metrics.
    Runs daily to track academic trends.
    """
    try:
        grades = Grade.objects.all()
        
        if not grades.exists():
            return {
                'status': 'skipped',
                'message': 'No grades to calculate',
                'timestamp': timezone.now().isoformat()
            }
        
        # Class statistics
        avg_percentage = grades.aggregate(avg=Avg('percentage'))['avg']
        total_grades = grades.count()
        unique_students = Grade.objects.values('student').distinct().count()
        
        # Grade distribution
        a_star = grades.filter(cambridge_letter_grade='A*').count()
        a = grades.filter(cambridge_letter_grade='A').count()
        b = grades.filter(cambridge_letter_grade='B').count()
        c = grades.filter(cambridge_letter_grade='C').count()
        d = grades.filter(cambridge_letter_grade='D').count()
        u = grades.filter(cambridge_letter_grade='U').count()
        
        # Performance categories
        excellent = Grade.objects.filter(percentage__gte=80).count()
        good = Grade.objects.filter(percentage__gte=70, percentage__lt=80).count()
        satisfactory = Grade.objects.filter(percentage__gte=60, percentage__lt=70).count()
        needs_improvement = Grade.objects.filter(percentage__lt=60).count()
        
        result = {
            'status': 'success',
            'class_average': float(avg_percentage),
            'total_grades': total_grades,
            'unique_students': unique_students,
            'grade_distribution': {
                'A*': a_star,
                'A': a,
                'B': b,
                'C': c,
                'D': d,
                'U': u,
            },
            'performance_categories': {
                'Excellent (80+)': excellent,
                'Good (70-79)': good,
                'Satisfactory (60-69)': satisfactory,
                'Needs Improvement (<60)': needs_improvement
            },
            'timestamp': timezone.now().isoformat()
        }
        
        # Log for admin view
        AuditLog.objects.create(
            actor=None,
            action='Class performance calculated',
            model_name='grade',
            object_repr=f'Class avg: {avg_percentage:.2f}%',
            changes=result
        )
        
        return result
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def identify_at_risk_students():
    """
    Identify students with below-average performance.
    Runs weekly to flag students needing intervention.
    """
    try:
        low_performers = []
        
        # Find students with average < 60%
        for student in StudentProfile.objects.filter(approved=True):
            summary = AcademicService.get_student_academic_summary(student)
            
            if summary['status'] in ['needs_improvement', 'at_risk']:
                low_performers.append({
                    'student': str(student),
                    'student_id': student.student_id,
                    'average': summary['average_percentage'],
                    'status': summary['status']
                })
                
                # Send notification to student
                if summary['average_percentage'] < 50:
                    msg = (
                        f"Your academic performance requires immediate attention. "
                        f"Current average: {summary['average_percentage']:.1f}%. "
                        f"Please consult with your teachers for support."
                    )
                    Notification.objects.create(
                        recipient=student.user,
                        title='Academic Performance Alert',
                        message=msg
                    )
                    
                    # Also notify parent/guardian (admin)
                    for admin in StudentProfile.objects.filter(user__is_staff=True):
                        admin_msg = (
                            f"{student.user.get_full_name()} ({student.student_id}) "
                            f"has low academic performance: {summary['average_percentage']:.1f}%"
                        )
                        Notification.objects.create(
                            recipient=admin.user,
                            title='Student Performance Alert',
                            message=admin_msg
                        )
        
        return {
            'status': 'success',
            'at_risk_count': len(low_performers),
            'students': low_performers,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def recognize_high_achievers():
    """
    Identify and recognize high-performing students.
    Runs weekly for motivational purposes.
    """
    try:
        high_achievers = []
        
        # Find students with average >= 85%
        for student in StudentProfile.objects.filter(approved=True):
            summary = AcademicService.get_student_academic_summary(student)
            
            if summary['status'] == 'excellent' and summary['average_percentage'] >= 85:
                high_achievers.append({
                    'student': str(student),
                    'student_id': student.student_id,
                    'average': summary['average_percentage'],
                })
                
                # Send congratulatory notification
                msg = (
                    f"Congratulations! You are an excellent performer with "
                    f"an average of {summary['average_percentage']:.1f}%. "
                    f"Keep up the outstanding work!"
                )
                Notification.objects.create(
                    recipient=student.user,
                    title='Excellent Academic Performance',
                    message=msg
                )
        
        return {
            'status': 'success',
            'high_achievers_count': len(high_achievers),
            'students': high_achievers,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def generate_term_performance_reports():
    """
    Generate comprehensive term performance reports.
    Runs at term-end (manual trigger recommended).
    """
    try:
        reports_generated = 0
        
        # Generate for all approved students
        for student in StudentProfile.objects.filter(approved=True):
            report = AcademicService.get_performance_report(student)
            
            if report.get('total_subjects', 0) > 0:
                # Store report info for admin access
                AuditLog.objects.create(
                    actor=None,
                    action='Term performance report generated',
                    model_name='grade',
                    object_repr=f"{student.student_id} - Avg: {report['average_percentage']:.1f}%",
                    changes=report
                )
                reports_generated += 1
                
                # Send to student
                msg = (
                    f"Your term performance report is ready: "
                    f"Average: {report['average_percentage']:.1f}% "
                    f"({report['performance_rating']}). "
                    f"Subjects: {report['total_subjects']}"
                )
                Notification.objects.create(
                    recipient=student.user,
                    title='Term Performance Report',
                    message=msg
                )
        
        return {
            'status': 'success',
            'reports_generated': reports_generated,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def notify_exam_approaching(days_ahead=7):
    """
    Notify students of upcoming exams.
    
    Args:
        days_ahead: Number of days to look ahead
    """
    try:
        from datetime import timedelta
        
        upcoming_date = timezone.now().date() + timedelta(days=days_ahead)
        
        upcoming_exams = ExamSchedule.objects.filter(
            exam_date=upcoming_date,
            results_released=False
        )
        
        notifications_sent = 0
        
        for exam in upcoming_exams:
            # Notify all students in this class
            students = StudentProfile.objects.filter(current_class__icontains=exam.term[:5])
            
            for student in students:
                msg = (
                    f"Exam reminder: {exam.subject} exam on {exam.exam_date} "
                    f"({exam.term}). Make sure to prepare!"
                )
                Notification.objects.create(
                    recipient=student.user,
                    title='Exam Reminder',
                    message=msg
                )
                notifications_sent += 1
        
        return {
            'status': 'success',
            'exams_found': upcoming_exams.count(),
            'notifications_sent': notifications_sent,
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
    ...existing tasks...
    
    'calculate-class-performance': {
        'task': 'apps.grades.tasks.calculate_class_performance',
        'schedule': crontab(minute=0, hour=23),  # Daily at 11 PM
    },
    'identify-at-risk-students': {
        'task': 'apps.grades.tasks.identify_at_risk_students',
        'schedule': crontab(day_of_week=0, hour=8),  # Weekly Monday at 8 AM
    },
    'recognize-high-achievers': {
        'task': 'apps.grades.tasks.recognize_high_achievers',
        'schedule': crontab(day_of_week=5, hour=10),  # Weekly Friday at 10 AM
    },
    'generate-term-reports': {
        'task': 'apps.grades.tasks.generate_term_performance_reports',
        'schedule': crontab(day_of_month='28,29,30'),  # Near term-end
    },
    'notify-exam-approaching': {
        'task': 'apps.grades.tasks.notify_exam_approaching',
        'schedule': crontab(minute=0, hour=7),  # Daily at 7 AM
    },
}
"""
