from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from datetime import timedelta

from apps.students.models import StudentProfile, ExamSchedule, ExamResult
from apps.notifications.models import Notification
from apps.grades.services import AcademicService
from .models import Grade


class GradeModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='student1', password='password123')
        self.student_profile = StudentProfile.objects.create(
            user=user,
            student_id='S001',
            current_class='Form 1'
        )

    def test_grade_calculation_a_star(self):
        grade = Grade(percentage=85, subject='Math', term='Term 1', student=self.student_profile)
        self.assertEqual(grade.calculate_cambridge_grade(grade.percentage), 'A*')


# ============================================================================
# Academic Synchronization Tests
# ============================================================================


class AcademicServiceTests(TestCase):
    """Tests for AcademicService"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user('student', 'student@example.com', 'password')
        self.student = StudentProfile.objects.create(
            user=self.user,
            student_id='STU001',
            current_class='Form 1',
            approved=True
        )
        
        self.admin = User.objects.create_user('admin', 'admin@example.com', 'password')
        self.admin.is_staff = True
        self.admin.save()
    
    def test_create_grade(self):
        """Test grade creation through service"""
        result = AcademicService.create_or_update_grade(
            self.student,
            'Mathematics',
            Decimal('85.5'),
            'term1'
        )
        
        self.assertTrue(result['success'])
        self.assertTrue(result['created'])
        self.assertEqual(result['cambridge_grade'], 'A*')
        
        # Verify grade exists
        grade = Grade.objects.get(student=self.student, subject='Mathematics')
        self.assertEqual(float(grade.percentage), 85.5)
    
    def test_update_grade(self):
        """Test updating existing grade"""
        # Create first
        AcademicService.create_or_update_grade(
            self.student,
            'Mathematics',
            Decimal('75.0'),
            'term1'
        )
        
        # Update
        result = AcademicService.create_or_update_grade(
            self.student,
            'Mathematics',
            Decimal('88.0'),
            'term1'
        )
        
        self.assertTrue(result['success'])
        self.assertFalse(result['created'])
        
        # Verify update
        grade = Grade.objects.get(student=self.student, subject='Mathematics')
        self.assertEqual(float(grade.percentage), 88.0)
    
    def test_invalid_percentage(self):
        """Test that invalid percentages are rejected"""
        result = AcademicService.create_or_update_grade(
            self.student,
            'Mathematics',
            Decimal('150.0'),  # Over 100%
            'term1'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('0 and 100', result['message'])
    
    def test_delete_grade(self):
        """Test grade deletion"""
        # Create grade
        grade = Grade.objects.create(
            student=self.student,
            subject='Mathematics',
            percentage=Decimal('85.0'),
            cambridge_letter_grade='A*',
            term='term1'
        )
        
        # Delete through service
        result = AcademicService.delete_grade(grade)
        
        self.assertTrue(result['success'])
        self.assertFalse(Grade.objects.filter(id=grade.id).exists())
        
        # Check notification
        notification = Notification.objects.filter(
            recipient=self.user,
            title__icontains='Removed',
        ).order_by('-id').first()
        self.assertIsNotNone(notification)
        self.assertIn('Removed', notification.title)
    
    def test_get_student_academic_summary(self):
        """Test student academic summary generation"""
        # Create multiple grades
        Grade.objects.create(
            student=self.student,
            subject='Mathematics',
            percentage=Decimal('90.0'),
            cambridge_letter_grade='A*',
            term='term1'
        )
        Grade.objects.create(
            student=self.student,
            subject='English',
            percentage=Decimal('80.0'),
            cambridge_letter_grade='A',
            term='term1'
        )
        Grade.objects.create(
            student=self.student,
            subject='Science',
            percentage=Decimal('70.0'),
            cambridge_letter_grade='B',
            term='term2'
        )
        
        summary = AcademicService.get_student_academic_summary(self.student)
        
        self.assertEqual(summary['total_subjects'], 3)
        self.assertAlmostEqual(summary['average_percentage'], 80.0, places=1)
        self.assertEqual(summary['highest_grade']['subject'], 'Mathematics')
        self.assertEqual(summary['lowest_grade']['subject'], 'Science')
        self.assertEqual(summary['status'], 'excellent')
    
    def test_no_grades_summary(self):
        """Test summary when student has no grades"""
        summary = AcademicService.get_student_academic_summary(self.student)
        
        self.assertEqual(summary['total_subjects'], 0)
        self.assertEqual(summary['average_percentage'], 0)
        self.assertEqual(summary['status'], 'no_grades')
    
    def test_get_admin_academic_dashboard(self):
        """Test admin academic dashboard"""
        # Create grades for multiple students
        user2 = User.objects.create_user('student2', 'student2@example.com', 'password')
        student2 = StudentProfile.objects.create(
            user=user2,
            student_id='STU002',
            current_class='Form 2',
            approved=True
        )
        
        # Student 1 grades
        Grade.objects.create(
            student=self.student,
            subject='Mathematics',
            percentage=Decimal('90.0'),
            cambridge_letter_grade='A*',
            term='term1'
        )
        
        # Student 2 grades
        Grade.objects.create(
            student=student2,
            subject='Mathematics',
            percentage=Decimal('70.0'),
            cambridge_letter_grade='B',
            term='term1'
        )
        
        dashboard = AcademicService.get_admin_academic_dashboard()
        
        self.assertEqual(dashboard['total_grades'], 2)
        self.assertEqual(dashboard['total_students_graded'], 2)
        self.assertGreater(len(dashboard['subjects_summary']), 0)
        self.assertEqual(dashboard['grade_distribution']['A*'], 1)
        self.assertEqual(dashboard['grade_distribution']['A'], 1)


class GradeSignalTests(TransactionTestCase):
    """Tests for grade synchronization signals"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user('student', 'student@example.com', 'password')
        self.student = StudentProfile.objects.create(
            user=self.user,
            student_id='STU001',
            current_class='Form 1',
            approved=True
        )
    
    def test_grade_creation_notification(self):
        """Test that grade creation triggers notification"""
        grade = Grade.objects.create(
            student=self.student,
            subject='Mathematics',
            percentage=Decimal('85.0'),
            cambridge_letter_grade='A*',
            term='term1'
        )
        
        # Check notification was created
        notification = Notification.objects.filter(recipient=self.user).first()
        self.assertIsNotNone(notification)
        self.assertIn('Grade', notification.title)
    
    def test_grade_deletion_notification(self):
        """Test that grade deletion triggers notification"""
        grade = Grade.objects.create(
            student=self.student,
            subject='Mathematics',
            percentage=Decimal('85.0'),
            cambridge_letter_grade='A*',
            term='term1'
        )
        
        grade_id = grade.id
        grade.delete()
        
        # Check removal notification
        notification = Notification.objects.filter(
            recipient=self.user,
            title__icontains='Removed'
        ).first()
        self.assertIsNotNone(notification)


