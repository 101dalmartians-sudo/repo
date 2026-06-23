"""
Academic Services for Aspire Academy Portal

Handles grade entry, calculations, and synchronization of academic data
across student profiles, performance tracking, and admin analytics.
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, F, Sum, Avg, Count
from apps.grades.models import Grade
from apps.students.models import StudentProfile, ExamResult, ExamSchedule
from apps.notifications.models import Notification
from django.contrib.auth.models import User


class AcademicService:
    """
    Centralized service for academic operations.
    
    Ensures:
    - Accurate grade calculations
    - Cambridge grading consistency
    - Student performance tracking
    - Admin analytics updates
    - Notification creation
    """
    
    @staticmethod
    @transaction.atomic
    def create_or_update_grade(student, subject, percentage, term, user=None):
        """
        Create or update a grade for a student.
        
        Args:
            student: StudentProfile instance
            subject: Subject name
            percentage: Grade percentage
            term: Term identifier
            user: User creating/updating (for audit)
            
        Returns:
            dict with result status and grade object
        """
        try:
            # Validate percentage
            if not (0 <= float(percentage) <= 100):
                return {
                    'success': False,
                    'message': 'Percentage must be between 0 and 100',
                    'status_code': 400
                }
            
            # Get or create grade
            grade, created = Grade.objects.get_or_create(
                student=student,
                subject=subject,
                term=term,
                defaults={'percentage': Decimal(str(percentage))}
            )
            
            if not created:
                grade.percentage = Decimal(str(percentage))
            
            # Cambridge grade is calculated in save()
            grade.save()
            
            # Invalidate caches
            AcademicService._invalidate_student_academic_cache(student)
            AcademicService._invalidate_admin_academic_cache()
            
            # Create notification if first grade
            if created:
                AcademicService._notify_grade_recorded(student, grade)
            
            return {
                'success': True,
                'message': 'Grade recorded successfully',
                'grade': grade,
                'created': created,
                'cambridge_grade': grade.cambridge_letter_grade,
                'status_code': 200
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error recording grade: {str(e)}',
                'status_code': 500
            }
    
    @staticmethod
    @transaction.atomic
    def delete_grade(grade, user=None):
        """
        Delete a grade and synchronize dependent data.
        
        Args:
            grade: Grade instance
            user: User deleting (for audit)
            
        Returns:
            dict with result status
        """
        try:
            student = grade.student
            subject = grade.subject
            term = grade.term
            
            grade.delete()
            
            # Invalidate caches
            AcademicService._invalidate_student_academic_cache(student)
            AcademicService._invalidate_admin_academic_cache()
            
            # Notify student
            msg = f"Grade for {subject} ({term}) has been removed from your record."
            Notification.objects.create(
                recipient=student.user,
                title='Grade Removed',
                message=msg
            )
            
            return {
                'success': True,
                'message': 'Grade deleted successfully',
                'status_code': 200
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error deleting grade: {str(e)}',
                'status_code': 500
            }
    
    @staticmethod
    def get_student_academic_summary(student):
        """
        Get comprehensive academic summary for a student.
        
        Args:
            student: StudentProfile instance
            
        Returns:
            dict with academic metrics
        """
        grades = Grade.objects.filter(student=student).order_by('term', 'subject')
        
        if not grades.exists():
            return {
                'total_subjects': 0,
                'average_percentage': Decimal('0.00'),
                'highest_grade': None,
                'lowest_grade': None,
                'grades_by_term': {},
                'status': 'no_grades'
            }
        
        # Overall metrics
        avg_percentage = grades.aggregate(avg=Avg('percentage'))['avg'] or Decimal('0.00')
        highest = grades.order_by('-percentage').first()
        lowest = grades.order_by('percentage').first()
        
        # Group by term
        grades_by_term = {}
        for grade in grades:
            if grade.term not in grades_by_term:
                grades_by_term[grade.term] = {
                    'grades': [],
                    'average': Decimal('0.00'),
                    'grade_count': 0
                }
            grades_by_term[grade.term]['grades'].append({
                'subject': grade.subject,
                'percentage': float(grade.percentage),
                'cambridge_grade': grade.cambridge_letter_grade
            })
        
        # Calculate term averages
        for term, data in grades_by_term.items():
            if data['grades']:
                avg = sum(g['percentage'] for g in data['grades']) / len(data['grades'])
                data['average'] = Decimal(str(avg))
                data['grade_count'] = len(data['grades'])
        
        # Determine performance status
        if avg_percentage >= 80:
            status = 'excellent'
        elif avg_percentage >= 70:
            status = 'good'
        elif avg_percentage >= 60:
            status = 'satisfactory'
        elif avg_percentage >= 50:
            status = 'needs_improvement'
        else:
            status = 'at_risk'
        
        return {
            'total_subjects': grades.count(),
            'average_percentage': float(avg_percentage),
            'highest_grade': {
                'subject': highest.subject,
                'percentage': float(highest.percentage),
                'grade': highest.cambridge_letter_grade
            } if highest else None,
            'lowest_grade': {
                'subject': lowest.subject,
                'percentage': float(lowest.percentage),
                'grade': lowest.cambridge_letter_grade
            } if lowest else None,
            'grades_by_term': grades_by_term,
            'status': status,
            'performance_rating': AcademicService._get_performance_rating(avg_percentage)
        }
    
    @staticmethod
    def get_admin_academic_dashboard():
        """
        Get academic dashboard summary for admin.
        
        Returns:
            dict with academic metrics and analytics
        """
        # Grade distribution
        grades = Grade.objects.all()
        total_grades = grades.count()
        
        if total_grades == 0:
            return {
                'total_grades': 0,
                'average_class_percentage': Decimal('0.00'),
                'grade_distribution': {},
                'students_by_performance': {},
                'subjects_summary': []
            }
        
        # Class average
        class_avg = grades.aggregate(avg=Avg('percentage'))['avg'] or Decimal('0.00')
        
        # Grade distribution (A*, A, B, C, D, U)
        grades_distribution = grades.values('cambridge_letter_grade').annotate(
            count=Count('id')
        ).order_by('-count')
        
        distribution = {
            'A*': grades.filter(cambridge_letter_grade='A*').count(),
            'A': grades.filter(cambridge_letter_grade='A').count(),
            'B': grades.filter(cambridge_letter_grade='B').count(),
            'C': grades.filter(cambridge_letter_grade='C').count(),
            'D': grades.filter(cambridge_letter_grade='D').count(),
            'U': grades.filter(cambridge_letter_grade='U').count(),
        }
        
        # Students by performance
        students_by_perf = {}
        for student in StudentProfile.objects.filter(approved=True):
            student_grades = Grade.objects.filter(student=student)
            if student_grades.exists():
                avg = student_grades.aggregate(avg=Avg('percentage'))['avg']
                if avg >= 80:
                    perf = 'Excellent'
                elif avg >= 70:
                    perf = 'Good'
                elif avg >= 60:
                    perf = 'Satisfactory'
                else:
                    perf = 'Needs Improvement'
                
                if perf not in students_by_perf:
                    students_by_perf[perf] = 0
                students_by_perf[perf] += 1
        
        # Subject summary
        subjects = grades.values('subject').annotate(
            avg_percentage=Avg('percentage'),
            count=Count('id')
        ).order_by('-avg_percentage')
        
        subjects_summary = [
            {
                'subject': s['subject'],
                'average': float(s['avg_percentage']),
                'grade_count': s['count']
            }
            for s in subjects[:10]
        ]
        
        return {
            'total_grades': total_grades,
            'average_class_percentage': float(class_avg),
            'grade_distribution': distribution,
            'students_by_performance': students_by_perf,
            'subjects_summary': subjects_summary,
            'total_students_graded': Grade.objects.values('student').distinct().count()
        }
    
    @staticmethod
    def process_exam_results(exam_schedule, user=None):
        """
        Process exam results and create grades.
        Should be called after exam scores are entered.
        
        Args:
            exam_schedule: ExamSchedule instance
            user: User processing (for audit)
            
        Returns:
            dict with processing status
        """
        try:
            results = exam_schedule.results.all()
            grades_created = 0
            
            for result in results:
                # Create or update grade from exam result
                percentage = (result.score / exam_schedule.max_score) * 100
                
                grade_result = AcademicService.create_or_update_grade(
                    result.student,
                    exam_schedule.subject,
                    percentage,
                    exam_schedule.term,
                    user
                )
                
                if grade_result['success']:
                    grades_created += 1
            
            # Mark exam as results released
            if grades_created > 0:
                exam_schedule.results_released = True
                exam_schedule.save()
                
                # Notify students
                for result in results:
                    msg = (
                        f"Your {exam_schedule.subject} exam results ({exam_schedule.term}) "
                        f"are now available. Score: {result.score}/{exam_schedule.max_score}"
                    )
                    Notification.objects.create(
                        recipient=result.student.user,
                        title='Exam Results Released',
                        message=msg
                    )
            
            return {
                'success': True,
                'message': f'Processed {grades_created} exam results',
                'grades_created': grades_created,
                'status_code': 200
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error processing exam results: {str(e)}',
                'status_code': 500
            }
    
    @staticmethod
    def get_performance_report(student, term=None):
        """
        Generate performance report for student.
        
        Args:
            student: StudentProfile instance
            term: Optional specific term
            
        Returns:
            dict with comprehensive performance data
        """
        grades_qs = Grade.objects.filter(student=student)
        
        if term:
            grades_qs = grades_qs.filter(term=term)
        
        if not grades_qs.exists():
            return {
                'student': str(student),
                'term': term,
                'generated_at': timezone.now().isoformat(),
                'message': 'No grades found'
            }
        
        total_subjects = grades_qs.count()
        avg_percentage = grades_qs.aggregate(avg=Avg('percentage'))['avg']
        
        grades_list = []
        for grade in grades_qs.order_by('-percentage'):
            grades_list.append({
                'subject': grade.subject,
                'percentage': float(grade.percentage),
                'cambridge_grade': grade.cambridge_letter_grade,
                'term': grade.term
            })
        
        return {
            'student': str(student),
            'student_id': student.student_id,
            'term': term,
            'total_subjects': total_subjects,
            'average_percentage': float(avg_percentage),
            'grades': grades_list,
            'performance_rating': AcademicService._get_performance_rating(avg_percentage),
            'generated_at': timezone.now().isoformat()
        }
    
    @staticmethod
    def _get_performance_rating(average_percentage):
        """Convert percentage to performance rating"""
        avg = float(average_percentage)
        if avg >= 90:
            return 'Outstanding'
        elif avg >= 80:
            return 'Excellent'
        elif avg >= 70:
            return 'Good'
        elif avg >= 60:
            return 'Satisfactory'
        elif avg >= 50:
            return 'Acceptable'
        else:
            return 'Below Standard'
    
    @staticmethod
    def _notify_grade_recorded(student, grade):
        """Notify student when first grade is recorded"""
        msg = (
            f"Your first grade has been recorded: "
            f"{grade.subject} - {grade.percentage}% ({grade.cambridge_letter_grade})"
        )
        Notification.objects.create(
            recipient=student.user,
            title='Grade Recorded',
            message=msg
        )
    
    @staticmethod
    def _invalidate_student_academic_cache(student):
        """Invalidate cached academic data for a student"""
        from django.core.cache import cache
        cache_keys = [
            f'student_academic_summary_{student.id}',
            f'student_performance_report_{student.id}',
            f'student_grades_{student.id}'
        ]
        cache.delete_many(cache_keys)
    
    @staticmethod
    def _invalidate_admin_academic_cache():
        """Invalidate admin academic dashboard cache"""
        from django.core.cache import cache
        cache.delete('admin_academic_dashboard')
        cache.delete('academic_analytics')
