from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from apps.students.models import Payment


def current_year():
    return timezone.now().year


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Expense categories'

    def __str__(self):
        return self.name


class Budget(models.Model):
    PERIOD_ANNUAL = 'annual'
    PERIOD_MONTHLY = 'monthly'
    PERIOD_CHOICES = [
        (PERIOD_ANNUAL, 'Annual'),
        (PERIOD_MONTHLY, 'Monthly'),
    ]

    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name='budgets')
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    year = models.PositiveIntegerField(default=current_year)
    month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_budgets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', 'month', 'category__name']
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'period_type', 'year', 'month'],
                name='unique_budget_per_period',
            ),
        ]

    def __str__(self):
        if self.period_type == self.PERIOD_MONTHLY and self.month:
            return f'{self.category} budget - {self.year}-{self.month:02d}'
        return f'{self.category} budget - {self.year}'

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.period_type == self.PERIOD_MONTHLY and not self.month:
            raise ValidationError({'month': 'Month is required for monthly budgets.'})
        if self.period_type == self.PERIOD_ANNUAL:
            self.month = None

    @property
    def expenses_total(self):
        filters = {'category': self.category, 'date__year': self.year}
        if self.period_type == self.PERIOD_MONTHLY and self.month:
            filters['date__month'] = self.month
        return self.category.expenses.filter(**filters).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    @property
    def remaining_budget(self):
        return self.amount - self.expenses_total

    @property
    def utilization_percentage(self):
        if not self.amount:
            return Decimal('0.00')
        return (self.expenses_total / self.amount) * Decimal('100')

    @property
    def status(self):
        percentage = self.utilization_percentage
        if percentage > 100:
            return 'Over Budget'
        if percentage >= 96:
            return 'Critical'
        if percentage >= 81:
            return 'Warning'
        return 'On Track'


class Expense(models.Model):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    date = models.DateField(default=timezone.now)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    receipt = models.FileField(upload_to='finance/receipts/', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_expenses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.category} - {self.amount} on {self.date}'


class Income(models.Model):
    SOURCE_SCHOOL_FEES = 'school_fees'
    SOURCE_REGISTRATION = 'registration_fees'
    SOURCE_EXAMINATION = 'examination_fees'
    SOURCE_OTHER = 'other_income'
    SOURCE_CHOICES = [
        (SOURCE_SCHOOL_FEES, 'School Fees'),
        (SOURCE_REGISTRATION, 'Registration Fees'),
        (SOURCE_EXAMINATION, 'Examination Fees'),
        (SOURCE_OTHER, 'Other Income'),
    ]

    source = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    date = models.DateField(default=timezone.now)
    description = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_incomes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.get_source_display()} - {self.amount} on {self.date}'


class MonthlyFinancialReport(models.Model):
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    generated_at = models.DateTimeField(auto_now=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_financial_reports')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-year', '-month']
        unique_together = ('year', 'month')

    def __str__(self):
        return f'Financial report {self.year}-{self.month:02d}'

    @property
    def total_income(self):
        manual_income = Income.objects.filter(
            date__year=self.year,
            date__month=self.month,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        school_fees = Payment.objects.filter(
            payment_date__year=self.year,
            payment_date__month=self.month,
            is_approved=True,
            status='approved',
            is_reversed=False,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        return manual_income + school_fees

    @property
    def total_expenses(self):
        return Expense.objects.filter(date__year=self.year, date__month=self.month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    @property
    def net_profit_loss(self):
        return self.total_income - self.total_expenses

    @property
    def budget_utilization_percentage(self):
        total_budget = Budget.objects.filter(year=self.year, month=self.month, period_type=Budget.PERIOD_MONTHLY).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        if total_budget == 0:
            return Decimal('0.00')
        return (self.total_expenses / total_budget) * Decimal('100')
