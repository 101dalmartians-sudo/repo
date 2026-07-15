from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.shortcuts import render, redirect

from apps.grades.forms import GradeEntrySelectionForm
from apps.grades.models import Grade
from apps.students.models import StudentProfile
from apps.teachers.selectors import get_filtered_students


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

    students = []
    form = GradeEntrySelectionForm(request.POST or request.GET or None)

    if request.method == 'POST':
        if form.is_valid():
            subject = form.cleaned_data['subject']
            term = form.cleaned_data['term']
            selected_students = request.POST.getlist('selected_students')
            saved_count = 0

            if selected_students:
                for student_id in selected_students:
                    percentage_raw = request.POST.get(f'percentage_{student_id}', '').strip()
                    if not percentage_raw:
                        continue
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
                    saved_count += 1
            else:
                # Backward compatibility for previous payload shape.
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
                    saved_count += 1

            messages.success(request, f'Grades saved successfully for {saved_count} student(s).')
            return redirect('grades_entry')
    else:
        if form.is_valid():
            should_load = request.GET.get('load') == '1' or bool(request.GET)
            if should_load:
                students = get_filtered_students(request.GET)[:250]

    return render(request, 'grades/entry.html', {
        'form': form,
        'students': students,
        'filters': {
            'search': (request.GET.get('search') or '').strip(),
            'grade': (request.GET.get('grade') or '').strip(),
            'class_stream': (request.GET.get('class_stream') or '').strip(),
            'subject_filter': (request.GET.get('subject_filter') or '').strip(),
        },
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
