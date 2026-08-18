from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):
    dependencies = [
        ('students', '0008_attendancerecord_recorded_by_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TermInvoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(default='Next term fees', max_length=160)),
                ('term', models.CharField(choices=[('term1', 'Term 1'), ('term2', 'Term 2'), ('term3', 'Term 3')], max_length=10)),
                ('year', models.PositiveIntegerField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('due_date', models.DateField(blank=True, null=True)),
                ('description', models.TextField(blank=True)),
                ('is_published', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_term_invoices', to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='term_invoices', to='students.studentprofile')),
            ],
            options={'ordering': ['-year', 'term', 'student__student_id']},
        ),
    ]