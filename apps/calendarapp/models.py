from django.db import models


class CalendarEvent(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_global = models.BooleanField(default=False)
    target_class = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.title
