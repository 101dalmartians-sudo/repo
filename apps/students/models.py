import os
import uuid
from collections import OrderedDict
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import models
from django.db.models import JSONField
from django.utils import timezone


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=32, unique=True)
    current_class = models.CharField(max_length=50)
    email_verified = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='students/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.student_id})"

    def get_active_financial_records(self):
        return self.financial_records.filter(total_balance__gt=0).order_by('year', 'term')

    def get_balance_summary(self):
        records = self.financial_records.all()
        return {
            'total_due': sum((record.total_fee for record in records), Decimal('0.00')),
            'total_paid': sum((record.total_paid for record in records), Decimal('0.00')),
            'total_balance': sum((record.total_balance for record in records), Decimal('0.00')),
        }

    def get_term_summaries(self):
        summaries = OrderedDict()
        for record in self.financial_records.order_by('-year', 'term'):
            key = (record.term, record.year)
            if key not in summaries:
                summaries[key] = {
                    'term': record.term,
                    'year': record.year,
                    'total_due': Decimal('0.00'),
                    'total_paid': Decimal('0.00'),
                    'total_balance': Decimal('0.00'),
                }
            summaries[key]['total_due'] += record.total_fee
            summaries[key]['total_paid'] += record.total_paid
            summaries[key]['total_balance'] += record.total_balance
        return list(summaries.values())


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
    transport_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    transport_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    transport_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # School tuition
    school_tuition = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tuition_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tuition_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'term', 'year')
        ordering = ['-year', 'term']
    
    def __str__(self):
        return f"{self.student} - {self.get_term_display()} {self.year}"
    
    @property
    def total_fee(self):
        return self.transport_fee + self.school_tuition
    
    @property
    def total_paid(self):
        return self.transport_paid + self.tuition_paid
    
    @property
    def total_balance(self):
        return self.transport_balance + self.tuition_balance

    @property
    def is_overdue(self):
        return self.due_date and self.due_date < timezone.now().date() and self.total_balance > 0

    def apply_payment(self, amount):
        remaining = Decimal(amount)
        if remaining <= 0:
            return Decimal('0.00')

        if self.transport_balance > 0:
            transport_payment = min(self.transport_balance, remaining)
            self.transport_paid += transport_payment
            self.transport_balance -= transport_payment
            remaining -= transport_payment

        if remaining > 0 and self.tuition_balance > 0:
            tuition_payment = min(self.tuition_balance, remaining)
            self.tuition_paid += tuition_payment
            self.tuition_balance -= tuition_payment
            remaining -= tuition_payment

        self.transport_balance = max(self.transport_balance, Decimal('0.00'))
        self.tuition_balance = max(self.tuition_balance, Decimal('0.00'))
        self.save(update_fields=[
            'transport_paid', 'transport_balance', 'tuition_paid', 'tuition_balance', 'updated_at'
        ])
        return remaining


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank transfer'),
        ('card', 'Card'),
        ('mobile_money', 'Mobile money'),
    ]

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='payments')
    financial_record = models.ForeignKey(FinancialRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=32, choices=PAYMENT_METHOD_CHOICES, default='cash')
    payment_date = models.DateTimeField(default=timezone.now)
    receipt_number = models.CharField(max_length=64, unique=True, editable=False)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"{self.student} - {self.amount} ({self.receipt_number})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        super().save(*args, **kwargs)
        if is_new and self.financial_record:
            remainder = self.financial_record.apply_payment(self.amount)
            if remainder > 0:
                self.note = (self.note or '') + f"\nUnapplied amount: {remainder:.2f}"
                super().save(update_fields=['note'])
            self.create_notifications()

    def generate_receipt_number(self):
        return f"RCPT-{uuid.uuid4().hex[:12].upper()}"

    def create_notifications(self):
        from apps.notifications.models import Notification

        message = (
            f"Payment of {self.amount:.2f} received for {self.student}. "
            f"Receipt: {self.receipt_number}."
        )
        Notification.objects.create(recipient=self.student.user, title='Payment received', message=message)
        if self.student.user.email:
            self.send_email_notification(message)

        for admin in User.objects.filter(is_staff=True):
            Notification.objects.create(
                recipient=admin,
                title='Student payment recorded',
                message=f"{self.student.user.username} paid {self.amount:.2f} for {self.financial_record.get_term_display() if self.financial_record else 'unknown term'}.",
            )

    def send_email_notification(self, message):
        subject = 'Payment Received'
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com')
        try:
            send_mail(subject, message, from_email, [self.student.user.email], fail_silently=True)
        except Exception:
            pass


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ]

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='attendance_records')
    term = models.CharField(max_length=10)
    year = models.IntegerField()
    date = models.DateField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='present')
    note = models.TextField(blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'term', 'year', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.student} — {self.date} ({self.get_status_display()})"


class ExamSchedule(models.Model):
    subject = models.CharField(max_length=128)
    term = models.CharField(max_length=10)
    year = models.IntegerField()
    exam_date = models.DateField()
    description = models.TextField(blank=True)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100.00)
    results_released = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', 'term', 'exam_date']

    def __str__(self):
        return f"{self.subject} exam — {self.get_term_display() if hasattr(self, 'get_term_display') else self.term} {self.year}"


class ExamResult(models.Model):
    exam = models.ForeignKey(ExamSchedule, on_delete=models.CASCADE, related_name='results')
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='exam_results')
    score = models.DecimalField(max_digits=6, decimal_places=2)
    comments = models.TextField(blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('exam', 'student')
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.student} — {self.exam.subject} {self.score}"


class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=128)
    model_name = models.CharField(max_length=128)
    object_repr = models.CharField(max_length=255)
    changes = JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.model_name} {self.action} by {self.actor or 'system'}"
