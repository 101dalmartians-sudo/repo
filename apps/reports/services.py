"""
Bi-Weekly Reporting Services

Handles business logic for report creation, approval, publishing,
and synchronization with all dashboards.
"""

from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from apps.notifications.models import Notification
from .models import BiWeeklyReport, ReportingAnalytics, ReportingPeriod


class BiWeeklyReportService:
    """Service for bi-weekly report operations"""
    
    @staticmethod
    @transaction.atomic
    def create_report(period, student, teacher, content):
        """
        Create a new bi-weekly report draft.
        
        Args:
            period: ReportingPeriod instance
            student: StudentProfile instance
            teacher: User (teacher) creating the report
            content: Dict of field_name -> value
            
        Returns:
            dict with result status
        """
        try:
            # Check submission window
            if not period.is_open_for_submission():
                return {
                    'success': False,
                    'message': 'Submission window is not open',
                    'status_code': 400
                }
            
            # Get or create report
            report, created = BiWeeklyReport.objects.get_or_create(
                period=period,
                student=student,
                defaults={
                    'teacher': teacher,
                    'content': content,
                    'status': 'draft'
                }
            )
            
            if not created:
                # Update existing draft
                if report.status != 'draft':
                    return {
                        'success': False,
                        'message': f'Cannot edit report in {report.status} status',
                        'status_code': 400
                    }
                report.content = content
                report.updated_by = teacher
                report.save()
            
            # Invalidate caches
            BiWeeklyReportService._invalidate_caches(student)
            
            return {
                'success': True,
                'message': 'Report created/updated successfully',
                'report': report,
                'created': created,
                'status_code': 200
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error creating report: {str(e)}',
                'status_code': 500
            }
    
    @staticmethod
    @transaction.atomic
    def submit_report(report, user):
        """
        Submit report for approval.
        
        Args:
            report: BiWeeklyReport instance
            user: User submitting (teacher)
            
        Returns:
            dict with result status
        """
        try:
            report.submit(user)
            
            # Notify admins
            BiWeeklyReportService._notify_report_submitted(report)
            
            # Update analytics
            BiWeeklyReportService._update_period_analytics(report.period)
            
            # Invalidate caches
            BiWeeklyReportService._invalidate_caches(report.student)
            
            return {
                'success': True,
                'message': 'Report submitted for approval',
                'status_code': 200
            }
            
        except ValueError as e:
            return {
                'success': False,
                'message': str(e),
                'status_code': 400
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error submitting report: {str(e)}',
                'status_code': 500
            }
    
    @staticmethod
    @transaction.atomic
    def approve_report(report, admin_user, approval_notes=''):
        """
        Approve report for publishing.
        
        Args:
            report: BiWeeklyReport instance
            admin_user: User approving (admin)
            approval_notes: Optional approval notes
            
        Returns:
            dict with result status
        """
        try:
            report.approve(admin_user, approval_notes)
            
            # Notify teacher
            BiWeeklyReportService._notify_report_approved(report)
            
            # Update analytics
            BiWeeklyReportService._update_period_analytics(report.period)
            
            # Invalidate caches
            BiWeeklyReportService._invalidate_caches(report.student)
            
            return {
                'success': True,
                'message': 'Report approved successfully',
                'status_code': 200
            }
            
        except ValueError as e:
            return {
                'success': False,
                'message': str(e),
                'status_code': 400
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error approving report: {str(e)}',
                'status_code': 500
            }
    
    @staticmethod
    @transaction.atomic
    def publish_report(report):
        """
        Publish report to student dashboard.
        
        Args:
            report: BiWeeklyReport instance
            
        Returns:
            dict with result status
        """
        try:
            report.publish()
            
            # Notify student
            BiWeeklyReportService._notify_report_published(report)
            
            # Update analytics
            BiWeeklyReportService._update_period_analytics(report.period)
            
            # Invalidate caches
            BiWeeklyReportService._invalidate_caches(report.student)
            
            return {
                'success': True,
                'message': 'Report published to student dashboard',
                'status_code': 200
            }
            
        except ValueError as e:
            return {
                'success': False,
                'message': str(e),
                'status_code': 400
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error publishing report: {str(e)}',
                'status_code': 500
            }
    
    @staticmethod
    def get_student_reports(student):
        """
        Get all reports for a student, grouped by type.
        
        Args:
            student: StudentProfile instance
            
        Returns:
            dict with bi-weekly and term reports
        """
        bi_weekly_reports = student.bi_weekly_reports.filter(
            status__in=['published', 'approved']
        ).order_by('-period__start_date')
        
        return {
            'bi_weekly_reports': list(bi_weekly_reports.values(
                'id', 'period__name', 'period__start_date', 'period__end_date',
                'status', 'published_at', 'teacher__first_name', 'teacher__last_name'
            )),
            'total_bi_weekly': bi_weekly_reports.count()
        }
    
    @staticmethod
    def get_period_report_status(period):
        """
        Get reporting status for a period.
        
        Args:
            period: ReportingPeriod instance
            
        Returns:
            dict with status counts
        """
        reports = period.reports.all()
        
        return {
            'total_reports': reports.count(),
            'draft_count': reports.filter(status='draft').count(),
            'submitted_count': reports.filter(status='submitted').count(),
            'approved_count': reports.filter(status='approved').count(),
            'published_count': reports.filter(status='published').count(),
            'completion_percentage': (
                (reports.filter(status__in=['published', 'approved']).count() / reports.count() * 100)
                if reports.exists() else 0
            )
        }
    
    # Private notification methods
    @staticmethod
    def _notify_report_submitted(report):
        """Notify admins that a report has been submitted"""
        from django.contrib.auth.models import Group
        
        try:
            admins = Group.objects.get(name='Administrators').user_set.all()
            message = (
                f"New bi-weekly report submitted: {report.student} - {report.period}\n"
                f"Teacher: {report.teacher.get_full_name()}\n"
                f"Submitted: {report.submitted_at.strftime('%Y-%m-%d %H:%M')}"
            )
            
            for admin in admins:
                Notification.objects.create(
                    recipient=admin,
                    title='Report Submitted for Approval',
                    message=message
                )
        except Exception as e:
            pass  # Silently fail notification
    
    @staticmethod
    def _notify_report_approved(report):
        """Notify teacher that report has been approved"""
        message = (
            f"Your bi-weekly report for {report.student} ({report.period}) "
            f"has been approved and will be published to the student dashboard."
        )
        Notification.objects.create(
            recipient=report.teacher,
            title='Report Approved',
            message=message
        )
    
    @staticmethod
    def _notify_report_published(report):
        """Notify student that report has been published"""
        message = (
            f"Your bi-weekly progress report for {report.period.name} is now available. "
            f"Check the 'Progress Reports' section of your dashboard."
        )
        Notification.objects.create(
            recipient=report.student.user,
            title='Progress Report Available',
            message=message
        )
    
    @staticmethod
    def _invalidate_caches(student):
        """Invalidate student report caches"""
        cache_keys = [
            f'student_bi_weekly_reports_{student.id}',
            f'student_all_reports_{student.id}',
            f'student_dashboard_{student.id}'
        ]
        cache.delete_many(cache_keys)
    
    @staticmethod
    def _update_period_analytics(period):
        """Update analytics for a reporting period"""
        try:
            analytics, _ = ReportingAnalytics.objects.get_or_create(period=period)
            
            reports = period.reports.all()
            
            analytics.total_students = reports.values('student').distinct().count()
            analytics.reports_created = reports.count()
            analytics.reports_submitted = reports.filter(status='submitted').count()
            analytics.reports_approved = reports.filter(status='approved').count()
            analytics.reports_published = reports.filter(status='published').count()
            analytics.reports_pending = reports.filter(status='draft').count()
            
            if analytics.total_students > 0:
                analytics.completion_percentage = (
                    (analytics.reports_published / analytics.total_students) * 100
                )
            
            analytics.save()
            
        except Exception as e:
            pass  # Silently fail
