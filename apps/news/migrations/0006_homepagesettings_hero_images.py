from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0005_homepagesettings_singleton_key'),
    ]

    operations = [
        migrations.RenameField(
            model_name='homepagesettings',
            old_name='hero_image',
            new_name='hero_image_1',
        ),
        migrations.AlterField(
            model_name='homepagesettings',
            name='hero_image_1',
            field=models.ImageField('Hero Image 1', blank=True, null=True, upload_to='homepage/settings/'),
        ),
        migrations.AddField(
            model_name='homepagesettings',
            name='hero_image_2',
            field=models.ImageField('Hero Image 2', blank=True, null=True, upload_to='homepage/settings/'),
        ),
        migrations.AddField(
            model_name='homepagesettings',
            name='hero_image_3',
            field=models.ImageField('Hero Image 3', blank=True, null=True, upload_to='homepage/settings/'),
        ),
        migrations.AddField(
            model_name='homepagesettings',
            name='hero_image_4',
            field=models.ImageField('Hero Image 4', blank=True, null=True, upload_to='homepage/settings/'),
        ),
    ]