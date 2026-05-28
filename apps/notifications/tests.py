from django.contrib.auth.models import User
from django.test import TestCase

from .models import Notification


class NotificationTests(TestCase):
    def test_notification_string_representation(self):
        user = User.objects.create_user(username='student1', password='password123')
        note = Notification.objects.create(
            recipient=user,
            title='Test Notice',
            message='This is a test.',
        )
        self.assertEqual(str(note), f'{user} - {note.title}')
