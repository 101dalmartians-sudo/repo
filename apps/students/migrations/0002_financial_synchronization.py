# Generated migration for Financial Record and Payment model enhancements

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0005_payment_attendance_exams_auditlog'),
    ]

    operations = [
        # Add fields to FinancialRecord
        migrations.AddField(
            model_name='financialrecord',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('partial', 'Partially Paid'),
                    ('paid', 'Fully Paid'),
                    ('overdue', 'Overdue'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='financialrecord',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='updated_financial_records',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='financialrecord',
            name='last_payment_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='financialrecord',
            name='payment_count',
            field=models.PositiveIntegerField(default=0),
        ),
        
        # Add fields to Payment
        migrations.AddField(
            model_name='payment',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending Approval'),
                    ('approved', 'Approved'),
                    ('reversed', 'Reversed'),
                ],
                default='approved',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='payment',
            name='is_approved',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='approved_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='approved_payments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='payment',
            name='approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='reversal_of',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reversals',
                to='students.payment',
            ),
        ),
        migrations.AddField(
            model_name='payment',
            name='is_reversed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='payment',
            name='reversal_reason',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='payment',
            name='reversed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='reversed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reversed_payments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
