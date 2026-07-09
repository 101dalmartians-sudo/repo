import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification
from .tasks import send_notification_email


logger = logging.getLogger(__name__)


@receiver(post_save, sender=Notification)
def notification_created(sender, instance, created, **kwargs):
    if created:
        try:
            send_notification_email.delay(instance.id)
            return
        except Exception as exc:
            logger.warning(
                'Celery dispatch failed for notification %s; falling back to sync send. Error: %s',
                instance.id,
                exc,
            )

        # Never let email delivery issues block the request/transaction flow.
        try:
            send_notification_email(instance.id)
        except Exception:
            logger.exception('Synchronous notification email failed for notification %s', instance.id)
