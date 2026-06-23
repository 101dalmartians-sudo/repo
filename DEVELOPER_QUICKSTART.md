# Developer Quick Start Guide - Data Synchronization

Quick reference for developers using the data synchronization system.

## Quick Links

- **Audit Report**: [AUDIT_REPORT.md](AUDIT_REPORT.md) - System gaps and analysis
- **Implementation Guide**: [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) - Detailed architecture and usage
- **Phase Status**: [PHASE_STATUS.md](PHASE_STATUS.md) - Implementation progress
- **Source Code**: See respective app directories (finance, grades, students)

---

## Financial Synchronization - Quick Start

### Process a Payment

```python
from apps.finance.services import FinancialService
from apps.students.models import Payment

# Create payment in admin/form
payment = Payment.objects.create(
    student=student,
    financial_record=financial_record,
    amount=Decimal('10000.00'),
    payment_method='cash',
    is_approved=True  # Triggers processing
)

# Service automatically:
# ✓ Applies payment to financial record
# ✓ Updates balances
# ✓ Calculates status
# ✓ Invalidates caches
# ✓ Creates notifications

# Or explicitly process:
result = FinancialService.process_payment(payment, request.user)
if result['success']:
    print(f"Payment processed. Remainder: {result['remainder']}")
```

### Get Student Financial Summary

```python
from apps.finance.services import FinancialService

student = StudentProfile.objects.get(pk=1)
summary = FinancialService.get_student_financial_summary(student)

# Returns: {
#   'total_due': Decimal('30000.00'),
#   'total_paid': Decimal('15000.00'),
#   'total_balance': Decimal('15000.00'),
#   'overdue_count': 2,
#   'status': 'partial'
# }
```

### Get Dashboard Data

```python
from apps.finance.cache import DashboardCache

# Admin dashboard (cached 5 min)
dashboard = DashboardCache.get_admin_financial_dashboard()

# Student dashboard
student_dashboard = DashboardCache.get_student_financial_dashboard(student_id)

# Results are automatically cached and invalidated on changes
```

### Reverse a Payment

```python
from apps.finance.services import FinancialService

result = FinancialService.reverse_payment(
    payment=payment,
    user=request.user,
    reason='Duplicate entry'
)

# Automatically:
# ✓ Marks payment as reversed
# ✓ Restores financial record balances
# ✓ Updates status
# ✓ Creates notifications
# ✓ Invalidates caches
```

### Update Financial Record

```python
from apps.finance.services import FinancialService

result = FinancialService.update_financial_record(
    financial_record=record,
    user=request.user,
    transport_fee=Decimal('6000.00'),
    school_tuition=Decimal('26000.00')
)

# Automatically updates all dependent data and notifies student
```

---

## Academic Synchronization - Quick Start

### Record a Grade

```python
from apps.grades.services import AcademicService

result = AcademicService.create_or_update_grade(
    student=student,
    subject='Mathematics',
    percentage=Decimal('85.5'),
    term='term1'
)

# Returns: {
#   'success': True,
#   'message': 'Grade recorded successfully',
#   'grade': grade_object,
#   'created': True,
#   'cambridge_grade': 'A*'
# }

# Automatically:
# ✓ Calculates Cambridge grade
# ✓ Creates notification
# ✓ Invalidates student cache
# ✓ Invalidates admin analytics cache
```

### Get Student Academic Summary

```python
from apps.grades.services import AcademicService

student = StudentProfile.objects.get(pk=1)
summary = AcademicService.get_student_academic_summary(student)

# Returns: {
#   'total_subjects': 5,
#   'average_percentage': 82.5,
#   'highest_grade': {...},
#   'lowest_grade': {...},
#   'grades_by_term': {...},
#   'status': 'excellent',
#   'performance_rating': 'Excellent'
# }
```

### Get Admin Academic Dashboard

```python
from apps.grades.services import AcademicService

dashboard = AcademicService.get_admin_academic_dashboard()

# Returns: {
#   'total_grades': 450,
#   'average_class_percentage': 75.3,
#   'grade_distribution': {
#       'A*': 45,
#       'A': 89,
#       'B': 120,
#       'C': 145,
#       'D': 38,
#       'U': 13
#   },
#   'students_by_performance': {...},
#   'subjects_summary': [...]
# }
```

### Delete a Grade

```python
from apps.grades.services import AcademicService

result = AcademicService.delete_grade(grade, user=request.user)

# Automatically:
# ✓ Removes grade
# ✓ Notifies student
# ✓ Invalidates caches
```

### Generate Performance Report

```python
from apps.grades.services import AcademicService

report = AcademicService.get_performance_report(student, term='term1')

# Returns detailed report with all grades for the term
```

### Process Exam Results to Grades

