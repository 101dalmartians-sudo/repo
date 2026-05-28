from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification
from .tasks import send_notification_email


@receiver(post_save, sender=Notification)
def notification_created(sender, instance, created, **kwargs):
    if created:
        send_notification_email.delay(instance.id)
