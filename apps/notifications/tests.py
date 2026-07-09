from django.contrib.auth.models import User
from django.test import TestCase
from unittest.mock import patch

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

    @patch('apps.notifications.signals.send_notification_email.delay', side_effect=Exception('broker down'))
    @patch('apps.notifications.signals.send_notification_email')
    def test_notification_creation_survives_celery_failure(self, send_notification_email_mock, _delay_mock):
        user = User.objects.create_user(username='student2', password='password123')

        note = Notification.objects.create(
            recipient=user,
            title='Fallback Notice',
            message='Celery unavailable should not break this.',
        )

        self.assertIsNotNone(note.pk)
        send_notification_email_mock.assert_called_once_with(note.id)
