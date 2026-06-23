# Data Synchronization Implementation Guide

## Overview

This document provides comprehensive guidance on the data synchronization system implemented in the Aspire Academy Portal. It covers the architecture, usage, testing, and troubleshooting.

---

## Architecture Overview

### Layers

```
┌─────────────────────────────────────────────────────────┐
│            Admin Dashboards / Views                      │
├─────────────────────────────────────────────────────────┤
│  Dashboard Cache Layer (5-min TTL)                      │
├─────────────────────────────────────────────────────────┤
│  Service Layer (FinancialService, etc.)                 │
├─────────────────────────────────────────────────────────┤
│  Signal Handlers (Auto-trigger on model changes)        │
├─────────────────────────────────────────────────────────┤
│  Django ORM / Database Models                           │
├─────────────────────────────────────────────────────────┤
│  Background Tasks (Celery) - Periodic sync & reports    │
└─────────────────────────────────────────────────────────┘
```

### Data Flow: Payment Processing

```
1. Admin creates/updates Payment
   ↓
2. Signal triggers: post_save @ Payment
   ↓
3. FinancialService.process_payment()
   ├─ Apply payment to FinancialRecord
   ├─ Update balances
   ├─ Calculate status
   ├─ Create notifications
   └─ Invalidate caches
   ↓
4. FinancialService._invalidate_student_cache()
   ↓
5. FinancialService._invalidate_dashboard_cache()
   ↓
6. Next dashboard access → Cache regenerated from DB
```

---

## Phase 2: Financial Synchronization

### Components Created

#### 1. **FinancialService** (`apps/finance/services.py`)

Centralized payment and balance management.

**Key Methods:**

```python
# Process a payment and synchronize all records
process_payment(payment, user) → dict

# Reverse a payment with audit trail
reverse_payment(payment, user, reason) → dict

# Update financial record safely
update_financial_record(financial_record, user, **updates) → dict

# Get consistent student summary
get_student_financial_summary(student) → dict

# Get dashboard metrics
get_financial_dashboard_summary() → dict
```

**Usage Example:**

```python
from apps.finance.services import FinancialService

# Process payment
payment = Payment.objects.get(pk=1)
result = FinancialService.process_payment(payment, request.user)

if result['success']:
    print(f"Payment processed. Remainder: {result['remainder']}")
else:
    print(f"Error: {result['message']}")

# Get student financial info
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

#### 2. **Financial Signals** (`apps/finance/signals.py`)

Automatic synchronization triggers.

**Signals:**

```python
# When payment is created/updated
@receiver(post_save, sender=Payment)
def synchronize_payment_creation()

# When payment is deleted
@receiver(post_delete, sender=Payment)
def synchronize_payment_deletion()

# When financial record is created/updated
@receiver(post_save, sender=FinancialRecord)
def synchronize_financial_record_update()

# When financial record deletion is attempted
@receiver(pre_delete, sender=FinancialRecord)
def synchronize_financial_record_deletion()
```

#### 3. **Dashboard Cache** (`apps/finance/cache.py`)

Performance optimization through intelligent caching.

**Key Methods:**

```python
# Get cached dashboard data (regenerates if expired)
get_admin_financial_dashboard() → dict

# Get student dashboard from cache
get_student_financial_dashboard(student_id) → dict

# Get monthly summary
get_monthly_financial_summary(year, month) → dict

# Invalidate specific caches
invalidate_admin_dashboard()
invalidate_student_dashboard(student_id)
```

**Cache Configuration:**
- **TTL**: 5 minutes (300 seconds)
- **Backend**: Django default cache (configure in settings)
- **Invalidation**: Automatic on model changes via signals

#### 4. **Background Tasks** (`apps/finance/tasks.py`)

Celery tasks for periodic synchronization.

**Available Tasks:**

| Task | Schedule | Purpose |
|------|----------|---------|
| `recalculate_financial_status` | Every 4 hours | Recalculate all status fields |
| `check_overdue_accounts` | Daily at 9 AM | Check for overdue and notify |
| `generate_monthly_financial_reports` | Month-end | Generate monthly reports |
| `generate_student_financial_statements` | On-demand | Generate student statements |
| `refresh_dashboard_cache` | Every 5 minutes | Refresh all caches |
| `audit_financial_consistency` | Daily at midnight | Audit for data integrity |

**Setup in settings.py:**

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'recalculate-financial-status': {
        'task': 'apps.finance.tasks.recalculate_financial_status',
        'schedule': crontab(minute=0, hour='*/4'),
    },
    'check-overdue-accounts': {
        'task': 'apps.finance.tasks.check_overdue_accounts',
        'schedule': crontab(minute=0, hour=9),
    },
    # ... more tasks
}
```

