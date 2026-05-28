from django.contrib.auth.models import User
from django.test import TestCase

from apps.students.models import StudentProfile
from .models import Grade


class GradeModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='student1', password='password123')
        self.student_profile = StudentProfile.objects.create(
            user=user,
            student_id='S001',
            current_class='Form 1'
        )

    def test_grade_calculation_a_star(self):
        grade = Grade(percentage=85, subject='Math', term='Term 1', student=self.student_profile)
        self.assertEqual(grade.calculate_cambridge_grade(grade.percentage), 'A*')

    def test_grade_calculation_c(self):
        self.assertEqual(Grade.calculate_cambridge_grade(52), 'C')
        self.assertEqual(Grade.calculate_cambridge_grade(49.9), 'D')

    def test_save_sets_letter_grade(self):
        grade = Grade(subject='Science', term='Term 2', percentage=76, student=self.student_profile)
        grade.save()
        self.assertEqual(grade.cambridge_letter_grade, 'A')
