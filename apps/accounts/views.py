from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.models import User


from decimal import Decimal

from django.db.models import F, Q, Sum
from django.utils import timezone

from apps.students.models import StudentProfile, FinancialRecord, Payment, AttendanceRecord
from apps.teachers.models import TeacherProfile
from apps.notifications.models import Notification
from apps.news.models import News, GalleryImage, HomePageContactSection
from apps.grades.models import Grade


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts_home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('accounts_home')
        messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def home(request):
    # Public landing page for unauthenticated users
    if not request.user.is_authenticated:
        news = News.objects.all().order_by('-created_at')[:5]
        gallery_images = GalleryImage.objects.filter(active=True).order_by('order', '-created_at')[:8]
        contact_section = HomePageContactSection.objects.first() or HomePageContactSection()
        return render(request, 'home.html', {
            'news': news,
            'gallery_images': gallery_images,
            'contact_section': contact_section,
            'notifications_count': 0,
        })

    # Authenticated users: route to their dashboards
    profile = None
    role = None
    if hasattr(request.user, 'student_profile'):
        profile = request.user.student_profile
        role = 'student'
    elif hasattr(request.user, 'teacher_profile'):
        profile = request.user.teacher_profile
        role = 'teacher'
    elif hasattr(request.user, 'admin_profile'):
        profile = request.user.admin_profile
        role = 'admin'
    else:
        return render(request, 'accounts/unknown_role.html')

    # require admin approval (email verification removed; approval alone is sufficient)
    if not getattr(profile, 'approved', False):
        return render(request, 'accounts/approval_pending.html')

    if role == 'student':
        return redirect('students_dashboard')
    if role == 'teacher':
        return redirect('teachers_dashboard')
    return redirect('admin_dashboard')


