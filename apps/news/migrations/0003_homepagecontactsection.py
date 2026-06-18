from django.db import migrations, models


def create_default_contact_section(apps, schema_editor):
    HomePageContactSection = apps.get_model('news', 'HomePageContactSection')
    if not HomePageContactSection.objects.exists():
        HomePageContactSection.objects.create()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0002_galleryimage'),
    ]

    operations = [
        migrations.CreateModel(
            name='HomePageContactSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('section_title', models.CharField(default='Contact our team', max_length=150)),
                (
                    'introductory_text',
                    models.TextField(
                        default='Questions, feedback, or partnership requests? We typically respond within 24 business hours.'
                    ),
                ),
                ('phone_number', models.CharField(default='+1 (234) 567-890', max_length=50)),
                ('email_address', models.EmailField(default='info@aspireacademy.com', max_length=254)),
                ('physical_address', models.TextField(default='145 Aspire Lane, Cityview, State 54321')),
                ('availability_hours', models.CharField(default='Mon - Fri: 8:00 AM - 5:00 PM', max_length=150)),
                ('form_heading', models.CharField(default='Start your inquiry', max_length=150)),
                ('form_description', models.TextField(default='Share your details and our team will get back to you soon.')),
            ],
            options={
                'verbose_name': 'Home Page Contact Section',
                'verbose_name_plural': 'Home Page Contact Section',
            },
        ),
        migrations.RunPython(create_default_contact_section, noop_reverse),
    ]
