from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from apps.assignments.models import Assignment
from apps.notifications.models import Notification
from apps.news.models import News


@login_required
def dashboard(request):
    if not hasattr(request.user, 'student_profile'):
        return redirect('accounts_home')

    profile = request.user.student_profile
    assignments = Assignment.objects.filter(target_class=profile.current_class).order_by('due_date')[:10]
    notifications = Notification.objects.filter(recipient=request.user).order_by('-timestamp')[:5]
    news = News.objects.all().order_by('-created_at')[:5]

    return render(request, 'students/dashboard.html', {
        'assignments': assignments,
        'notifications': notifications,
        'news': news,
    })