```python
from apps.grades.services import AcademicService

exam_schedule = ExamSchedule.objects.get(pk=1)
result = AcademicService.process_exam_results(exam_schedule)

# Automatically:
# ✓ Creates grade for each exam result
# ✓ Calculates percentage based on score/max_score
# ✓ Marks exam as results_released
# ✓ Sends notifications to students
# ✓ Updates admin analytics
```

---

## Cache Management

### Invalidate Student Caches

```python
from apps.finance.cache import DashboardCache

# Invalidate specific student
DashboardCache.invalidate_student_dashboard(student_id)

# This invalidates:
# - Financial dashboard
# - Academic summary
# - Attendance summary
```

### Invalidate Admin Dashboard

```python
from apps.finance.cache import DashboardCache

DashboardCache.invalidate_admin_dashboard()

# Next load regenerates from database
```

### Manually Clear All Cache

```python
from django.core.cache import cache

cache.clear()  # Clears everything (use with caution in production)
```

---

## Background Tasks (Celery)

### Run a Task Manually

```python
from apps.finance.tasks import check_overdue_accounts

# Run immediately
result = check_overdue_accounts.delay()

# Or synchronously (for testing)
result = check_overdue_accounts()
```

### View Task Results

```python
from celery.result import AsyncResult

task_id = 'abc123'  # From task.delay() call
result = AsyncResult(task_id)

print(result.state)  # PENDING, STARTED, SUCCESS, FAILURE
print(result.result)  # Actual result or exception
```

### Monitor Running Tasks

```bash
# In separate terminal, watch Celery worker:
celery -A aspireacademy worker -l info

# In another, watch Celery beat (scheduler):
celery -A aspireacademy beat -l info
```

---

## Testing

### Run All Tests

```bash
# All tests
python manage.py test

# Specific app
python manage.py test apps.finance
python manage.py test apps.grades

# Specific class
python manage.py test apps.finance.tests.PaymentSynchronizationTests

# Specific test method
python manage.py test apps.finance.tests.PaymentSynchronizationTests.test_payment_reversal

# With coverage
coverage run --source='apps.finance' manage.py test apps.finance
coverage report
coverage html  # View in htmlcov/index.html
```

### Test Payment Processing

```python
from django.test import TransactionTestCase
from apps.students.models import Payment, FinancialRecord, StudentProfile
from apps.finance.services import FinancialService

class TestPaymentFlow(TransactionTestCase):
    def test_payment_sync(self):
        # Create test data
        student = StudentProfile.objects.create(...)
        record = FinancialRecord.objects.create(...)
        
        # Create payment
        payment = Payment.objects.create(
            student=student,
            financial_record=record,
            amount=Decimal('10000.00'),
            is_approved=True
        )
        
        # Process
        result = FinancialService.process_payment(payment, None)
        
        # Verify
        self.assertTrue(result['success'])
        record.refresh_from_db()
        self.assertEqual(record.total_paid, Decimal('10000.00'))
```

---

## Monitoring & Debugging

### Check Payment Status

```python
from apps.students.models import Payment

payment = Payment.objects.get(pk=1)
print(f"Status: {payment.status}")  # approved, pending, reversed
print(f"Approved: {payment.is_approved}")
print(f"Reversed: {payment.is_reversed}")
print(f"Approved by: {payment.approved_by}")
print(f"Approved at: {payment.approved_at}")
```

### Check Financial Record Status

```python
from apps.students.models import FinancialRecord

record = FinancialRecord.objects.get(pk=1)
print(f"Status: {record.status}")  # pending, partial, paid, overdue
print(f"Total Fee: {record.total_fee}")
print(f"Total Paid: {record.total_paid}")
print(f"Total Balance: {record.total_balance}")
print(f"Payment Count: {record.payment_count}")
print(f"Last Payment: {record.last_payment_date}")
print(f"Updated By: {record.updated_by}")
```

### Check Grade Status

```python
from apps.grades.models import Grade

grade = Grade.objects.get(pk=1)
print(f"Subject: {grade.subject}")
print(f"Percentage: {grade.percentage}")
print(f"Cambridge Grade: {grade.cambridge_letter_grade}")
print(f"Term: {grade.term}")
```

### View Audit Logs

```python
from apps.students.models import AuditLog

# Recent changes
logs = AuditLog.objects.order_by('-created_at')[:20]
for log in logs:
    print(f"{log.actor} | {log.action} | {log.model_name} | {log.created_at}")

# By model
financial_logs = AuditLog.objects.filter(model_name='payment')
grade_logs = AuditLog.objects.filter(model_name='grade')
```

### Check Cache Status

```python
from django.core.cache import cache

# Check specific key
value = cache.get('admin_financial_dashboard')
if value:
    print("Dashboard cache exists")
else:
    print("Dashboard cache missing or expired")

# List cached keys (Redis only)
# cache.keys('*')  # Requires Redis-py

# Get cache statistics (if supported)
# stats = cache.get_stats()
```

