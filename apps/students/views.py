from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from apps.assignments.models import Assignment
from apps.notifications.models import Notification
from apps.news.models import News
from apps.grades.models import Grade
from .models import (
    StudentProfile,
    FinancialRecord,
    Payment,
    AttendanceRecord,
    ExamSchedule,
    ExamResult,
)


@login_required
def dashboard(request):
    if not hasattr(request.user, 'student_profile'):
        return redirect('accounts:accounts_home')

    profile = request.user.student_profile
    assignments = Assignment.objects.filter(target_class=profile.current_class).order_by('due_date')[:10]
    notifications = Notification.objects.filter(recipient=request.user).order_by('-timestamp')[:5]
    news = News.objects.all().order_by('-created_at')[:5]
    overdue_records = FinancialRecord.objects.filter(
        student=profile,
        due_date__lt=timezone.now().date()
    ).exclude(
        transport_balance=0,
        tuition_balance=0
    )
    upcoming_exams = ExamSchedule.objects.filter(exam_date__gte=timezone.now().date()).order_by('exam_date')[:3]

    return render(request, 'students/dashboard.html', {
        'assignments': assignments,
        'notifications': notifications,
        'news': news,
        'overdue_records': overdue_records,
        'upcoming_exams': upcoming_exams,
    })


@login_required
def profile_detail(request):
    if not hasattr(request.user, 'student_profile'):
        return redirect('accounts:accounts_home')
    
    profile = request.user.student_profile
    term_filter = request.GET.get('term')
    year_filter = request.GET.get('year')
    status_filter = request.GET.get('status')

    financial_records = FinancialRecord.objects.filter(student=profile).order_by('-year', 'term')
    if term_filter:
        financial_records = financial_records.filter(term=term_filter)
    if year_filter:
        financial_records = financial_records.filter(year=year_filter)
    if status_filter == 'overdue':
        financial_records = financial_records.filter(
            due_date__lt=timezone.now().date()
        ).exclude(
            transport_balance=0,
            tuition_balance=0
        )
    elif status_filter == 'balanced':
        financial_records = financial_records.filter(
            transport_balance=0,
            tuition_balance=0
        )

    payments = Payment.objects.filter(student=profile).order_by('-payment_date')[:10]
    attendance_queryset = AttendanceRecord.objects.filter(student=profile).order_by('-date')
    attendance = attendance_queryset[:10]
    exams = ExamSchedule.objects.order_by('exam_date')[:10]
    grades = Grade.objects.filter(student=profile).order_by('term', 'subject')
    average_grade = grades.aggregate(avg=Avg('percentage'))['avg'] or Decimal('0.00')
    attendance_summary = {
        'present': attendance_queryset.filter(status='present').count(),
        'absent': attendance_queryset.filter(status='absent').count(),
        'late': attendance_queryset.filter(status='late').count(),
    }
    student_summary = profile.get_balance_summary()
    term_summaries = profile.get_term_summaries()

    return render(request, 'students/profile_detail.html', {
        'profile': profile,
        'financial_records': financial_records,
        'payments': payments,
        'attendance_records': attendance,
        'exams': exams,
        'grades': grades,
        'average_grade': average_grade,
        'attendance_summary': attendance_summary,
        'student_summary': student_summary,
        'term_summaries': term_summaries,
        'filter_term': term_filter,
        'filter_year': year_filter,
        'filter_status': status_filter,
    })


@login_required
def payment_receipt(request, receipt_number):
    payment = get_object_or_404(
        Payment,
        receipt_number=receipt_number,
        student__user=request.user
    )
    return render(request, 'students/payment_receipt.html', {
        'payment': payment,
        'profile': payment.student,
    })
