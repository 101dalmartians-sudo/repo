from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.shortcuts import render, redirect

from apps.grades.forms import GradeEntrySelectionForm
from apps.grades.models import Grade
from apps.students.models import StudentProfile


@login_required
def index(request):
    if hasattr(request.user, 'teacher_profile'):
        return redirect('grades_entry')
    if hasattr(request.user, 'student_profile'):
        return redirect('grades_student_view')
    return redirect('accounts_home')


@login_required
def entry(request):
    if not hasattr(request.user, 'teacher_profile'):
        messages.error(request, 'Only teacher accounts may enter grades.')
        return redirect('accounts_home')

    students = []
    form = GradeEntrySelectionForm(request.POST or request.GET or None)

    if request.method == 'POST':
        if form.is_valid():
            target_class = form.cleaned_data['target_class']
            subject = form.cleaned_data['subject']
            term = form.cleaned_data['term']
            student_ids = request.POST.getlist('student_id')
            percentages = request.POST.getlist('percentage')

            for student_id, percentage_raw in zip(student_ids, percentages):
                try:
                    student = StudentProfile.objects.get(pk=student_id)
                    percentage = float(percentage_raw)
                except (StudentProfile.DoesNotExist, ValueError):
                    continue

                Grade.objects.update_or_create(
                    student=student,
                    subject=subject,
                    term=term,
                    defaults={'percentage': percentage},
                )

            messages.success(request, 'Grades saved successfully.')
            return redirect('grades_entry')
    else:
        if form.is_valid() and form.cleaned_data.get('target_class'):
            students = StudentProfile.objects.filter(current_class=form.cleaned_data['target_class']).order_by('student_id')

    return render(request, 'grades/entry.html', {
        'form': form,
        'students': students,
    })


@login_required
def student_view(request):
    if not hasattr(request.user, 'student_profile'):
        return redirect('accounts_home')

    grades = Grade.objects.filter(student=request.user.student_profile).order_by('subject', 'term')
    average = grades.aggregate(avg=Avg('percentage'))['avg'] or 0

    return render(request, 'grades/view.html', {
        'grades': grades,
        'average': average,
    })
