from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404
from django.shortcuts import render, redirect
from django.utils import timezone

from apps.assignments.forms import AssignmentForm
from apps.assignments.models import Assignment
from apps.news.models import News
from apps.reports.services import BiWeeklyReportService
from apps.students.models import AttendanceSession, ExamSchedule

from .forms import AttendanceWorkspaceForm, ExamScheduleWorkspaceForm
from .selectors import get_filtered_students
from .services import TeacherWorkspaceService


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
        'attendance_sessions_count': AttendanceSession.objects.filter(teacher=request.user).count(),
        'upcoming_exam_count': ExamSchedule.objects.filter(created_by=request.user, exam_date__gte=timezone.now().date()).count(),
    })


@login_required
def attendance_workspace(request):
    if not hasattr(request.user, 'teacher_profile'):
        raise Http404

    attendance_form = AttendanceWorkspaceForm(request.POST or None)
    students = get_filtered_students(request.GET)
    sessions = AttendanceSession.objects.filter(teacher=request.user).order_by('-date', '-created_at')[:20]

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_session':
            if attendance_form.is_valid():
                session = TeacherWorkspaceService.create_attendance_session(
                    teacher=request.user,
                    title=attendance_form.cleaned_data['title'],
                    date=attendance_form.cleaned_data['date'],
                    term=attendance_form.cleaned_data['term'],
                    year=attendance_form.cleaned_data['year'],
                    class_stream=attendance_form.cleaned_data['class_stream'],
                    subject=attendance_form.cleaned_data['subject'],
                )
                messages.success(request, f'Attendance session "{session.title}" created.')
                return redirect('teachers_attendance_workspace')
            messages.error(request, 'Please correct the attendance session form.')

        elif action == 'save_attendance':
            session = AttendanceSession.objects.filter(pk=request.POST.get('session_id'), teacher=request.user).first()
            if not session:
                messages.error(request, 'Select a valid attendance session.')
                return redirect('teachers_attendance_workspace')

            selected_students = request.POST.getlist('selected_students')
            entries = []
            for student_id in selected_students:
                status = request.POST.get(f'status_{student_id}', 'present')
                note = request.POST.get(f'note_{student_id}', '').strip()
                entries.append({'student_id': student_id, 'status': status, 'note': note})

            if not entries:
                messages.error(request, 'Select at least one student for attendance.')
                return redirect('teachers_attendance_workspace')

            TeacherWorkspaceService.save_attendance(
                teacher=request.user,
                session=session,
                entries=entries,
            )
            messages.success(request, f'Attendance saved for {len(entries)} student(s).')
            return redirect('teachers_attendance_workspace')

    return render(request, 'teachers/attendance_workspace.html', {
        'attendance_form': attendance_form,
        'students': students[:200],
        'sessions': sessions,
        'filters': {
            'search': (request.GET.get('search') or '').strip(),
            'grade': (request.GET.get('grade') or '').strip(),
            'class_stream': (request.GET.get('class_stream') or '').strip(),
            'subject_filter': (request.GET.get('subject_filter') or '').strip(),
        },
    })


@login_required
def exams_workspace(request):
    if not hasattr(request.user, 'teacher_profile'):
        raise Http404

    exam_form = ExamScheduleWorkspaceForm(request.POST or None)
    exams = ExamSchedule.objects.filter(created_by=request.user).order_by('-exam_date', '-created_at')[:30]

    if request.method == 'POST' and request.POST.get('action') == 'create_exam':
        if exam_form.is_valid():
            exam = TeacherWorkspaceService.create_exam(
                teacher=request.user,
                exam_name=exam_form.cleaned_data['exam_name'],
                subject=exam_form.cleaned_data['subject'],
                class_stream=exam_form.cleaned_data['class_stream'],
                term=exam_form.cleaned_data['term'],
                year=exam_form.cleaned_data['year'],
                exam_date=exam_form.cleaned_data['exam_date'],
                instructions=exam_form.cleaned_data['instructions'],
            )
            messages.success(request, f'Exam "{exam.exam_name or exam.subject}" scheduled and published.')
            return redirect('teachers_exams_workspace')
        messages.error(request, 'Please correct the exam form fields.')

    return render(request, 'teachers/exams_workspace.html', {
        'exam_form': exam_form,
        'exams': exams,
    })


@login_required
def exam_results_workspace(request, exam_id):
    if not hasattr(request.user, 'teacher_profile'):
        raise Http404

    exam = ExamSchedule.objects.filter(pk=exam_id, created_by=request.user).first()
    if not exam:
        raise Http404

    selector_params = request.GET.copy()
    selector_params.setdefault('class_stream', exam.target_class)
    selector_params.setdefault('subject_filter', exam.subject)
    students = get_filtered_students(selector_params)

    if request.method == 'POST' and request.POST.get('action') == 'save_results':
        selected_students = request.POST.getlist('selected_students')
        entries = []
        for student_id in selected_students:
            score_raw = (request.POST.get(f'score_{student_id}') or '').strip()
            if not score_raw:
                continue
            comment = request.POST.get(f'comment_{student_id}', '').strip()
            entries.append({'student_id': student_id, 'score': score_raw, 'comments': comment})

        if not entries:
            messages.error(request, 'Enter at least one score before saving exam results.')
            return redirect('teachers_exam_results_workspace', exam_id=exam.id)

        TeacherWorkspaceService.save_exam_results(
            teacher=request.user,
            exam=exam,
            entries=entries,
        )
        messages.success(request, f'Exam results saved for {len(entries)} student(s).')
        return redirect('teachers_exam_results_workspace', exam_id=exam.id)

    return render(request, 'teachers/exam_results_workspace.html', {
        'exam': exam,
        'students': students[:200],
    })


@login_required
def learning_resources(request):
    if not hasattr(request.user, 'teacher_profile'):
        raise Http404

    return render(request, 'teachers/learning_resources.html')
