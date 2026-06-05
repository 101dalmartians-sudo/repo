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


class FinancialRecord(models.Model):
    TERM_CHOICES = [
        ('term1', 'Term 1'),
        ('term2', 'Term 2'),
        ('term3', 'Term 3'),
    ]
    
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='financial_records')
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    year = models.IntegerField()
    due_date = models.DateField(null=True, blank=True)
    
    # Transport fee
    transport_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    transport_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    transport_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # School tuition
    school_tuition = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tuition_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tuition_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'term', 'year')
        ordering = ['-year', 'term']
    
    def __str__(self):
        return f"{self.student} - {self.term.upper()} {self.year}"
    
    @property
    def total_fee(self):
        return self.transport_fee + self.school_tuition
    
    @property
    def total_paid(self):
        return self.transport_paid + self.tuition_paid
    
    @property
    def total_balance(self):
        return self.transport_balance + self.tuition_balance
