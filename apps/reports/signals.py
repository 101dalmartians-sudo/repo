"""
Bi-Weekly Reporting Signals

Automatic synchronization of bi-weekly reports with dashboards,
analytics, and notifications.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from .models import BiWeeklyReport, ReportingAnalytics
from .services import BiWeeklyReportService


@receiver(post_save, sender=BiWeeklyReport)
def synchronize_report_changes(sender, instance, created, **kwargs):
    """
    Synchronize when a bi-weekly report is created or updated.
    
    Updates:
    - Student dashboard cache
    - Period analytics
    - Admin dashboard
    """
    # Invalidate student dashboard
    BiWeeklyReportService._invalidate_caches(instance.student)
    
    # Update period analytics
    BiWeeklyReportService._update_period_analytics(instance.period)
    
    # Invalidate admin dashboard
    cache.delete('admin_reporting_dashboard')


@receiver(post_delete, sender=BiWeeklyReport)
def synchronize_report_deletion(sender, instance, **kwargs):
    """
    Synchronize when a bi-weekly report is deleted.
    
    Updates:
    - Student dashboard cache
    - Period analytics
    - Admin dashboard
    """
    # Invalidate caches
    BiWeeklyReportService._invalidate_caches(instance.student)
    
    # Update period analytics
    BiWeeklyReportService._update_period_analytics(instance.period)
    
    # Invalidate admin dashboard
    cache.delete('admin_reporting_dashboard')
