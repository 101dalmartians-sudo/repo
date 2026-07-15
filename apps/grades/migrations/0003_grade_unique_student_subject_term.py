from django.db import migrations, models


def deduplicate_grades(apps, schema_editor):
    Grade = apps.get_model('grades', 'Grade')

    duplicate_keys = (
        Grade.objects.values('student_id', 'subject', 'term')
        .annotate(record_count=models.Count('id'))
        .filter(record_count__gt=1)
    )

    for key in duplicate_keys.iterator():
        duplicates = Grade.objects.filter(
            student_id=key['student_id'],
            subject=key['subject'],
            term=key['term'],
        ).order_by('-id')

        keeper = duplicates.first()
        if keeper is None:
            continue

        duplicates.exclude(id=keeper.id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('grades', '0002_alter_grade_cambridge_letter_grade'),
    ]

    operations = [
        migrations.RunPython(deduplicate_grades, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='grade',
            constraint=models.UniqueConstraint(
                fields=('student', 'subject', 'term'),
                name='unique_grade_per_student_subject_term',
            ),
        ),
    ]