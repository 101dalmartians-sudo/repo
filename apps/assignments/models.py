from django.db import models


class Assignment(models.Model):
    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=128)
    target_class = models.CharField(max_length=64)
    due_date = models.DateTimeField()
    file_attachment = models.FileField(upload_to='assignments/')
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        'teachers.TeacherProfile',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assignments'
    )

    def __str__(self):
        return self.title
