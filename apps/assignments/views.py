from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from apps.assignments.forms import AssignmentForm
from apps.notifications.models import Notification


def notify_students_for_assignment(assignment):
    from apps.students.models import StudentProfile

    students = StudentProfile.objects.filter(current_class=assignment.target_class)
    notifications = []
    for student_profile in students:
        notifications.append(Notification(
            recipient=student_profile.user,
            title=f'New assignment: {assignment.title}',
            message=(
                f'New assignment "{assignment.title}" for {assignment.subject} '
                f'has been posted for class {assignment.target_class}. Due {assignment.due_date:%Y-%m-%d %H:%M}.'
            ),
        ))
    Notification.objects.bulk_create(notifications)


def index(request):
    return render(request, 'assignments/index.html')


@login_required
def upload_assignment(request):
    if not hasattr(request.user, 'teacher_profile'):
        messages.error(request, 'Only teacher accounts may upload assignments.')
        return redirect('accounts_home')

    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.uploaded_by = request.user.teacher_profile
            assignment.save()
            notify_students_for_assignment(assignment)
            messages.success(request, 'Assignment uploaded and notifications were created.')
            return redirect('assignment_upload')
    else:
        form = AssignmentForm()

    return render(request, 'assignments/upload.html', {'form': form})
