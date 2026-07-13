from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from tempfile import TemporaryDirectory

from apps.assignments.models import Assignment
from apps.notifications.models import Notification
from apps.students.models import StudentProfile
from apps.teachers.models import TeacherProfile


class AssignmentUploadTests(TestCase):
    def setUp(self):
        self.temp_media = TemporaryDirectory(ignore_cleanup_errors=True)
        self.override_settings = self.settings(MEDIA_ROOT=self.temp_media.name)
        self.override_settings.enable()

        self.teacher = User.objects.create_user(username='teacher1', password='password123', email='teacher1@example.com')
        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher, department='Science')
        self.student_user = User.objects.create_user(username='student1', password='password123', email='student1@example.com')
        self.student_profile = StudentProfile.objects.create(user=self.student_user, student_id='S001', current_class='Form 1')
        self.other_student_user = User.objects.create_user(username='student2', password='password123', email='student2@example.com')
        StudentProfile.objects.create(user=self.other_student_user, student_id='S002', current_class='Form 2')
        self.client = Client()
        self.client.login(username='teacher1', password='password123')

    def tearDown(self):
        self.override_settings.disable()
        self.temp_media.cleanup()

    def _future_due_date(self):
        return timezone.now() + timedelta(days=30)

    def test_assignment_upload_creates_notification(self):
        upload_file = SimpleUploadedFile('test.pdf', b'PDF content', content_type='application/pdf')
        response = self.client.post(
            '/assignments/upload/',
            {
                'title': 'Test Assignment',
                'subject': 'Biology',
                'target_class': 'Form 1',
                'due_date': '2030-01-01T12:00',
                'file_attachment': upload_file,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Notification.objects.exists())
        assignment = Assignment.objects.get(title='Test Assignment')
        self.assertTrue(assignment.file_attachment.name.startswith('assignments/'))
        notification = Notification.objects.first()
        self.assertIn('New assignment', notification.title)

    def test_student_dashboard_renders_attachment_links(self):
        assignment = Assignment.objects.create(
            title='Biology worksheet',
            subject='Biology',
            target_class='Form 1',
            due_date=self._future_due_date(),
            file_attachment=SimpleUploadedFile('worksheet.pdf', b'PDF content', content_type='application/pdf'),
            uploaded_by=self.teacher_profile,
        )

        self.client.logout()
        self.client.login(username='student1', password='password123')
        response = self.client.get(reverse('students_dashboard'))

        self.assertEqual(response.status_code, 200)
        expected_link = reverse('assignment_attachment_download', args=[assignment.id])
        self.assertContains(response, expected_link)
        self.assertContains(response, 'Open attachment')
        self.assertContains(response, 'Download')

    def test_authorized_student_can_access_attachment_endpoint(self):
        assignment = Assignment.objects.create(
            title='Math worksheet',
            subject='Mathematics',
            target_class='Form 1',
            due_date=self._future_due_date(),
            file_attachment=SimpleUploadedFile('math.pdf', b'PDF content', content_type='application/pdf'),
            uploaded_by=self.teacher_profile,
        )

        self.client.logout()
        self.client.login(username='student1', password='password123')
        response = self.client.get(reverse('assignment_attachment_download', args=[assignment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Disposition'), 'inline; filename="math.pdf"')
        response.close()

    def test_unauthorized_student_cannot_access_attachment_endpoint(self):
        assignment = Assignment.objects.create(
            title='Chem worksheet',
            subject='Chemistry',
            target_class='Form 1',
            due_date=self._future_due_date(),
            file_attachment=SimpleUploadedFile('chem.pdf', b'PDF content', content_type='application/pdf'),
            uploaded_by=self.teacher_profile,
        )

        self.client.logout()
        self.client.login(username='student2', password='password123')
        response = self.client.get(reverse('assignment_attachment_download', args=[assignment.id]))

        self.assertEqual(response.status_code, 403)
        response.close()

    def test_teacher_can_access_own_attachment(self):
        assignment = Assignment.objects.create(
            title='Physics worksheet',
            subject='Physics',
            target_class='Form 1',
            due_date=self._future_due_date(),
            file_attachment=SimpleUploadedFile('physics.pdf', b'PDF content', content_type='application/pdf'),
            uploaded_by=self.teacher_profile,
        )

        response = self.client.get(reverse('assignment_attachment_download', args=[assignment.id]))
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_supported_file_types_are_accessible(self):
        file_matrix = [
            ('test.pdf', 'application/pdf'),
            ('test.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            ('test.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('test.jpg', 'image/jpeg'),
            ('test.png', 'image/png'),
        ]

        self.client.logout()
        self.client.login(username='teacher1', password='password123')

        for filename, content_type in file_matrix:
            with self.subTest(filename=filename):
                assignment = Assignment.objects.create(
                    title=f'Upload {filename}',
                    subject='General',
                    target_class='Form 1',
                    due_date=self._future_due_date(),
                    file_attachment=SimpleUploadedFile(filename, b'binary-content', content_type=content_type),
                    uploaded_by=self.teacher_profile,
                )

                self.client.logout()
                self.client.login(username='student1', password='password123')
                response = self.client.get(reverse('assignment_attachment_download', args=[assignment.id]))
                self.assertEqual(response.status_code, 200)
                response.close()

                download_response = self.client.get(
                    reverse('assignment_attachment_download', args=[assignment.id]) + '?download=1'
                )
                self.assertEqual(download_response.status_code, 200)
                self.assertIn('attachment; filename="', download_response.get('Content-Disposition', ''))
                download_response.close()

                self.client.logout()
                self.client.login(username='teacher1', password='password123')