### Model Enhancements

#### FinancialRecord New Fields

```python
class FinancialRecord(models.Model):
    # ... existing fields ...
    
    # Status tracking
    status = CharField(choices=[
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
        ('overdue', 'Overdue'),
    ], default='pending')
    
    # Audit trail
    updated_by = ForeignKey(User, null=True, blank=True)
    
    # Metadata
    last_payment_date = DateTimeField(null=True, blank=True)
    payment_count = PositiveIntegerField(default=0)
    
    # New method
    def update_status(self):
        """Calculate status based on balances and due date"""
```

#### Payment New Fields

```python
class Payment(models.Model):
    # ... existing fields ...
    
    # Approval tracking
    status = CharField(choices=[
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('reversed', 'Reversed'),
    ], default='approved')
    is_approved = BooleanField(default=True)
    approved_by = ForeignKey(User, null=True, blank=True)
    approved_at = DateTimeField(null=True, blank=True)
    
    # Reversal tracking
    reversal_of = ForeignKey('self', null=True, blank=True)
    is_reversed = BooleanField(default=False)
    reversal_reason = CharField(max_length=255, blank=True)
    reversed_at = DateTimeField(null=True, blank=True)
    reversed_by = ForeignKey(User, null=True, blank=True)
```

### Data Integrity Features

#### 1. Atomic Transactions

All payment operations use Django's `transaction.atomic()`:

```python
@transaction.atomic
def process_payment(payment, user=None):
    # All changes succeed or all fail
    # No partial updates
```

#### 2. Balance Validation

```python
# Prevents negative balances
financial_record.transport_balance = max(balance, Decimal('0.00'))

# Prevents overpayment
if payment.amount > record.total_balance:
    handle_overpayment()
```

#### 3. Foreign Key Constraints

```python
# Cannot delete record with payments
if instance.payments.filter(is_reversed=False).exists():
    raise ProtectedError("Cannot delete record with payments")
```

#### 4. Audit Trail

All changes tracked via:
- `updated_by` field
- `updated_at` auto timestamp
- Historical audit logs (if needed)

---

## Testing

### Running Tests

```bash
# All financial tests
python manage.py test apps.finance

# Specific test class
python manage.py test apps.finance.tests.PaymentSynchronizationTests

# With coverage
coverage run --source='apps.finance' manage.py test
coverage report
```

### Test Suite

**Financial Record Tests:**
- ✅ Status calculation (pending → partial → paid → overdue)
- ✅ Total calculations
- ✅ Notification creation on new record

**Payment Tests:**
- ✅ Payment processing updates balances
- ✅ Multiple payments to same record
- ✅ Overpayment handling
- ✅ Payment reversal
- ✅ Reversal audit trail

**Service Tests:**
- ✅ Student financial summary accuracy
- ✅ Dashboard metrics accuracy
- ✅ Cache invalidation
- ✅ Financial record updates

---

## Admin Interface Updates

### Payment Admin

```python
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'receipt_number', 'student', 'amount',
        'payment_date', 'status', 'approved_by'
    )
    list_filter = ('status', 'payment_method', 'payment_date')
    search_fields = ('student__student_id', 'receipt_number')
    readonly_fields = ('receipt_number', 'status', 'approved_at')
    
    # Payment reversal action
    actions = ['reverse_selected_payments']
    
    def reverse_selected_payments(self, request, queryset):
        # Admin can reverse multiple payments
        for payment in queryset:
            if not payment.is_reversed:
                FinancialService.reverse_payment(payment, request.user)
        self.message_user(request, f"{queryset.count()} payments reversed")
```

### FinancialRecord Admin

```python
@admin.register(FinancialRecord)
class FinancialRecordAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'term', 'year', 'total_fee',
        'total_paid', 'total_balance', 'status'
    )
    list_filter = ('status', 'term', 'year')
    search_fields = ('student__student_id', 'student__user__username')
    
    # Prevent direct status editing
    readonly_fields = ('status', 'payment_count', 'last_payment_date', 'updated_by')
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        obj.update_status()
        FinancialService._invalidate_student_cache(obj.student)
        FinancialService._invalidate_dashboard_cache()
        super().save_model(request, obj, form, change)
```

---

## Migration Guide

### Step 1: Back up database
```bash
python manage.py dumpdata > backup.json
```

### Step 2: Run migrations
```bash
python manage.py migrate students 0002_financial_synchronization
```

### Step 3: Update all existing status fields
```python
# Run once after migration
python manage.py shell
>>> from apps.students.models import FinancialRecord
>>> for record in FinancialRecord.objects.all():
...     record.update_status()
...     record.save(update_fields=['status'])
```

