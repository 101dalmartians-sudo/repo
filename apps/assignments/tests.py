from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from apps.notifications.models import Notification
from apps.students.models import StudentProfile
from apps.teachers.models import TeacherProfile


class AssignmentUploadTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='teacher1', password='password123', email='teacher1@example.com')
        TeacherProfile.objects.create(user=self.teacher, department='Science')
        student_user = User.objects.create_user(username='student1', password='password123', email='student1@example.com')
        StudentProfile.objects.create(user=student_user, student_id='S001', current_class='Form 1')
        self.client = Client()
        self.client.login(username='teacher1', password='password123')

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
        notification = Notification.objects.first()
        self.assertIn('New assignment', notification.title)