@login_required
def admin_dashboard(request):
    if not hasattr(request.user, 'admin_profile'):
        return redirect('accounts_home')

    admin_profile = request.user.admin_profile
    if not admin_profile.approved:
        return redirect('accounts_home')

    total_students = StudentProfile.objects.filter(approved=True).count()
    total_fees_collected = Payment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    outstanding_records = FinancialRecord.objects.filter(Q(transport_balance__gt=0) | Q(tuition_balance__gt=0))
    total_outstanding = outstanding_records.aggregate(total=Sum(F('transport_balance') + F('tuition_balance')))['total'] or Decimal('0.00')
    term_income = FinancialRecord.objects.values('term', 'year').annotate(
        total_paid=Sum(F('transport_paid') + F('tuition_paid'))
    ).order_by('-year', 'term')[:6]
    attendance_rate = AttendanceRecord.objects.filter(status='present').count()
    attendance_total = AttendanceRecord.objects.count() or 1
    attendance_percentage = (attendance_rate / attendance_total) * 100 if attendance_total else 0
    overdue_accounts = outstanding_records.filter(due_date__lt=timezone.now().date()).count()

    return render(request, 'accounts/admin_dashboard.html', {
        'admin_profile': admin_profile,
        'notifications': Notification.objects.filter(recipient=request.user).order_by('-timestamp')[:10],
        'total_students': total_students,
        'total_fees_collected': total_fees_collected,
        'total_outstanding': total_outstanding,
        'term_income': term_income,
        'attendance_percentage': attendance_percentage,
        'overdue_accounts': overdue_accounts,
    })


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('accounts_home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role')

        if not username or not password or not role:
            messages.error(request, 'Please fill all required fields.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
        else:
            user = User.objects.create_user(username=username, password=password, email=email)
            if role == 'student':
                student_id = request.POST.get('student_id', '') or f"S{user.id:04d}"
                current_class = request.POST.get('current_class', '')
                StudentProfile.objects.create(user=user, student_id=student_id, current_class=current_class)
            elif role == 'teacher':
                department = request.POST.get('department', '')
                TeacherProfile.objects.create(user=user, department=department)
            else:  # admin
                from .models import AdminProfile
                approved_admins = AdminProfile.objects.filter(approved=True).count()
                if approved_admins >= 10:
                    messages.error(request, 'Maximum number of admins reached. Cannot register new admin.')
                    user.delete()
                    return render(request, 'accounts/signup.html')

                if approved_admins < 5:
                    AdminProfile.objects.create(user=user, approved=True, email_verified=True)
                    user.is_staff = True
                    user.is_superuser = True
                    user.save()
                else:
                    AdminProfile.objects.create(user=user)
            # skip email verification flow; new accounts await admin approval if not auto-approved
            return redirect('accounts_home')

    return render(request, 'accounts/signup.html')

# Verification endpoints removed; admin approval is now the only acceptance step.


@login_required
def admin_approvals(request):
    # simple admin approvals page that lists pending admin profiles for approval
    if not request.user.is_staff:
        return redirect('accounts_home')

    from .models import AdminProfile
    pending = AdminProfile.objects.filter(approved=False)
    if request.method == 'POST':
        action = request.POST.get('action')
        profile_id = request.POST.get('profile_id')
        try:
            ap = AdminProfile.objects.get(pk=profile_id)
        except AdminProfile.DoesNotExist:
            ap = None
        if ap and action == 'approve':
            # enforce max 10 admins
            if AdminProfile.objects.filter(approved=True).count() >= 10:
                messages.error(request, 'Cannot approve: admin limit reached.')
            else:
                ap.approved = True
                # automatically mark email as verified at approval (verification flow removed)
                ap.email_verified = True
                ap.user.is_staff = True
                ap.user.is_superuser = True
                ap.user.save()
                ap.save()
                messages.success(request, f'Approved {ap.user.username}')
        elif ap and action == 'reject':
            ap.user.delete()
            messages.success(request, 'Rejected and removed account.')

    return render(request, 'accounts/admin_approvals.html', {'pending': pending})


@login_required
def manage_profiles(request):
    # allow admins to view and approve/reject student and teacher profiles
    if not request.user.is_staff:
        return redirect('accounts_home')

    pending_students = StudentProfile.objects.filter(approved=False)
    pending_teachers = TeacherProfile.objects.filter(approved=False)

    if request.method == 'POST':
        action = request.POST.get('action')
        profile_type = request.POST.get('type')
        profile_id = request.POST.get('profile_id')

        if profile_type == 'student':
            try:
                prof = StudentProfile.objects.get(pk=profile_id)
            except StudentProfile.DoesNotExist:
                prof = None
        else:
            try:
                prof = TeacherProfile.objects.get(pk=profile_id)
            except TeacherProfile.DoesNotExist:
                prof = None

        if prof and action == 'approve':
            prof.approved = True
            prof.email_verified = True
            prof.save()
            # notify all approved admins
            from .models import AdminProfile
            admins = AdminProfile.objects.filter(approved=True)
            for a in admins:
                Notification.objects.create(
                    recipient=a.user,
                    title=f"Approved {prof.user.username}",
                    message=f"{request.user.username} approved {prof.user.username} ({profile_type}).",
                )
            messages.success(request, f'Approved {prof.user.username}')
        elif prof and action == 'reject':
            username = prof.user.username
            prof.user.delete()
            from .models import AdminProfile
            admins = AdminProfile.objects.filter(approved=True)
            for a in admins:
                Notification.objects.create(
                    recipient=a.user,
                    title=f"Rejected {username}",
                    message=f"{request.user.username} rejected and removed {username} ({profile_type}).",
                )
            messages.success(request, f'Rejected and removed {username}')

        return redirect('manage_profiles')

    return render(request, 'accounts/manage_profiles.html', {
        'pending_students': pending_students,
        'pending_teachers': pending_teachers,
    })


@login_required
def edit_profile(request, profile_type, profile_id):
    if not request.user.is_staff:
        return redirect('accounts_home')

    if profile_type == 'student':
        try:
            prof = StudentProfile.objects.get(pk=profile_id)
        except StudentProfile.DoesNotExist:
            return redirect('manage_profiles')
    else:
        try:
            prof = TeacherProfile.objects.get(pk=profile_id)
        except TeacherProfile.DoesNotExist:
            return redirect('manage_profiles')

    if request.method == 'POST':
        # allow editing simple fields
        if profile_type == 'student':
            prof.student_id = request.POST.get('student_id', prof.student_id)
            prof.current_class = request.POST.get('current_class', prof.current_class)
        else:
            prof.department = request.POST.get('department', prof.department)
            prof.work_email = request.POST.get('work_email', prof.work_email)
            prof.phone_number = request.POST.get('phone_number', prof.phone_number)
        
        # handle profile picture upload
        if 'profile_picture' in request.FILES:
            prof.profile_picture = request.FILES['profile_picture']
        
        prof.save()

        # notify admins of edit
        from .models import AdminProfile
        admins = AdminProfile.objects.filter(approved=True)
        for a in admins:
            Notification.objects.create(
                recipient=a.user,
                title=f"Edited {prof.user.username}",
                message=f"{request.user.username} edited {prof.user.username} ({profile_type}).",
            )

        messages.success(request, 'Profile updated')
        return redirect('manage_profiles')

    return render(request, 'accounts/edit_profile.html', {'profile': prof, 'type': profile_type})
