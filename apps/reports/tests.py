"""
Tests for Bi-Weekly Student Reporting System
"""

from decimal import Decimal
from django.contrib.auth.models import User, Group
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.students.models import StudentProfile
from apps.accounts.models import AdminProfile
from apps.teachers.models import TeacherProfile
from apps.grades.models import Grade
from apps.reports.models import (
    ReportingPeriod, ReportField, BiWeeklyReport, ReportingAnalytics
)
from apps.reports.services import BiWeeklyReportService


class ReportingPeriodTests(TestCase):
    """Tests for ReportingPeriod model"""
    
    def setUp(self):
        """Set up test data"""
        now = timezone.now()
        self.period = ReportingPeriod.objects.create(
            name="Week 1-2 Term 1",
            start_date=now.date(),
            end_date=(now + timedelta(days=14)).date(),
            term='term1',
            year=2026,
            submission_opens=now - timedelta(hours=1),
            submission_deadline=now + timedelta(days=7),
            approval_deadline=now + timedelta(days=14),
            status='open'
        )
    
    def test_is_open_for_submission(self):
        """Test submission window check"""
        self.assertTrue(self.period.is_open_for_submission())
    
    def test_can_be_approved(self):
        """Test approval window check"""
        self.assertTrue(self.period.can_be_approved())


class ReportFieldTests(TestCase):
    """Tests for ReportField model"""
    
    def setUp(self):
        """Set up test data"""
        self.field = ReportField.objects.create(
            name='Academic Performance',
            field_type='score',
            description='Student academic progress',
            order=1,
            is_required=True,
            is_active=True
        )
    
    def test_field_creation(self):
        """Test report field creation"""
        self.assertEqual(self.field.name, 'Academic Performance')
        self.assertEqual(self.field.field_type, 'score')
        self.assertTrue(self.field.is_active)


class BiWeeklyReportTests(TestCase):
    """Tests for BiWeeklyReport model"""
    
    def setUp(self):
        """Set up test data"""
        # Create users
        self.teacher_user = User.objects.create_user('teacher', 'teacher@example.com', 'password')
        self.admin_user = User.objects.create_user('admin', 'admin@example.com', 'password')
        self.student_user = User.objects.create_user('student', 'student@example.com', 'password')
        
        # Create student
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            student_id='STU001',
            current_class='Form 1',
            approved=True
        )
        
        # Create period
        now = timezone.now()
        self.period = ReportingPeriod.objects.create(
            name="Week 1-2 Term 1",
            start_date=now.date(),
            end_date=(now + timedelta(days=14)).date(),
            term='term1',
            year=2026,
            submission_opens=now - timedelta(hours=1),
            submission_deadline=now + timedelta(days=7),
            approval_deadline=now + timedelta(days=14),
            status='open'
        )
    
    def test_create_report(self):
        """Test creating a draft report"""
        report = BiWeeklyReport.objects.create(
            period=self.period,
            student=self.student,
            teacher=self.teacher_user,
            content={'academic': 'Good', 'behaviour': 'Excellent'},
            status='draft'
        )
        
        self.assertEqual(report.status, 'draft')
        self.assertEqual(report.teacher, self.teacher_user)
    
    def test_submit_report(self):
        """Test submitting a report for approval"""
        report = BiWeeklyReport.objects.create(
            period=self.period,
            student=self.student,
            teacher=self.teacher_user,
            content={'academic': 'Good'},
            status='draft'
        )
        
        report.submit(self.admin_user)
        
        self.assertEqual(report.status, 'submitted')
        self.assertIsNotNone(report.submitted_at)
        self.assertEqual(report.submitted_by, self.admin_user)
    
    def test_approve_report(self):
        """Test approving a report"""
        report = BiWeeklyReport.objects.create(
            period=self.period,
            student=self.student,
            teacher=self.teacher_user,
            content={'academic': 'Good'},
            status='submitted'
        )
        
        report.approve(self.admin_user, 'Looks good')
        
        self.assertEqual(report.status, 'approved')
        self.assertIsNotNone(report.approved_at)
        self.assertEqual(report.approved_by, self.admin_user)
    
    def test_publish_report(self):
        """Test publishing a report"""
        report = BiWeeklyReport.objects.create(
            period=self.period,
            student=self.student,
            teacher=self.teacher_user,
            content={'academic': 'Good'},
            status='approved'
        )
        
        report.publish()
        
        self.assertEqual(report.status, 'published')
        self.assertIsNotNone(report.published_at)
    
    def test_archive_report(self):
        """Test archiving a report"""
        report = BiWeeklyReport.objects.create(
            period=self.period,
            student=self.student,
            teacher=self.teacher_user,
            content={'academic': 'Good'},
            status='published'
        )
        
        report.archive()
        
        self.assertEqual(report.status, 'archived')


