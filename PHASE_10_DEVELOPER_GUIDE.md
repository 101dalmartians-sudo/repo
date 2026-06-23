# Phase 10 Developer Quick Start

**Last Updated:** June 23, 2026

---

## Quick Setup (5 minutes)

### 1. Apply Migrations
```bash
python manage.py migrate reports
```

### 2. Create Admin Account (if needed)
```bash
python manage.py createsuperuser
```

### 3. Access Django Admin
```
http://localhost:8000/admin/
```

---

## Creating a Reporting Period

1. Go to: **Reports → Reporting Periods → Add**
2. Fill in:
   - **Name:** "Week 1-2 Term 1"
   - **Term:** term1
   - **Year:** 2026
   - **Start Date:** 2026-06-23
   - **End Date:** 2026-07-06
   - **Submission Opens:** 2026-06-23
   - **Submission Deadline:** 2026-07-03
   - **Approval Deadline:** 2026-07-06
   - **Status:** open
3. Click Save

---

## Configuring Report Fields

1. Go to: **Reports → Report Fields → Add**
2. Create fields for report (e.g.):

| Name | Type | Required | Order |
|------|------|----------|-------|
| Academic Progress | text | Yes | 1 |
| Subject Performance | score | Yes | 2 |
| Teacher Comments | textarea | Yes | 3 |
| Behavior | rating | No | 4 |
| Attendance | score | No | 5 |

3. Each field can be dragged to reorder

---

## Testing the Workflow

### As Admin
```python
from apps.reports.models import ReportingPeriod, BiWeeklyReport
from apps.students.models import StudentProfile
from django.contrib.auth.models import User

# Get test data
period = ReportingPeriod.objects.first()
student = StudentProfile.objects.first()
teacher = User.objects.filter(groups__name='Teachers').first()
admin = User.objects.filter(is_staff=True).first()

# Create report as teacher
from apps.reports.services import BiWeeklyReportService

result = BiWeeklyReportService.create_report(
    period=period,
    student=student,
    teacher=teacher,
    content={'academic': 'Good', 'behaviour': 'Excellent'}
)

report = result['report']  # Get the report object

# Submit
BiWeeklyReportService.submit_report(report, teacher)

# Approve as admin
BiWeeklyReportService.approve_report(report, admin, 'Looks good')

# Publish
BiWeeklyReportService.publish_report(report)

# Verify
print(f"Report status: {report.status}")
print(f"Published at: {report.published_at}")
```

---

## Key Files

| File | Purpose |
|------|---------|
| `apps/reports/models.py` | Models: ReportingPeriod, ReportField, BiWeeklyReport, ReportingAnalytics |
| `apps/reports/admin.py` | Django Admin customization |
| `apps/reports/services.py` | Business logic (BiWeeklyReportService) |
| `apps/reports/signals.py` | Automatic synchronization |
| `apps/reports/tests.py` | Test cases |

---

## Common Service Methods

### Create Report
```python
result = BiWeeklyReportService.create_report(
    period=period,
    student=student,
    teacher=teacher,
    content={'field1': 'value1', 'field2': 'value2'}
)

if result['success']:
    report = result['report']
else:
    error = result['message']
```

### Submit Report
```python
result = BiWeeklyReportService.submit_report(report, user)
if not result['success']:
    print(result['message'])
```

### Approve Report
```python
result = BiWeeklyReportService.approve_report(
    report=report,
    admin_user=admin,
    approval_notes='Good work'
)
```

### Publish Report
```python
result = BiWeeklyReportService.publish_report(report)
```

### Get Student Reports
```python
reports = BiWeeklyReportService.get_student_reports(student)
# Returns: {'bi_weekly_reports': [...], 'total_bi_weekly': count}
```

### Get Period Status
```python
status = BiWeeklyReportService.get_period_report_status(period)
# Returns: {
#     'total_reports': count,
#     'draft_count': count,
#     'submitted_count': count,
#     'approved_count': count,
#     'published_count': count,
#     'completion_percentage': float
# }
```

---

## Running Tests

### Run all reports tests
```bash
python manage.py test apps.reports
```

### Run specific test class
```bash
python manage.py test apps.reports.tests.BiWeeklyReportServiceTests
```

### Run with verbose output
```bash
python manage.py test apps.reports --verbosity=2
```

---

## Database Queries

### Get All Reports for a Student
```python
reports = BiWeeklyReport.objects.filter(student=student)
```

### Get Published Reports Only
```python
reports = BiWeeklyReport.objects.filter(status='published')
```

### Get Reports by Period
```python
reports = BiWeeklyReport.objects.filter(period=period)
```

### Get Reports Pending Approval
```python
reports = BiWeeklyReport.objects.filter(status='submitted')
```

### Get Reports by Teacher
```python
reports = BiWeeklyReport.objects.filter(teacher=teacher)
```

### Get Period Analytics
```python
from apps.reports.models import ReportingAnalytics
analytics = ReportingAnalytics.objects.get(period=period)
print(f"Completion: {analytics.completion_percentage}%")
```

---

## Admin Bulk Actions

