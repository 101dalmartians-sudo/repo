from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assignments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='assignment',
            name='file_content_type',
            field=models.CharField(blank=True, max_length=127),
        ),
        migrations.AddField(
            model_name='assignment',
            name='file_size',
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='assignment',
            name='original_filename',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
