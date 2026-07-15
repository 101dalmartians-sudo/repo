from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse

from apps.grades.forms import GradeEntrySelectionForm
from apps.grades.models import Grade
from apps.grades.services import AcademicService
from apps.students.models import StudentProfile


@login_required
def index(request):
    if hasattr(request.user, 'teacher_profile'):
        return redirect('grades_entry')
    if hasattr(request.user, 'student_profile'):
        return redirect('grades_student_view')
    return redirect('accounts:accounts_home')


@login_required
def entry(request):
    if not hasattr(request.user, 'teacher_profile'):
        messages.error(request, 'Only teacher accounts may enter grades.')
        return redirect('accounts:accounts_home')

    students = StudentProfile.objects.filter(approved=True).select_related('user').order_by(
        'user__first_name', 'user__last_name', 'student_id'
    )
    selected_student = None
    selected_student_id = (request.POST.get('student_id') or request.GET.get('student_id') or '').strip()
    form = GradeEntrySelectionForm(request.POST or None)

    if selected_student_id:
        selected_student = get_object_or_404(students, pk=selected_student_id)

    if request.method == 'POST':
        if not selected_student:
            messages.error(request, 'Select a student before entering a grade.')
        elif form.is_valid():
            subject = form.cleaned_data['subject']
            term = form.cleaned_data['term']
            percentage_raw = (request.POST.get('percentage') or '').strip()

            try:
                percentage = float(percentage_raw)
            except ValueError:
                percentage = None

            if percentage is None:
                messages.error(request, 'Enter a valid percentage before saving.')
            else:
                result = AcademicService.create_or_update_grade(
                    selected_student,
                    subject,
                    percentage,
                    term,
                    user=request.user,
                )
                if result['success']:
                    messages.success(request, f'Grade saved successfully for {selected_student}.')
                    return redirect(f"{reverse('grades_entry')}?student_id={selected_student.id}")

                messages.error(request, result['message'])

    return render(request, 'grades/entry.html', {
        'form': form,
        'students': students,
        'selected_student': selected_student,
        'selected_student_id': selected_student.id if selected_student else '',
        'student_search': (request.GET.get('student_search') or '').strip(),
        'existing_grades': Grade.objects.filter(student=selected_student).order_by('term', 'subject') if selected_student else [],
    })


@login_required
def student_view(request):
    if not hasattr(request.user, 'student_profile'):
        return redirect('accounts:accounts_home')

    grades = Grade.objects.filter(student=request.user.student_profile).order_by('subject', 'term')
    average = grades.aggregate(avg=Avg('percentage'))['avg'] or 0

    return render(request, 'grades/view.html', {
        'grades': grades,
        'average': average,
    })
