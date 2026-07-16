"""
Django Admin Configuration for Bi-Weekly Reports

Admins can manage reporting periods, fields, and reports.
Teachers can create and submit reports.
"""

from django.contrib import admin, messages
from django.utils.html import format_html, format_html_join
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import ReportingPeriod, ReportField, BiWeeklyReport, ReportingAnalytics


@admin.register(ReportingPeriod)
class ReportingPeriodAdmin(admin.ModelAdmin):
    """Admin for managing bi-weekly reporting periods"""
    
    list_display = [
        'name', 'term_display', 'year', 'date_range', 'status_badge',
        'submission_status', 'reports_count'
    ]
    list_filter = ['status', 'year', 'term', 'start_date']
    search_fields = ['name']
    readonly_fields = ['created_by', 'last_edited_by', 'is_published', 'created_at', 'updated_at', 'analytics_link']
    actions = ['mark_open', 'mark_closed', 'mark_archived']
    actions = ['open_periods', 'close_periods', 'archive_periods']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'reporting_type', 'term', 'year')
        }),
        ('Period Dates', {
            'fields': ('start_date', 'end_date')
        }),
        ('Submission Window', {
            'fields': ('submission_opens', 'submission_deadline'),
            'description': 'When teachers can create and submit reports'
        }),
        ('Approval Window', {
            'fields': ('approval_deadline',),
            'description': 'When admins must approve reports'
        }),
        ('Publishing', {
            'fields': ('publish_date', 'is_published')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Audit Trail', {
            'fields': ('created_by', 'last_edited_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Analytics', {
            'fields': ('analytics_link',),
            'classes': ('collapse',)
        }),
    )
    
    def term_display(self, obj):
        return obj.get_term_display() if obj.term else '—'
    term_display.short_description = 'Term'
    
    def date_range(self, obj):
        return f"{obj.start_date} to {obj.end_date}"
    date_range.short_description = 'Date Range'
    
    def status_badge(self, obj):
        colors = {
            'open': '#28a745',
            'closed': '#ffc107',
            'archived': '#6c757d',
        }
        color = colors.get(obj.status, '#007bff')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def submission_status(self, obj):
        if obj.is_open_for_submission():
            return mark_safe('<span style="color: #28a745; font-weight: bold;">✓ Open</span>')
        else:
            return mark_safe('<span style="color: #dc3545;">✗ Closed</span>')
    submission_status.short_description = 'Submission Open?'
    
    def reports_count(self, obj):
        count = obj.reports.count()
        return format_html(
            '<a href="?period__id__exact={}">{} report{}</a>',
            obj.id,
            count,
            's' if count != 1 else ''
        )
    reports_count.short_description = 'Reports'
    
    def analytics_link(self, obj):
        if hasattr(obj, 'analytics'):
            url = reverse('admin:reports_reportinganalytics_change', args=[obj.analytics.id])
            return format_html(
                '<a class="button" href="{}">View Analytics</a>',
                url
            )
        return '—'
    analytics_link.short_description = 'Analytics'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.last_edited_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description='Open selected reporting periods')
    def mark_open(self, request, queryset):
        updated = queryset.update(status='open')
        self.message_user(request, f'{updated} reporting period(s) opened.', messages.SUCCESS)

    @admin.action(description='Close selected reporting periods')
    def mark_closed(self, request, queryset):
        updated = queryset.update(status='closed')
        self.message_user(request, f'{updated} reporting period(s) closed.', messages.SUCCESS)

    @admin.action(description='Archive selected reporting periods')
    def mark_archived(self, request, queryset):
        updated = queryset.update(status='archived')
        self.message_user(request, f'{updated} reporting period(s) archived.', messages.SUCCESS)

    def open_periods(self, request, queryset):
        updated = queryset.exclude(status='open').update(status='open')
        self.message_user(request, f'Opened {updated} reporting period(s).', messages.SUCCESS)
    open_periods.short_description = 'Mark selected periods as Open'

    def close_periods(self, request, queryset):
        updated = queryset.exclude(status='closed').update(status='closed')
        self.message_user(request, f'Closed {updated} reporting period(s).', messages.SUCCESS)
    close_periods.short_description = 'Mark selected periods as Closed'

    def archive_periods(self, request, queryset):
        updated = queryset.exclude(status='archived').update(status='archived')
        self.message_user(request, f'Archived {updated} reporting period(s).', messages.SUCCESS)
    archive_periods.short_description = 'Mark selected periods as Archived'


