from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
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
def download_attachment(request, assignment_id):
    from apps.assignments.models import Assignment

    assignment = Assignment.objects.select_related('uploaded_by').filter(id=assignment_id).first()
    if not assignment:
        raise Http404('Assignment not found.')

    if hasattr(request.user, 'student_profile'):
        if assignment.target_class != request.user.student_profile.current_class:
            raise PermissionDenied('You do not have access to this attachment.')
    elif hasattr(request.user, 'teacher_profile'):
        if assignment.uploaded_by_id != request.user.teacher_profile.id:
            raise PermissionDenied('You do not have access to this attachment.')
    elif not request.user.is_staff:
        raise PermissionDenied('You do not have access to this attachment.')

    if not assignment.file_attachment:
        raise Http404('Attachment not found.')

    try:
        file_handle = assignment.file_attachment.open('rb')
    except FileNotFoundError as exc:
        raise Http404('Attachment file missing from storage.') from exc

    filename = assignment.attachment_filename
    content_type = assignment.attachment_content_type
    force_download = request.GET.get('download') == '1'
    can_inline = content_type == 'application/pdf' or content_type.startswith('image/')
    as_attachment = force_download or not can_inline
    return FileResponse(
        file_handle,
        as_attachment=as_attachment,
        filename=filename,
        content_type=content_type,
    )


@login_required
def upload_assignment(request):
    if not hasattr(request.user, 'teacher_profile'):
        messages.error(request, 'Only teacher accounts may upload assignments.')
        return redirect('accounts:accounts_home')

    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.uploaded_by = request.user.teacher_profile
            uploaded_file = request.FILES.get('file_attachment')
            if uploaded_file:
                assignment.original_filename = uploaded_file.name
                assignment.file_content_type = uploaded_file.content_type or ''
                assignment.file_size = uploaded_file.size
            assignment.save()
            notify_students_for_assignment(assignment)
            messages.success(request, 'Assignment uploaded and notifications were created.')
            return redirect('assignment_upload')
    else:
        form = AssignmentForm()

    return render(request, 'assignments/upload.html', {'form': form})
