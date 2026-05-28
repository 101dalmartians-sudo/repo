from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Notification


@login_required
def index(request):
    # show current user's notifications
    notes = Notification.objects.filter(recipient=request.user).order_by('-timestamp')
    return render(request, 'notifications/index.html', {'notifications': notes})
