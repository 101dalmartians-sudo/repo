from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import AdminProfile
from apps.students.models import StudentProfile
from apps.teachers.models import TeacherProfile


class AccountsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='student1', password='password123')

    def test_login_page_loads(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Login')

    def test_login_invalid(self):
        response = self.client.post(reverse('accounts:login'), {'username': 'student1', 'password': 'wrong'})
        self.assertContains(response, 'Invalid username or password.')

    def test_authenticated_redirects_home(self):
        self.client.login(username='student1', password='password123')
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 302)

    def test_signup_student_creates_profile_and_sends_email(self):
        response = self.client.post(
            reverse('accounts:signup'),
            {
                'username': 'student2',
                'password': 'password456',
                'email': 'student2@example.com',
                'role': 'student',
                'student_id': 'S002',
                'current_class': 'Form 1',
            },
        )
        user = User.objects.get(username='student2')
        self.assertTrue(hasattr(user, 'student_profile'))
        self.assertEqual(user.student_profile.student_id, 'S002')
        # email verification flow removed; no verification email should be sent
        self.assertEqual(len(mail.outbox), 0)

    # email verification endpoints are deprecated in this flow; tests removed

    def test_signup_admin_auto_approves_first_five(self):
        for i in range(4):
            response = self.client.post(
                reverse('accounts:signup'),
                {
                    'username': f'admin{i}',
                    'password': 'password123',
                    'email': f'admin{i}@example.com',
                    'role': 'admin',
                },
            )
            self.assertEqual(response.status_code, 302)
            admin_user = User.objects.get(username=f'admin{i}')
            self.assertTrue(admin_user.is_staff)
            self.assertTrue(admin_user.is_superuser)
            self.assertTrue(admin_user.admin_profile.approved)

        response = self.client.post(
            reverse('accounts:signup'),
            {
                'username': 'admin4',
                'password': 'password123',
                'email': 'admin4@example.com',
                'role': 'admin',
            },
        )
        admin_user = User.objects.get(username='admin4')
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.admin_profile.approved)

        response = self.client.post(
            reverse('accounts:signup'),
            {
                'username': 'admin5',
                'password': 'password123',
                'email': 'admin5@example.com',
                'role': 'admin',
            },
        )
        admin_user = User.objects.get(username='admin5')
        self.assertFalse(admin_user.is_staff)
        self.assertFalse(admin_user.is_superuser)
        self.assertFalse(admin_user.admin_profile.approved)

    def test_signup_admin_rejects_when_admin_limit_reached(self):
        for i in range(10):
            admin_user = User.objects.create_user(
                username=f'admin{i}',
                password='password123',
                email=f'admin{i}@example.com',
            )
            AdminProfile.objects.create(user=admin_user, email_verified=True, approved=True)

        response = self.client.post(
            reverse('accounts:signup'),
            {
                'username': 'admin_new',
                'password': 'password456',
                'email': 'admin_new@example.com',
                'role': 'admin',
            },
        )

        self.assertContains(response, 'Maximum number of admins reached')
        self.assertFalse(User.objects.filter(username='admin_new').exists())

    def test_admin_approvals_promotes_admin_to_superuser(self):
        admin_user = User.objects.create_superuser(username='superadmin', email='superadmin@example.com', password='password123')
        AdminProfile.objects.create(user=admin_user, email_verified=True, approved=True)
        self.client.login(username='superadmin', password='password123')

        pending_user = User.objects.create_user(username='pendingadmin', password='password123', email='pending@example.com')
        pending_profile = AdminProfile.objects.create(user=pending_user, email_verified=True, approved=False)

        response = self.client.post(
            reverse('accounts:admin_approvals'),
            {'action': 'approve', 'profile_id': str(pending_profile.id)},
            follow=True,
        )

        self.assertContains(response, 'Approved pendingadmin')
        pending_user.refresh_from_db()
        pending_profile.refresh_from_db()
        self.assertTrue(pending_user.is_superuser)
        self.assertTrue(pending_user.is_staff)
        self.assertTrue(pending_profile.approved)

    def test_admin_home_is_not_blocked_by_missing_student_or_teacher_profile(self):
        user = User.objects.create_user(username='admin1', password='password123')
        AdminProfile.objects.create(user=user, approved=True)
        self.client.login(username='admin1', password='password123')

        response = self.client.get(reverse('accounts:accounts_home'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('accounts:admin_dashboard'))

    def test_admin_dashboard_page_renders(self):
        user = User.objects.create_user(username='admin3', password='password123')
        AdminProfile.objects.create(user=user, approved=True)
        self.client.login(username='admin3', password='password123')

        response = self.client.get(reverse('accounts:admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin dashboard')

    def test_admin_pending_approval_shows_pending_page(self):
        user = User.objects.create_user(username='admin2', password='password123')
        AdminProfile.objects.create(user=user, approved=False)
        self.client.login(username='admin2', password='password123')

        response = self.client.get(reverse('accounts:accounts_home'))
        self.assertContains(response, 'Awaiting admin approval')

    def test_home_requires_email_verification_and_admin_approval(self):
        user = User.objects.create_user(username='student4', password='password123', email='student4@example.com')
        profile = StudentProfile.objects.create(user=user, student_id='S004', current_class='Form 3')
        self.client.login(username='student4', password='password123')
        response = self.client.get(reverse('accounts:accounts_home'))
        # email verification removed; account awaits admin approval
        self.assertContains(response, 'Awaiting admin approval')