class BiWeeklyReportServiceTests(TestCase):
    """Tests for BiWeeklyReportService"""
    
    def setUp(self):
        """Set up test data"""
        # Create users
        self.teacher_user = User.objects.create_user('teacher', 'teacher@example.com', 'password')
        self.admin_user = User.objects.create_user('admin', 'admin@example.com', 'password')
        self.student_user = User.objects.create_user('student', 'student@example.com', 'password')
        
        # Create student
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            student_id='STU001',
            current_class='Form 1',
            approved=True
        )
        
        # Create period
        now = timezone.now()
        self.period = ReportingPeriod.objects.create(
            name="Week 1-2 Term 1",
            start_date=now.date(),
            end_date=(now + timedelta(days=14)).date(),
            term='term1',
            year=2026,
            submission_opens=now - timedelta(hours=1),
            submission_deadline=now + timedelta(days=7),
            approval_deadline=now + timedelta(days=14),
            status='open'
        )
    
    def test_create_report(self):
        """Test service creates report"""
        result = BiWeeklyReportService.create_report(
            self.period,
            self.student,
            self.teacher_user,
            {'academic': 'Good', 'behaviour': 'Excellent'}
        )
        
        self.assertTrue(result['success'])
        self.assertTrue(result['created'])
        
        # Verify report was created
        report = BiWeeklyReport.objects.get(period=self.period, student=self.student)
        self.assertEqual(report.status, 'draft')
    
    def test_submit_report(self):
        """Test service submits report"""
        # Create report
        result = BiWeeklyReportService.create_report(
            self.period,
            self.student,
            self.teacher_user,
            {'academic': 'Good'}
        )
        report = result['report']
        
        # Submit
        result = BiWeeklyReportService.submit_report(report, self.teacher_user)
        
        self.assertTrue(result['success'])
        report.refresh_from_db()
        self.assertEqual(report.status, 'submitted')
    
    def test_approve_report(self):
        """Test service approves report"""
        # Create and submit report
        report = BiWeeklyReport.objects.create(
            period=self.period,
            student=self.student,
            teacher=self.teacher_user,
            content={'academic': 'Good'},
            status='submitted'
        )
        
        # Approve
        result = BiWeeklyReportService.approve_report(report, self.admin_user, 'Good work')
        
        self.assertTrue(result['success'])
        report.refresh_from_db()
        self.assertEqual(report.status, 'approved')
    
    def test_publish_report(self):
        """Test service publishes report"""
        # Create and approve report
        report = BiWeeklyReport.objects.create(
            period=self.period,
            student=self.student,
            teacher=self.teacher_user,
            content={'academic': 'Good'},
            status='approved'
        )
        
        # Publish
        result = BiWeeklyReportService.publish_report(report)
        
        self.assertTrue(result['success'])
        report.refresh_from_db()
        self.assertEqual(report.status, 'published')
    
    def test_get_student_reports(self):
        """Test retrieving student reports"""
        # Create reports
        BiWeeklyReport.objects.create(
            period=self.period,
            student=self.student,
            teacher=self.teacher_user,
            content={'academic': 'Good'},
            status='published'
        )
        
        # Get reports
        reports = BiWeeklyReportService.get_student_reports(self.student)
        
        self.assertEqual(reports['total_bi_weekly'], 1)
        self.assertEqual(len(reports['bi_weekly_reports']), 1)
    
    def test_get_period_report_status(self):
        """Test getting period reporting status"""
        # Create multiple reports with different statuses
        BiWeeklyReport.objects.create(
            period=self.period,
            student=self.student,
            teacher=self.teacher_user,
            content={'academic': 'Good'},
            status='draft'
        )
        
        # Create another student
        student2_user = User.objects.create_user('student2', 'student2@example.com', 'password')
        student2 = StudentProfile.objects.create(
            user=student2_user,
            student_id='STU002',
            current_class='Form 1',
            approved=True
        )
        
        BiWeeklyReport.objects.create(
            period=self.period,
            student=student2,
            teacher=self.teacher_user,
            content={'academic': 'Excellent'},
            status='published'
        )
        
        # Get status
        status = BiWeeklyReportService.get_period_report_status(self.period)
        
        self.assertEqual(status['total_reports'], 2)
        self.assertEqual(status['draft_count'], 1)
        self.assertEqual(status['published_count'], 1)