class ExamResultSynchronizationTests(TestCase):
    """Tests for exam result synchronization"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user('student', 'student@example.com', 'password')
        self.student = StudentProfile.objects.create(
            user=self.user,
            student_id='STU001',
            current_class='Form 1',
            approved=True
        )
        
        self.exam = ExamSchedule.objects.create(
            subject='Mathematics',
            term='term1',
            year=2024,
            exam_date=timezone.now().date() - timedelta(days=1),
            max_score=Decimal('100.00')
        )
    
    def test_process_exam_results(self):
        """Test processing exam results to grades"""
        # Create exam result
        result = ExamResult.objects.create(
            exam=self.exam,
            student=self.student,
            score=Decimal('85.00')
        )
        
        # Process results
        process_result = AcademicService.process_exam_results(self.exam)
        
        self.assertTrue(process_result['success'])
        self.assertEqual(process_result['grades_created'], 1)
        
        # Check grade was created
        grade = Grade.objects.filter(
            student=self.student,
            subject='Mathematics'
        ).first()
        self.assertIsNotNone(grade)
        self.assertEqual(float(grade.percentage), 85.0)


class PerformanceReportTests(TestCase):
    """Tests for performance report generation"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user('student', 'student@example.com', 'password')
        self.student = StudentProfile.objects.create(
            user=self.user,
            student_id='STU001',
            current_class='Form 1',
            approved=True
        )
        
        # Create multiple grades
        Grade.objects.create(
            student=self.student,
            subject='Mathematics',
            percentage=Decimal('85.0'),
            cambridge_letter_grade='A*',
            term='term1'
        )
        Grade.objects.create(
            student=self.student,
            subject='English',
            percentage=Decimal('90.0'),
            cambridge_letter_grade='A*',
            term='term1'
        )
    
    def test_performance_report_generation(self):
        """Test performance report generation"""
        report = AcademicService.get_performance_report(self.student, 'term1')
        
        self.assertEqual(report['student'], str(self.student))
        self.assertEqual(report['total_subjects'], 2)
        self.assertAlmostEqual(report['average_percentage'], 87.5, places=1)
        self.assertEqual(report['performance_rating'], 'Excellent')
        self.assertEqual(len(report['grades']), 2)
    
    def test_report_with_no_grades(self):
        """Test report generation when no grades exist"""
        user2 = User.objects.create_user('student2', 'student2@example.com', 'password')
        student2 = StudentProfile.objects.create(
            user=user2,
            student_id='STU002',
            current_class='Form 2',
            approved=True
        )
        
        report = AcademicService.get_performance_report(student2)
        
        self.assertIn('No grades', report['message'])

    def test_grade_calculation_c(self):
        self.assertEqual(Grade.calculate_cambridge_grade(52), 'C')
        self.assertEqual(Grade.calculate_cambridge_grade(49.9), 'D')

    def test_save_sets_letter_grade(self):
        grade = Grade(subject='Science', term='Term 2', percentage=76, student=self.student)
        grade.save()
        self.assertEqual(grade.cambridge_letter_grade, 'A')
