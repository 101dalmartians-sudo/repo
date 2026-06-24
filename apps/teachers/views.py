from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from apps.assignments.forms import AssignmentForm
from apps.assignments.models import Assignment
from apps.news.models import News
from apps.reports.services import BiWeeklyReportService


@login_required
def dashboard(request):
    if not hasattr(request.user, 'teacher_profile'):
        return redirect('accounts:accounts_home')

    teacher_profile = request.user.teacher_profile
    assignments = teacher_profile.assignments.order_by('-created_at')[:5]
    news = News.objects.all().order_by('-created_at')[:5]

    return render(request, 'teachers/dashboard.html', {
        'assignments': assignments,
        'form': AssignmentForm(),
        'news': news,
        'report_metrics': BiWeeklyReportService.get_teacher_metrics(request.user),
    })
