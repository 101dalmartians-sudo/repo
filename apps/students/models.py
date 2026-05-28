from django.db import models
from django.contrib.auth.models import User


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=32, unique=True)
    current_class = models.CharField(max_length=50)
    email_verified = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='students/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.student_id})"