class ReportingAnalyticsTests(TestCase):
    """Tests for ReportingAnalytics model"""
    
    def setUp(self):
        """Set up test data"""
        now = timezone.now()
        self.period = ReportingPeriod.objects.create(
            name="Week 1-2 Term 1",
            start_date=now.date(),
            end_date=(now + timedelta(days=14)).date(),
            term='term1',
            year=2026,
            submission_opens=now - timedelta(hours=1),
            submission_deadline=now + timedelta(days=7),
            approval_deadline=now + timedelta(days=14),
            status='open'
        )
        
        self.analytics = ReportingAnalytics.objects.create(
            period=self.period,
            total_students=100,
            reports_created=100,
            reports_submitted=85,
            reports_approved=70,
            reports_published=65,
            completion_percentage=Decimal('65.00')
        )
    
    def test_analytics_creation(self):
        """Test analytics creation"""
        self.assertEqual(self.analytics.total_students, 100)
        self.assertEqual(self.analytics.completion_percentage, Decimal('65.00'))


class ReportingWorkflowTests(TransactionTestCase):
    """End-to-end workflow tests for reporting"""
    
    def setUp(self):
        """Set up test data"""
        # Create users
        self.teacher_user = User.objects.create_user('teacher', 'teacher@example.com', 'password')
        self.admin_user = User.objects.create_user('admin', 'admin@example.com', 'password')
        self.student_user = User.objects.create_user('student', 'student@example.com', 'password')
        
        # Create student
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            student_id='STU001',
            current_class='Form 1',
            approved=True
        )
        
        # Create period
        now = timezone.now()
        self.period = ReportingPeriod.objects.create(
            name="Week 1-2 Term 1",
            start_date=now.date(),
            end_date=(now + timedelta(days=14)).date(),
            term='term1',
            year=2026,
            submission_opens=now - timedelta(hours=1),
            submission_deadline=now + timedelta(days=7),
            approval_deadline=now + timedelta(days=14),
            status='open'
        )
    
    def test_complete_reporting_workflow(self):
        """Test complete workflow: Create → Submit → Approve → Publish"""
        
        # 1. Create report
        result = BiWeeklyReportService.create_report(
            self.period,
            self.student,
            self.teacher_user,
            {'academic': 'Good', 'behaviour': 'Excellent'}
        )
        self.assertTrue(result['success'])
        report = result['report']
        self.assertEqual(report.status, 'draft')
        
        # 2. Submit report
        result = BiWeeklyReportService.submit_report(report, self.teacher_user)
        self.assertTrue(result['success'])
        report.refresh_from_db()
        self.assertEqual(report.status, 'submitted')
        
        # 3. Approve report
        result = BiWeeklyReportService.approve_report(report, self.admin_user, 'Approved')
        self.assertTrue(result['success'])
        report.refresh_from_db()
        self.assertEqual(report.status, 'approved')
        
        # 4. Publish report
        result = BiWeeklyReportService.publish_report(report)
        self.assertTrue(result['success'])
        report.refresh_from_db()
        self.assertEqual(report.status, 'published')
        self.assertIsNotNone(report.published_at)


