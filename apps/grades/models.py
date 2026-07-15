from django.db import models


class Grade(models.Model):
    student = models.ForeignKey(
        'students.StudentProfile',
        on_delete=models.CASCADE,
        related_name='grades'
    )
    subject = models.CharField(max_length=128)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    cambridge_letter_grade = models.CharField(max_length=4, blank=True)
    term = models.CharField(max_length=32)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'subject', 'term'],
                name='unique_grade_per_student_subject_term',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.percentage is not None:
            self.cambridge_letter_grade = self.calculate_cambridge_grade(self.percentage)
        super().save(*args, **kwargs)

    @staticmethod
    def calculate_cambridge_grade(value):
        try:
            percentage = float(value)
        except (TypeError, ValueError):
            return ''

        if percentage >= 80:
            return 'A*'
        if percentage >= 70:
            return 'A'
        if percentage >= 60:
            return 'B'
        if percentage >= 50:
            return 'C'
        if percentage >= 40:
            return 'D'
        return 'U'

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.percentage})"