### Approve Multiple Reports
1. Go to: **Reports → Reports**
2. Filter by Status = "submitted"
3. Select reports using checkboxes
4. Choose action: "Approve selected reports"
5. Click Go

### Publish Multiple Reports
1. Go to: **Reports → Reports**
2. Filter by Status = "approved"
3. Select reports
4. Choose action: "Publish selected reports"
5. Click Go

### Archive Multiple Reports
1. Go to: **Reports → Reports**
2. Filter by Status = "published"
3. Select reports
4. Choose action: "Archive selected reports"
5. Click Go

---

## Workflow States

```
draft → submitted → approved → published
   ↓          ↓           ↓          ↓
 edit      waiting      review    visible
```

### Valid Transitions
- draft → draft (edit)
- draft → submitted (submit)
- submitted → approved (admin approve)
- approved → published (admin publish)
- published → archived (admin archive)

### Invalid Transitions
- Cannot go from submitted back to draft
- Cannot approve a draft (must be submitted first)
- Cannot publish unapproved report

---

## Signals & Caching

### Signals Sent On
- Report created/updated: Cache invalidation, analytics update
- Report deleted: Cache invalidation, analytics update

### Cache Keys Invalidated
- `student_bi_weekly_reports_{id}`
- `student_all_reports_{id}`
- `student_dashboard_{id}`
- `admin_reporting_dashboard`

### Manual Cache Clear
```python
from django.core.cache import cache
cache.delete('student_bi_weekly_reports_123')
cache.clear()  # Clear all caches
```

---

## Debugging Tips

### Check Signal Registration
```python
from django.core.signals import setting_changed
from django.dispatch import receivers
print(receivers(setting_changed))
```

### Enable Query Logging
```python
import logging
logging.getLogger('django.db.backends').setLevel(logging.DEBUG)
```

### Check Cache
```python
from django.core.cache import cache
cache.set('test_key', 'test_value', 300)
print(cache.get('test_key'))  # Should print: test_value
```

### List All Reports
```python
from apps.reports.models import BiWeeklyReport
BiWeeklyReport.objects.all().values('id', 'student', 'status', 'period')
```

---

## Common Issues & Solutions

**Q: Report not appearing in admin?**
A: Check if 'apps.reports' is in INSTALLED_APPS. Run `python manage.py check`.

**Q: Can't see student reports?**
A: Ensure report status is 'published' and period is open.

**Q: Notification not sent?**
A: Check Celery is running, verify CELERY_TASK_ALWAYS_EAGER=True in dev.

**Q: Admin bulk action not working?**
A: Refresh page, select reports again, check browser console for errors.

**Q: Migration failed?**
A: Run `python manage.py migrate reports --fake-initial` or delete and recreate.

---

## Environment Variables

For production, set:
```bash
DEBUG=False
ALLOWED_HOSTS=your-domain.com
DATABASE_URL=postgresql://user:pass@host/dbname
CELERY_BROKER_URL=redis://localhost:6379/0
CACHE_URL=redis://localhost:6379/1
```

---

## Useful Django Shell Commands

```bash
python manage.py shell
```

Then in shell:
```python
from apps.reports.models import *
from apps.reports.services import BiWeeklyReportService

# Get first period
period = ReportingPeriod.objects.first()

# Count reports
BiWeeklyReport.objects.count()

# Get completion percentage
analytics = ReportingAnalytics.objects.get(period=period)
print(analytics.completion_percentage)

# Update analytics manually
BiWeeklyReportService._update_period_analytics(period)
```

---

## Performance Tips

1. **Add database indexes:**
   ```python
   # In model Meta class
   indexes = [
       models.Index(fields=['period', 'student']),
       models.Index(fields=['status', 'period']),
   ]
   ```

2. **Use select_related:**
   ```python
   reports = BiWeeklyReport.objects.select_related(
       'period', 'student', 'teacher'
   )
   ```

3. **Use prefetch_related for many-to-many:**
   ```python
   reports = BiWeeklyReport.objects.prefetch_related('fields')
   ```

4. **Cache report queries:**
   ```python
   cache_key = f'period_reports_{period.id}'
   reports = cache.get(cache_key)
   if not reports:
       reports = BiWeeklyReport.objects.filter(period=period)
       cache.set(cache_key, reports, 300)
   ```

---

## Next Steps After Deployment

1. **Create dashboard section** - Add "Progress Reports" to student dashboard
2. **Add PDF export** - Generate PDFs using ReportLab
3. **Email notifications** - Send report links to parents
4. **Analytics dashboard** - Show completion trends
5. **Bulk operations** - Create Celery tasks for batch operations

---

## Support Resources

- **Model Documentation:** See docstrings in `apps/reports/models.py`
- **Service Documentation:** See docstrings in `apps/reports/services.py`
- **Admin Documentation:** See docstrings in `apps/reports/admin.py`
- **Test Examples:** See `apps/reports/tests.py` for usage patterns
- **Django Admin Docs:** https://docs.djangoproject.com/en/4.2/ref/contrib/admin/

---

**Questions? Check the implementation files or run tests to understand the system!**

