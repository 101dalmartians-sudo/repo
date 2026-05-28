from django.db import models
from django.contrib.auth.models import User


class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    department = models.CharField(max_length=128)
    work_email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='teachers/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — {self.department}"