### Step 4: Verify data integrity
```python
# Check for orphaned payments
Payment.objects.filter(financial_record__isnull=True)

# Check for negative balances
FinancialRecord.objects.filter(
    Q(transport_balance__lt=0) | Q(tuition_balance__lt=0)
)
```

---

## Troubleshooting

### Cache Not Updating

**Problem:** Dashboard shows old data

**Solution:**
```python
from django.core.cache import cache
cache.clear()  # Clear all caches

# Or specific cache
from apps.finance.cache import DashboardCache
DashboardCache.invalidate_admin_dashboard()
```

### Payment Not Synchronizing

**Problem:** Payment created but balances not updated

**Cause:** Signals not registered

**Solution:**
```bash
# Ensure apps.finance.signals is imported
# In apps/finance/apps.py:
class FinanceConfig(AppConfig):
    def ready(self):
        import apps.finance.signals

# Then restart Django
```

### Celery Tasks Not Running

**Problem:** Background tasks not executing

**Solution:**
```bash
# Check Celery worker is running
celery -A aspireacademy worker -l info

# Check Celery beat is running (for scheduled tasks)
celery -A aspireacademy beat -l info

# Test a task manually
python manage.py shell
>>> from apps.finance.tasks import check_overdue_accounts
>>> check_overdue_accounts.delay()
```

### Negative Balances

**Problem:** Balance calculations are negative

**Cause:** Manual payment not applied correctly

**Solution:**
```python
# Fix in shell
from apps.students.models import FinancialRecord
record = FinancialRecord.objects.get(pk=1)
record.transport_balance = max(record.transport_balance, Decimal('0.00'))
record.tuition_balance = max(record.tuition_balance, Decimal('0.00'))
record.save()
```

---

## Best Practices

### 1. Always Use FinancialService

❌ **Don't:** Directly edit balances
```python
payment.financial_record.transport_paid += amount
payment.financial_record.save()
```

✅ **Do:** Use service
```python
FinancialService.process_payment(payment, user)
```

### 2. Validate Before Processing

```python
if payment.is_reversed:
    return {'success': False, 'message': 'Already reversed'}
if payment.financial_record is None:
    return {'success': False, 'message': 'No record linked'}
```

### 3. Always Track Changes

```python
# When modifying records
financial_record.updated_by = request.user
financial_record.save()
```

### 4. Monitor Cache Hit Rate

```python
from django.core.cache import cache
info = cache.get_stats()  # If cache backend supports it
```

### 5. Test Before Deployment

```bash
# Run full test suite
python manage.py test apps.finance

# Run specific scenarios
python manage.py test apps.finance.tests.PaymentSynchronizationTests
```

---

## Performance Considerations

### Database Queries

**Optimized:**
```python
# Use select_related for ForeignKeys
Payment.objects.select_related('student', 'financial_record')

# Use prefetch_related for reverse ForeignKeys
student = StudentProfile.objects.prefetch_related('financial_records', 'payments')
```

### Caching Strategy

- Dashboard: 5-minute TTL (refreshed every 5 min by Celery)
- Student data: 5-minute TTL (invalidated on payment)
- Monthly reports: 30-minute TTL

### Query Optimization

```python
# ❌ N+1 problem
for payment in Payment.objects.all():
    print(payment.student.student_id)

# ✅ Optimized
Payment.objects.select_related('student').all()
for payment in payments:
    print(payment.student.student_id)
```

---

## Monitoring & Alerts

### Key Metrics to Monitor

1. **Financial Consistency**
   - Negative balances (should be 0)
   - Orphaned payments (without record)
   - Reversed payment count

2. **Performance**
   - Dashboard load time (target: <1s)
   - Cache hit rate (target: >80%)
   - Query count per page (target: <20)

3. **Data Quality**
   - Overdue accounts count
   - Collection rate %
   - Payment processing success rate

### Audit Log Queries

```python
# Last 100 changes
AuditLog.objects.order_by('-created_at')[:100]

# Changes by specific admin
AuditLog.objects.filter(actor=request.user)

# Changes to specific record
AuditLog.objects.filter(
    model_name='payment',
    object_repr='RCPT-ABC123'
)
```

---

## Next Phases

- **Phase 3:** Academic Synchronization (Grades)
- **Phase 4:** Attendance Synchronization
- **Phase 5:** Student Profile Synchronization
- **Phase 6:** Staff Management Synchronization

Each phase follows the same pattern:
1. Service layer implementation
2. Signal-based triggers
3. Cache management
4. Background tasks
5. Comprehensive tests

