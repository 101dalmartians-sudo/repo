from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

from .models import Notification


@shared_task
def send_notification_email(notification_id):
    try:
        notification = Notification.objects.get(pk=notification_id)
    except Notification.DoesNotExist:
        return

    recipient = notification.recipient
    if not recipient.email:
        return

    subject = f"Aspire Academy Portal: {notification.title}"
    message = notification.message
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [recipient.email],
        fail_silently=False,
    )