---

## Common Issues & Solutions

### Issue: Payment not showing in student dashboard

**Solution:**
```python
# Check if payment was processed
from apps.students.models import Payment

payment = Payment.objects.get(pk=1)
if not payment.is_approved:
    print("Payment not approved yet")
    # Approve it
    payment.is_approved = True
    payment.save()

# Force cache invalidation
from apps.finance.cache import DashboardCache
DashboardCache.invalidate_student_dashboard(student_id)
```

### Issue: Balance calculations wrong

**Solution:**
```python
# Recalculate all financial records
from apps.students.models import FinancialRecord

for record in FinancialRecord.objects.all():
    record.update_status()
    record.save(update_fields=['status', 'updated_at'])

# Clear caches
from django.core.cache import cache
cache.clear()
```

### Issue: Grade not appearing in dashboard

**Solution:**
```python
# Check if grade was created
from apps.grades.models import Grade

grade = Grade.objects.get(student=student, subject='Math')
print(f"Grade exists: {grade.percentage}%")

# Recalculate Cambridge grade
grade.save()  # Triggers recalculation

# Clear cache
from apps.finance.cache import DashboardCache
DashboardCache.invalidate_student_dashboard(student.id)
```

### Issue: Celery tasks not running

**Solution:**
```bash
# Check if Celery worker is running
ps aux | grep celery

# Start Celery worker if not running
celery -A aspireacademy worker -l info

# Check if Celery beat is running (for scheduled tasks)
ps aux | grep beat

# Start Celery beat
celery -A aspireacademy beat -l info
```

---

## Best Practices

### ✅ DO

- Always use FinancialService for payment operations
- Always use AcademicService for grade operations
- Always wrap operations in try-except
- Always set updated_by when modifying records
- Always use @transaction.atomic for multi-step operations
- Always invalidate relevant caches after changes
- Always test changes before deployment

### ❌ DON'T

- Don't directly edit balances without using service
- Don't bypass signals by using update() queryset method
- Don't forget to set is_approved when creating payments
- Don't delete financial records with payments
- Don't mix manual calculations with service methods
- Don't create duplicate payments in loop
- Don't forget to clear test data between test methods

---

## Performance Tips

### Optimize Queries

```python
# ❌ N+1 problem
for payment in Payment.objects.all():
    print(payment.student.student_id)

# ✅ Optimized
Payment.objects.select_related('student').all()
for payment in payments:
    print(payment.student.student_id)
```

### Use Caching

```python
# ❌ Recalculates every time
def get_dashboard():
    return FinancialService.get_financial_dashboard_summary()

# ✅ Caches result
def get_dashboard():
    from apps.finance.cache import DashboardCache
    return DashboardCache.get_admin_financial_dashboard()
```

### Batch Operations

```python
# ❌ Slow - updates one at a time
for record in records:
    record.status = 'paid'
    record.save()

# ✅ Faster - batch update
FinancialRecord.objects.filter(total_balance=0).update(status='paid')
```

---

## Code Examples

### Complete Payment Flow

```python
from django.shortcuts import render, redirect
from apps.students.models import Payment, FinancialRecord
from apps.finance.services import FinancialService

def record_payment(request, record_id):
    record = FinancialRecord.objects.get(pk=record_id)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        method = request.POST.get('method')
        
        # Create payment
        payment = Payment.objects.create(
            student=record.student,
            financial_record=record,
            amount=Decimal(amount),
            payment_method=method,
            is_approved=True
        )
        
        # Process through service
        result = FinancialService.process_payment(payment, request.user)
        
        if result['success']:
            messages.success(request, 'Payment recorded')
            if result['remainder'] > 0:
                messages.warning(request, f'Overpayment: {result["remainder"]:.2f}')
        else:
            messages.error(request, result['message'])
        
        return redirect('some_view')
    
    # Show payment form
    return render(request, 'payment_form.html', {'record': record})
```

---

## Helpful Commands

```bash
# Run tests with coverage
coverage run --source='apps' manage.py test && coverage report

# Check for syntax errors
python -m py_compile apps/**/*.py

# Run specific test
python manage.py test apps.finance.tests.PaymentSynchronizationTests.test_payment_processing

# Drop and recreate test database
python manage.py test --keepdb

# Profile views (add django-silk for better profiling)
python manage.py runserver_plus

# Check database migrations
python manage.py showmigrations

# Create/apply migrations
python manage.py makemigrations
python manage.py migrate

# Access Django shell with models preloaded
python manage.py shell

# Dump data for backup
python manage.py dumpdata > backup.json

# Load data from backup
python manage.py loaddata backup.json
```

---

**Last Updated:** 2026-06-23  
**For detailed documentation, see [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)**