@admin.register(ReportField)
class ReportFieldAdmin(admin.ModelAdmin):
    """Admin for configuring report fields"""
    
    list_display = ['name', 'field_type', 'is_required', 'order', 'is_active']
    list_filter = ['field_type', 'is_required', 'is_active']
    list_editable = ['order', 'is_active']
    search_fields = ['name']
    
    fieldsets = (
        ('Field Information', {
            'fields': ('name', 'description', 'field_type')
        }),
        ('Configuration', {
            'fields': ('order', 'is_required', 'is_active')
        }),
        ('Choices', {
            'fields': ('choices',),
            'description': 'For choice-based fields, enter JSON array: ["Option 1", "Option 2"]'
        }),
    )


@admin.register(BiWeeklyReport)
class BiWeeklyReportAdmin(admin.ModelAdmin):
    """Admin for managing bi-weekly reports"""
    
    list_display = [
        'student_link', 'period_link', 'teacher_display', 
        'status_badge', 'submitted_display', 'approved_display', 'actions_display'
    ]
    list_filter = ['status', 'period__year', 'period__term', 'created_at']
    search_fields = ['student__student_id', 'student__user__first_name', 'student__user__last_name']
    readonly_fields = [
        'period', 'student', 'teacher', 'created_at', 'updated_at', 
        'submitted_at', 'submitted_by', 'approved_at', 'approved_by', 
        'published_at', 'content_display'
    ]
    
    fieldsets = (
        ('Report Information', {
            'fields': ('period', 'student', 'teacher')
        }),
        ('Report Content', {
            'fields': ('content_display', 'content'),
            'classes': ('collapse',)
        }),
        ('Status & Workflow', {
            'fields': ('status',)
        }),
        ('Submission', {
            'fields': ('submitted_at', 'submitted_by'),
            'classes': ('collapse',)
        }),
        ('Approval', {
            'fields': ('approved_at', 'approved_by', 'approval_notes'),
            'classes': ('collapse',)
        }),
        ('Publishing', {
            'fields': ('published_at',),
            'classes': ('collapse',)
        }),
        ('Audit Trail', {
            'fields': ('created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_reports', 'publish_reports', 'archive_reports']
    
    def student_link(self, obj):
        url = reverse('admin:students_studentprofile_change', args=[obj.student.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            str(obj.student)
        )
    student_link.short_description = 'Student'
    
    def period_link(self, obj):
        url = reverse('admin:reports_reportingperiod_change', args=[obj.period.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.period.name
        )
    period_link.short_description = 'Period'
    
    def teacher_display(self, obj):
        if obj.teacher:
            return obj.teacher.get_full_name() or obj.teacher.username
        return '—'
    teacher_display.short_description = 'Created By'
    
    def status_badge(self, obj):
        colors = {
            'draft': '#6c757d',
            'submitted': '#007bff',
            'approved': '#28a745',
            'published': '#20c997',
            'archived': '#dc3545',
        }
        color = colors.get(obj.status, '#007bff')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def submitted_display(self, obj):
        if obj.submitted_at:
            return format_html(
                '✓ {}<br><small>{}</small>',
                obj.submitted_at.strftime('%Y-%m-%d %H:%M'),
                obj.submitted_by.username if obj.submitted_by else '—'
            )
        return '—'
    submitted_display.short_description = 'Submitted'
    
    def approved_display(self, obj):
        if obj.approved_at:
            return format_html(
                '✓ {}<br><small>{}</small>',
                obj.approved_at.strftime('%Y-%m-%d %H:%M'),
                obj.approved_by.username if obj.approved_by else '—'
            )
        return '—'
    approved_display.short_description = 'Approved'
    
    def content_display(self, obj):
        """Display report content in readable format"""
        if not obj.content:
            return '—'

        rows = format_html_join(
            '',
            '<tr><td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">{}</td>'
            '<td style="border: 1px solid #ddd; padding: 8px;">{}</td></tr>',
            ((key, value) for key, value in obj.content.items()),
        )
        return format_html(
            '<table style="width: 100%; border-collapse: collapse;">{}</table>',
            rows,
        )
    content_display.short_description = 'Content'
    
    def actions_display(self, obj):
        buttons = []
        
        if obj.status == 'submitted':
            buttons.append('Approve')
        elif obj.status == 'approved':
            buttons.append('Publish')
        
        if obj.status != 'archived':
            buttons.append('Archive')
        
        return ', '.join(buttons) if buttons else '—'
    actions_display.short_description = 'Available Actions'
    
    def approve_reports(self, request, queryset):
        """Bulk approve reports"""
        approved_count = 0
        for report in queryset:
            if report.status == 'submitted':
                try:
                    report.approve(request.user)
                    approved_count += 1
                except ValueError as e:
                    self.message_user(
                        request,
                        f"Could not approve {report}: {str(e)}",
                        messages.ERROR
                    )
        
        self.message_user(
            request,
            f"Successfully approved {approved_count} report(s)",
            messages.SUCCESS
        )
    approve_reports.short_description = "Approve selected reports"
    
    def publish_reports(self, request, queryset):
        """Bulk publish reports"""
        published_count = 0
        for report in queryset:
            if report.status == 'approved':
                try:
                    report.publish()
                    published_count += 1
                except ValueError as e:
                    self.message_user(
                        request,
                        f"Could not publish {report}: {str(e)}",
                        messages.ERROR
                    )
        
        self.message_user(
            request,
            f"Successfully published {published_count} report(s)",
            messages.SUCCESS
        )
    publish_reports.short_description = "Publish selected reports"
    
    def archive_reports(self, request, queryset):
        """Bulk archive reports"""
        for report in queryset:
            report.archive()
        
        self.message_user(
            request,
            f"Successfully archived {queryset.count()} report(s)",
            messages.SUCCESS
        )
    archive_reports.short_description = "Archive selected reports"


@admin.register(ReportingAnalytics)
class ReportingAnalyticsAdmin(admin.ModelAdmin):
    """Admin for viewing bi-weekly reporting analytics"""
    
    list_display = [
        'period_link', 'total_students', 'completion_badge',
        'submitted_count', 'approved_count', 'published_count'
    ]
    list_filter = ['period__year', 'period__term']
    readonly_fields = [
        'period', 'total_students', 'reports_created', 'reports_submitted',
        'reports_approved', 'reports_published', 'reports_pending',
        'completion_percentage', 'updated_at'
    ]
    
    fieldsets = (
        ('Period', {
            'fields': ('period',)
        }),
        ('Report Counts', {
            'fields': (
                'total_students', 'reports_created', 'reports_submitted',
                'reports_approved', 'reports_published', 'reports_pending'
            )
        }),
        ('Metrics', {
            'fields': ('completion_percentage',)
        }),
        ('Updated', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
    
    def period_link(self, obj):
        url = reverse('admin:reports_reportingperiod_change', args=[obj.period.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.period.name
        )
    period_link.short_description = 'Period'
    
    def completion_badge(self, obj):
        percentage = float(obj.completion_percentage)
        if percentage == 100:
            color = '#28a745'
        elif percentage >= 75:
            color = '#20c997'
        elif percentage >= 50:
            color = '#ffc107'
        else:
            color = '#dc3545'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 3px; font-weight: bold;">{}%</span>',
            color,
            percentage
        )
    completion_badge.short_description = 'Completion'
    
    def submitted_count(self, obj):
        return format_html(
            '{} <small style="color: #666;">/ {}</small>',
            obj.reports_submitted,
            obj.reports_created
        )
    submitted_count.short_description = 'Submitted'
    
    def approved_count(self, obj):
        return format_html(
            '{} <small style="color: #666;">/ {}</small>',
            obj.reports_approved,
            obj.reports_submitted
        )
    approved_count.short_description = 'Approved'
    
    def published_count(self, obj):
        return format_html(
            '{} <small style="color: #666;">/ {}</small>',
            obj.reports_published,
            obj.reports_approved
        )
    published_count.short_description = 'Published'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