class ReportingViewsIntegrationTests(TestCase):
    def setUp(self):
        now = timezone.now()

        self.teacher_user = User.objects.create_user('tview', 'tview@example.com', 'password')
        TeacherProfile.objects.create(user=self.teacher_user, department='Science', approved=True)

        self.admin_user = User.objects.create_user('aview', 'aview@example.com', 'password')
        self.admin_user.is_staff = True
        self.admin_user.save()
        AdminProfile.objects.create(user=self.admin_user, approved=True, email_verified=True)

        self.student_user = User.objects.create_user('sview', 'sview@example.com', 'password')
        self.student = StudentProfile.objects.create(
            user=self.student_user,
            student_id='STUV01',
            current_class='Form 1',
            approved=True,
        )

        self.period = ReportingPeriod.objects.create(
            name='Cycle 1',
            start_date=now.date(),
            end_date=(now + timedelta(days=14)).date(),
            term='term1',
            year=2026,
            submission_opens=now - timedelta(days=1),
            submission_deadline=now + timedelta(days=5),
            approval_deadline=now + timedelta(days=10),
            status='open',
        )

    def test_teacher_can_open_periods_page(self):
        self.client.login(username='tview', password='password')
        response = self.client.get(reverse('reports:teacher_periods'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reports Workspace')

    def test_teacher_can_save_subject_comments_in_report_builder(self):
        self.client.login(username='tview', password='password')
        response = self.client.post(reverse('reports:teacher_report_editor', args=[self.period.id, self.student.id]), {
            'academic_row_count': '2',
            'academic_subject_0': 'Mathematics',
            'academic_percentage_0': '88.0',
            'academic_term_0': 'term1',
            'academic_comment_0': 'Strong problem solving.',
            'academic_include_0': 'on',
            'academic_subject_1': 'English',
            'academic_percentage_1': '72.0',
            'academic_term_1': 'term1',
            'academic_comment_1': 'Keep reading daily.',
            'strengths': 'Consistent effort',
            'areas_for_improvement': 'Written expression',
            'recommendations': 'More revision',
            'general_comments': 'Good progress',
            'additional_comments': 'Ready for the next reporting cycle',
            'grading_format': 'percentage',
            'custom_grading_scale': '',
            'action': 'save',
        })

        self.assertEqual(response.status_code, 200)
        report = BiWeeklyReport.objects.get(period=self.period, student=self.student)
        self.assertEqual(report.content['selected_subjects'], ['Mathematics'])
        self.assertEqual(report.content['subject_comments']['Mathematics'], 'Strong problem solving.')
        self.assertEqual(report.content['draft_academic_entries']['Mathematics']['percentage'], 88.0)
        self.assertEqual(report.content['additional_comments'], 'Ready for the next reporting cycle')
        self.assertFalse(Grade.objects.filter(student=self.student, subject='Mathematics', term='term1').exists())

    def test_submit_promotes_draft_marks_to_grade_records(self):
        self.client.login(username='tview', password='password')
        response = self.client.post(reverse('reports:teacher_report_editor', args=[self.period.id, self.student.id]), {
            'academic_row_count': '2',
            'academic_subject_0': 'Mathematics',
            'academic_percentage_0': '91',
            'academic_term_0': 'term1',
            'academic_comment_0': 'Excellent consistency.',
            'academic_include_0': 'on',
            'academic_subject_1': 'English',
            'academic_percentage_1': '76',
            'academic_term_1': 'term1',
            'academic_comment_1': 'Good reading skills.',
            'academic_include_1': 'on',
            'strengths': 'Strong academics',
            'areas_for_improvement': 'Homework timing',
            'recommendations': 'Daily revision',
            'general_comments': 'Positive progress',
            'additional_comments': 'Keep momentum',
            'grading_format': 'percentage',
            'custom_grading_scale': '',
            'action': 'submit',
        })

        self.assertEqual(response.status_code, 302)
        report = BiWeeklyReport.objects.get(period=self.period, student=self.student)
        self.assertEqual(report.status, 'submitted')

        math_grade = Grade.objects.get(student=self.student, subject='Mathematics', term='term1')
        english_grade = Grade.objects.get(student=self.student, subject='English', term='term1')
        self.assertEqual(float(math_grade.percentage), 91.0)
        self.assertEqual(float(english_grade.percentage), 76.0)

    def test_admin_can_approve_and_publish_report(self):
        report = BiWeeklyReport.objects.create(
            period=self.period,
            student=self.student,
            teacher=self.teacher_user,
            content={'strengths': 'Strong progress'},
            status='submitted',
            submitted_by=self.teacher_user,
            submitted_at=timezone.now(),
        )

        self.client.login(username='aview', password='password')
        response = self.client.post(reverse('reports:admin_reports_dashboard'), {
            'report_id': report.id,
            'action': 'approve',
            'note': 'Approved',
        })
        self.assertEqual(response.status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.status, 'approved')

        response = self.client.post(reverse('reports:admin_reports_dashboard'), {
            'report_id': report.id,
            'action': 'publish',
        })
        self.assertEqual(response.status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.status, 'published')

    def test_student_can_view_published_reports(self):
        Grade.objects.create(
            student=self.student,
            subject='Mathematics',
            percentage=Decimal('85.0'),
            cambridge_letter_grade='A*',
            term='term1',
        )
        Grade.objects.create(
            student=self.student,
            subject='English',
            percentage=Decimal('65.0'),
            cambridge_letter_grade='B',
            term='term1',
        )

        report = BiWeeklyReport.objects.create(
            period=self.period,
            student=self.student,
            teacher=self.teacher_user,
            content={
                'general_comments': 'Great job',
                'additional_comments': 'Maintain momentum',
                'selected_subjects': ['Mathematics'],
                'subject_comments': {'Mathematics': 'Excellent work'},
            },
            status='published',
            published_at=timezone.now(),
        )

        self.client.login(username='sview', password='password')
        response = self.client.get(reverse('reports:student_reports'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Progress Reports')
        self.assertContains(response, 'Reports Available: 1')
        self.assertContains(response, 'End of Term Reports')
        self.assertContains(response, self.period.name)

        detail = self.client.get(reverse('reports:student_report_detail', args=[report.id]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self.period.name)
        self.assertContains(detail, 'Excellent work')
        self.assertContains(detail, 'Maintain momentum')
        self.assertNotContains(detail, 'English')
