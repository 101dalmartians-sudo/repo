from django.db.models import Q

from apps.students.models import StudentProfile


def get_filtered_students(params):
    """Shared, reusable student selector for teacher workflows."""
    queryset = StudentProfile.objects.filter(approved=True).select_related('user')

    search = (params.get('search') or '').strip()
    grade = (params.get('grade') or '').strip()
    class_stream = (params.get('class_stream') or '').strip()
    subject = (params.get('subject_filter') or params.get('subject') or '').strip()

    if search:
        queryset = queryset.filter(
            Q(student_id__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__username__icontains=search)
        )

    if grade:
        queryset = queryset.filter(current_class__icontains=grade)

    if class_stream:
        queryset = queryset.filter(current_class__icontains=class_stream)

    if subject:
        queryset = queryset.filter(grades__subject__icontains=subject).distinct()

    return queryset.order_by('student_id')
