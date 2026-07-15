"""
Bi-Weekly Student Reporting System Models

Provides structured bi-weekly progress reports alongside existing
end-of-term reports. Fully manageable from Django Admin.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError


class ReportingPeriod(models.Model):
    """
    Defines a bi-weekly reporting period.
    Administrators can create and manage reporting windows.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('archived', 'Archived'),
    ]

    REPORTING_TYPE_CHOICES = [
        ('bi_weekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
        ('mid_term', 'Mid-Term'),
        ('end_term', 'End-of-Term'),
        ('custom', 'Custom'),
    ]
    
    name = models.CharField(max_length=100)
    # e.g., "Week 1-2 of Term 1" or "June 23-July 6, 2026"
    reporting_type = models.CharField(max_length=20, choices=REPORTING_TYPE_CHOICES, default='bi_weekly')
    
    start_date = models.DateField()
    end_date = models.DateField()
    
    term = models.CharField(
        max_length=10,
        choices=[('term1', 'Term 1'), ('term2', 'Term 2'), ('term3', 'Term 3')],
        null=True,
        blank=True
    )
    year = models.IntegerField()
    
    # Reporting window
    submission_opens = models.DateTimeField()  # When teachers can start creating reports
    submission_deadline = models.DateTimeField()  # When teachers must submit by
    approval_deadline = models.DateTimeField()  # When admin must approve by
    publish_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Audit trail
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reporting_periods_created')
    last_edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reporting_periods_edited')
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-year', '-start_date']
        verbose_name = 'Reporting Period'
        verbose_name_plural = 'Reporting Periods'
    
    def __str__(self):
        return f"{self.name} ({self.year})"

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date cannot be earlier than start date.'})
        span_days = (self.end_date - self.start_date).days
        if self.reporting_type == 'bi_weekly' and span_days not in (13, 14):
            raise ValidationError({'end_date': 'Bi-weekly reporting periods should cover approximately 14 days.'})

    @property
    def workspace_status(self):
        if self.status == 'archived':
            return 'archived'
        return 'published' if self.is_published else 'draft'
    
    def is_open_for_submission(self):
        """Check if submission window is currently open"""
        now = timezone.now()
        return self.submission_opens <= now <= self.submission_deadline
    
    def can_be_approved(self):
        """Check if approval deadline has passed"""
        now = timezone.now()
        return now <= self.approval_deadline


class ReportField(models.Model):
    """
    Configurable report fields that can appear in bi-weekly reports.
    Administrators can add/remove fields from Django Admin.
    """
    FIELD_TYPE_CHOICES = [
        ('text', 'Text'),
        ('textarea', 'Long Text'),
        ('score', 'Score (0-100)'),
        ('rating', 'Rating (1-5)'),
        ('boolean', 'Yes/No'),
        ('choice', 'Multiple Choice'),
    ]
    
    name = models.CharField(max_length=100)  # e.g., "Academic Performance"
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
    description = models.TextField(blank=True)
    
    # Order in report
    order = models.PositiveIntegerField(default=0)
    
    # Whether this field is required
    is_required = models.BooleanField(default=True)
    
    # Choices for choice-based fields (stored as JSON)
    choices = models.JSONField(default=list, blank=True, help_text='For choice fields: ["Option 1", "Option 2"]')
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Report Field'
        verbose_name_plural = 'Report Fields'
    
    def __str__(self):
        return self.name


class BiWeeklyReport(models.Model):
    """
    Bi-weekly progress report for a student created by teacher.
    Teachers create, admins approve, then published to student dashboard.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    # Relationship
    period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name='reports')
    student = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE, related_name='bi_weekly_reports')
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='biweekly_reports_created')
    
    # Content - stored as JSON
    content = models.JSONField(default=dict, help_text='Field name -> value pairs')
    
    # Status and workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Approvals
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='biweekly_reports_submitted')
    
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='biweekly_reports_approved')
    approval_notes = models.TextField(blank=True)
    
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='biweekly_reports_updated')
    
    class Meta:
        unique_together = ('period', 'student')
        ordering = ['-period__start_date']
        verbose_name = 'Bi-Weekly Report'
        verbose_name_plural = 'Bi-Weekly Reports'
    
    def __str__(self):
        return f"{self.student} - {self.period} ({self.status})"
    
    def submit(self, user):
        """Submit report for approval"""
        if self.status != 'draft':
            raise ValueError('Only draft reports can be submitted')
        self.status = 'submitted'
        self.submitted_at = timezone.now()
        self.submitted_by = user
        self.save(update_fields=['status', 'submitted_at', 'submitted_by', 'updated_at'])
    
    def approve(self, user, notes=''):
        """Approve report"""
        if self.status != 'submitted':
            raise ValueError('Only submitted reports can be approved')
        self.status = 'approved'
        self.approved_at = timezone.now()
        self.approved_by = user
        self.approval_notes = notes
        self.save(update_fields=['status', 'approved_at', 'approved_by', 'approval_notes', 'updated_at'])
    
    def publish(self):
        """Publish report to student dashboard"""
        if self.status != 'approved':
            raise ValueError('Only approved reports can be published')
        self.status = 'published'
        self.published_at = timezone.now()
        self.save(update_fields=['status', 'published_at', 'updated_at'])
    
    def archive(self):
        """Archive report"""
        self.status = 'archived'
        self.save(update_fields=['status', 'updated_at'])


class ReportingAnalytics(models.Model):
    """
    Aggregated analytics for bi-weekly reporting.
    Updated whenever reports are created, approved, or published.
    """
    period = models.OneToOneField(ReportingPeriod, on_delete=models.CASCADE, related_name='analytics')
    
    # Counts
    total_students = models.PositiveIntegerField(default=0)
    reports_created = models.PositiveIntegerField(default=0)
    reports_submitted = models.PositiveIntegerField(default=0)
    reports_approved = models.PositiveIntegerField(default=0)
    reports_published = models.PositiveIntegerField(default=0)
    reports_pending = models.PositiveIntegerField(default=0)
    
    # Completion percentage
    completion_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    
    # Timestamps
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Reporting Analytics'
        verbose_name_plural = 'Reporting Analytics'
    
    def __str__(self):
        return f"Analytics for {self.period}"
