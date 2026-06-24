from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.grades.models import Grade
from apps.students.models import AttendanceRecord, AuditLog, ExamResult, StudentProfile

from .models import BiWeeklyReport, ReportingPeriod
from .services import BiWeeklyReportService


def _teacher_guard(request):
    return hasattr(request.user, 'teacher_profile') and request.user.teacher_profile.approved


def _admin_guard(request):
    return (
        hasattr(request.user, 'admin_profile')
        and request.user.admin_profile.approved
        and request.user.is_staff
    )


def _student_guard(request):
    return hasattr(request.user, 'student_profile') and request.user.student_profile.approved


def _compile_academic_snapshot(student, period):
    grades = Grade.objects.filter(student=student)
    if period.term:
        grades = grades.filter(term=period.term)
    grade_rows = list(
        grades.order_by('subject').values('subject', 'percentage', 'cambridge_letter_grade', 'term')
    )

    attendance = AttendanceRecord.objects.filter(
        student=student,
        date__gte=period.start_date,
        date__lte=period.end_date,
    )
    if period.term:
        attendance = attendance.filter(term=period.term)
    attendance = attendance.filter(year=period.year)
    present_count = attendance.filter(status='present').count()
    absent_count = attendance.filter(status='absent').count()
    late_count = attendance.filter(status='late').count()
    total_count = attendance.count()
    attendance_percentage = (present_count / total_count * 100) if total_count else 0

    exam_results = ExamResult.objects.select_related('exam').filter(
        student=student,
        exam__exam_date__gte=period.start_date,
        exam__exam_date__lte=period.end_date,
    ).order_by('-exam__exam_date')[:10]

    average_percentage = grades.aggregate(avg=Avg('percentage'))['avg'] or 0

    return {
        'grades': grade_rows,
        'average_percentage': float(average_percentage),
        'attendance_percentage': attendance_percentage,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'attendance_total': total_count,
        'exam_results': exam_results,
    }


def _log_report_action(actor, action, report):
    AuditLog.objects.create(
        actor=actor,
        action=action,
        model_name='biweeklyreport',
        object_repr=str(report),
        changes={
            'report_id': report.id,
            'status': report.status,
            'period': str(report.period),
            'student': str(report.student),
        },
    )


@login_required
def teacher_periods(request):
    if not _teacher_guard(request):
        raise Http404

    periods = ReportingPeriod.objects.exclude(status='archived').order_by('-year', '-start_date')
    students = StudentProfile.objects.filter(approved=True).order_by('student_id')
    my_reports = BiWeeklyReport.objects.filter(teacher=request.user).select_related('period', 'student', 'student__user')

    if request.method == 'POST':
        period_id = request.POST.get('period_id')
        student_id = request.POST.get('student_id')
        return redirect('reports:teacher_report_editor', period_id=period_id, student_id=student_id)

    context = {
        'periods': periods,
        'students': students,
        'my_reports': my_reports[:30],
    }
    return render(request, 'reports/teacher_periods.html', context)


@login_required
def teacher_report_editor(request, period_id, student_id):
    if not _teacher_guard(request):
        raise Http404

    period = get_object_or_404(ReportingPeriod, pk=period_id)
    student = get_object_or_404(StudentProfile.objects.select_related('user'), pk=student_id, approved=True)
    report, created = BiWeeklyReport.objects.get_or_create(
        period=period,
        student=student,
        defaults={
            'teacher': request.user,
            'content': {
                'strengths': '',
                'areas_for_improvement': '',
                'recommendations': '',
                'general_comments': '',
            },
            'status': 'draft',
        },
    )
    if created:
        _log_report_action(request.user, 'Bi-weekly report draft created', report)

    if report.teacher and report.teacher != request.user and not request.user.is_staff:
        raise Http404

    if request.method == 'POST':
        content = {
            'strengths': request.POST.get('strengths', '').strip(),
            'areas_for_improvement': request.POST.get('areas_for_improvement', '').strip(),
            'recommendations': request.POST.get('recommendations', '').strip(),
            'general_comments': request.POST.get('general_comments', '').strip(),
        }
        report.content = content
        report.updated_by = request.user

        action = request.POST.get('action')
        if report.status in {'approved', 'published', 'archived'}:
            messages.error(request, f'Cannot edit a report in {report.get_status_display()} state.')
            return redirect('reports:teacher_report_editor', period_id=period.id, student_id=student.id)

        report.save(update_fields=['content', 'updated_by', 'updated_at'])
        _log_report_action(request.user, 'Bi-weekly report updated', report)

        if action == 'submit':
            submit_result = BiWeeklyReportService.submit_report(report, request.user)
            if submit_result['success']:
                _log_report_action(request.user, 'Bi-weekly report submitted', report)
                messages.success(request, 'Report submitted for approval.')
                return redirect('reports:teacher_periods')
            messages.error(request, submit_result['message'])
        else:
            messages.success(request, 'Draft saved successfully.')

    academic = _compile_academic_snapshot(student, period)
    return render(
        request,
        'reports/teacher_report_editor.html',
        {
            'period': period,
            'student': student,
            'report': report,
            'academic': academic,
        },
    )


@login_required
def admin_reports_dashboard(request):
    if not _admin_guard(request):
        raise Http404

    reports = BiWeeklyReport.objects.select_related('period', 'student', 'student__user', 'teacher', 'approved_by')
    period_id = request.GET.get('period')
    status = request.GET.get('status')

    if period_id:
        reports = reports.filter(period_id=period_id)
    if status:
        reports = reports.filter(status=status)

    if request.method == 'POST':
        report = get_object_or_404(BiWeeklyReport, pk=request.POST.get('report_id'))
        action = request.POST.get('action')
        note = request.POST.get('note', '').strip()

        if action == 'approve':
            result = BiWeeklyReportService.approve_report(report, request.user, note)
            if result['success']:
                _log_report_action(request.user, 'Bi-weekly report approved', report)
                messages.success(request, 'Report approved.')
            else:
                messages.error(request, result['message'])
        elif action == 'return':
            report.status = 'draft'
            report.approval_notes = note or 'Returned for revision.'
            report.updated_by = request.user
            report.save(update_fields=['status', 'approval_notes', 'updated_by', 'updated_at'])
            BiWeeklyReportService._update_period_analytics(report.period)
            BiWeeklyReportService._invalidate_caches(report.student)
            _log_report_action(request.user, 'Bi-weekly report returned for revision', report)
            messages.success(request, 'Report returned for revision.')
        elif action == 'reject':
            report.status = 'draft'
            report.approval_notes = note or 'Rejected by admin. Update and resubmit.'
            report.updated_by = request.user
            report.save(update_fields=['status', 'approval_notes', 'updated_by', 'updated_at'])
            BiWeeklyReportService._update_period_analytics(report.period)
            BiWeeklyReportService._invalidate_caches(report.student)
            _log_report_action(request.user, 'Bi-weekly report rejected', report)
            messages.success(request, 'Report rejected and moved back to draft.')
        elif action == 'publish':
            result = BiWeeklyReportService.publish_report(report)
            if result['success']:
                _log_report_action(request.user, 'Bi-weekly report published', report)
                messages.success(request, 'Report published to student dashboard.')
            else:
                messages.error(request, result['message'])
        elif action == 'archive':
            report.archive()
            BiWeeklyReportService._update_period_analytics(report.period)
            BiWeeklyReportService._invalidate_caches(report.student)
            _log_report_action(request.user, 'Bi-weekly report archived', report)
            messages.success(request, 'Report archived.')

        return redirect('reports:admin_reports_dashboard')

    periods = ReportingPeriod.objects.order_by('-year', '-start_date')
    metrics = BiWeeklyReportService.get_admin_metrics()
    context = {
        'reports': reports.order_by('-updated_at')[:100],
        'periods': periods,
        'selected_period': period_id,
        'selected_status': status,
        'metrics': metrics,
    }
    return render(request, 'reports/admin_reports_dashboard.html', context)


@login_required
def student_reports(request):
    if not _student_guard(request):
        raise Http404

    student = request.user.student_profile
    reports = student.bi_weekly_reports.filter(status='published').select_related('period', 'teacher', 'approved_by')

    # Lightweight end-of-term summary from existing grades (no duplicate storage).
    term_summary = defaultdict(lambda: {'total': 0, 'sum': 0.0})
    for grade in Grade.objects.filter(student=student):
        term_summary[grade.term]['total'] += 1
        term_summary[grade.term]['sum'] += float(grade.percentage)

    end_of_term_reports = []
    for term, data in term_summary.items():
        average = (data['sum'] / data['total']) if data['total'] else 0
        end_of_term_reports.append({'term': term, 'average': average, 'subjects': data['total']})

    context = {
        'reports': reports.order_by('-published_at'),
        'end_of_term_reports': sorted(end_of_term_reports, key=lambda item: item['term']),
        'student_metrics': BiWeeklyReportService.get_student_metrics(student),
    }
    return render(request, 'reports/student_reports.html', context)


@login_required
def student_report_detail(request, report_id):
    if not _student_guard(request):
        raise Http404

    report = get_object_or_404(
        BiWeeklyReport.objects.select_related('period', 'teacher', 'approved_by', 'student', 'student__user'),
        pk=report_id,
        student=request.user.student_profile,
        status='published',
    )
    academic = _compile_academic_snapshot(report.student, report.period)
    return render(request, 'reports/student_report_detail.html', {'report': report, 'academic': academic, 'print_mode': False})


@login_required
def student_report_print(request, report_id):
    if not _student_guard(request):
        raise Http404

    report = get_object_or_404(
        BiWeeklyReport.objects.select_related('period', 'teacher', 'approved_by', 'student', 'student__user'),
        pk=report_id,
        student=request.user.student_profile,
        status='published',
    )
    academic = _compile_academic_snapshot(report.student, report.period)
    return render(request, 'reports/student_report_detail.html', {'report': report, 'academic': academic, 'print_mode': True})


@login_required
def student_report_download(request, report_id):
    if not _student_guard(request):
        raise Http404

    report = get_object_or_404(
        BiWeeklyReport.objects.select_related('period', 'teacher', 'approved_by', 'student', 'student__user'),
        pk=report_id,
        student=request.user.student_profile,
        status='published',
    )
    academic = _compile_academic_snapshot(report.student, report.period)

    lines = [
        f"Aspire Academy Bi-Weekly Report",
        f"Student: {report.student}",
        f"Period: {report.period.name} ({report.period.start_date} to {report.period.end_date})",
        f"Teacher: {report.teacher.get_full_name() if report.teacher else '-'}",
        f"Published: {report.published_at}",
        '',
        'Academic Performance',
        f"Average Percentage: {academic['average_percentage']:.2f}",
    ]
    for grade in academic['grades']:
        lines.append(
            f"- {grade['subject']}: {grade['percentage']}% ({grade['cambridge_letter_grade']})"
        )

    lines.extend([
        '',
        'Attendance',
        f"Attendance %: {academic['attendance_percentage']:.2f}",
        f"Present: {academic['present_count']}",
        f"Absent: {academic['absent_count']}",
        f"Late: {academic['late_count']}",
        '',
        'Teacher Commentary',
        f"Strengths: {report.content.get('strengths', '')}",
        f"Areas For Improvement: {report.content.get('areas_for_improvement', '')}",
        f"Recommendations: {report.content.get('recommendations', '')}",
        f"General Comments: {report.content.get('general_comments', '')}",
        '',
        'Approval',
        f"Approved By: {report.approved_by}",
        f"Approved At: {report.approved_at}",
    ])

    response = HttpResponse('\n'.join(lines), content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename=bi-weekly-report-{report.id}.txt'
    return responsefrom django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.students.models import AuditLog
from .forms import TeacherReportContentForm, TeacherStudentSelectForm
from .models import BiWeeklyReport, ReportingPeriod
from .services import BiWeeklyReportService


COMMENTARY_KEYS = [
    'strengths',
    'areas_for_improvement',
    'recommendations',
    'general_comments',
]


def _is_teacher(user):
    return hasattr(user, 'teacher_profile') and user.teacher_profile.approved


def _is_admin(user):
    return hasattr(user, 'admin_profile') and user.admin_profile.approved and user.is_staff


def _audit(user, action, report, extra=None):
    AuditLog.objects.create(
        actor=user,
        action=action,
        model_name='biweeklyreport',
        object_repr=str(report),
        changes=extra or {},
    )


@login_required
def teacher_periods(request):
    if not _is_teacher(request.user):
        raise Http404

    periods = ReportingPeriod.objects.exclude(status='archived').order_by('-year', 'start_date')
    report_qs = BiWeeklyReport.objects.filter(teacher=request.user)
    metrics = {
        'draft': report_qs.filter(status='draft').count(),
        'submitted': report_qs.filter(status='submitted').count(),
        'approved': report_qs.filter(status='approved').count(),
        'published': report_qs.filter(status='published').count(),
        'archived': report_qs.filter(status='archived').count(),
    }

    return render(request, 'reports/teacher_periods.html', {
        'periods': periods,
        'metrics': metrics,
        'active_reports_tab': 'periods',
    })


@login_required
def teacher_report_editor(request, period_id):
    if not _is_teacher(request.user):
        raise Http404

    period = get_object_or_404(ReportingPeriod, pk=period_id)

    student_form = TeacherStudentSelectForm(request.GET or None)
    selected_student = None
    report = None
    report_form = None
    snapshot = None

    student_id = request.GET.get('student') or request.POST.get('student')
    if student_id:
        selected_student = get_object_or_404(student_form.fields['student'].queryset, pk=student_id)
        report, _ = BiWeeklyReport.objects.get_or_create(
            period=period,
            student=selected_student,
            defaults={
                'teacher': request.user,
                'content': {},
                'status': 'draft',
            },
        )

        if report.teacher and report.teacher != request.user and not _is_admin(request.user):
            raise Http404

        snapshot = BiWeeklyReportService.build_student_academic_snapshot(selected_student, period)

        initial = {key: report.content.get(key, '') for key in COMMENTARY_KEYS}
        report_form = TeacherReportContentForm(request.POST or None, initial=initial)

        if request.method == 'POST' and report_form.is_valid():
            if period.status != 'open' and report.status == 'draft':
                messages.error(request, 'This reporting period is not open for draft updates.')
                return redirect('reports:teacher_report_editor', period_id=period.id)

            report.content = {
                **report.content,
                **{key: report_form.cleaned_data.get(key, '').strip() for key in COMMENTARY_KEYS},
            }
            report.updated_by = request.user
            report.teacher = report.teacher or request.user
            report.save(update_fields=['content', 'updated_by', 'teacher', 'updated_at'])

            action = request.POST.get('action')
            if action == 'submit':
                submit_result = BiWeeklyReportService.submit_report(report, request.user)
                if submit_result['success']:
                    _audit(request.user, 'Report submitted', report, {'period_id': period.id})
                    messages.success(request, 'Report submitted for admin review.')
                else:
                    messages.error(request, submit_result['message'])
            else:
                _audit(request.user, 'Report draft updated', report, {'period_id': period.id})
                messages.success(request, 'Draft saved successfully.')

            cache.delete(f'teacher_reporting_dashboard_{request.user.id}')
            return redirect(f"{request.path}?student={selected_student.id}")

    return render(request, 'reports/teacher_report_editor.html', {
        'period': period,
        'student_form': student_form,
        'selected_student': selected_student,
        'report': report,
        'report_form': report_form,
        'snapshot': snapshot,
        'active_reports_tab': 'edit',
    })


@login_required
def admin_report_queue(request):
    if not _is_admin(request.user):
        raise Http404

    reports = BiWeeklyReport.objects.select_related(
        'student', 'student__user', 'teacher', 'period', 'approved_by'
    ).order_by('-updated_at')

    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        reports = reports.filter(status=status_filter)

    reports_outstanding = reports.filter(status__in=['draft', 'submitted', 'approved']).count()
    metrics = {
        'drafted': BiWeeklyReport.objects.filter(status='draft').count(),
        'submitted': BiWeeklyReport.objects.filter(status='submitted').count(),
        'approved': BiWeeklyReport.objects.filter(status='approved').count(),
        'published': BiWeeklyReport.objects.filter(status='published').count(),
        'outstanding': reports_outstanding,
    }

    return render(request, 'reports/admin_queue.html', {
        'reports': reports,
        'metrics': metrics,
        'status_filter': status_filter,
        'active_reports_tab': 'admin',
    })


@login_required
def admin_report_review(request, report_id):
    if not _is_admin(request.user):
        raise Http404

    report = get_object_or_404(
        BiWeeklyReport.objects.select_related('student', 'student__user', 'teacher', 'period', 'approved_by'),
        pk=report_id,
    )
    snapshot = BiWeeklyReportService.build_student_academic_snapshot(report.student, report.period)

    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('approval_notes', '').strip()

        if action == 'approve':
            result = BiWeeklyReportService.approve_report(report, request.user, notes)
            if result['success']:
                _audit(request.user, 'Report approved', report, {'notes': notes})
                messages.success(request, 'Report approved.')
            else:
                messages.error(request, result['message'])

        elif action == 'return_revision':
            report.status = 'draft'
            report.approval_notes = notes
            report.approved_at = None
            report.approved_by = None
            report.save(update_fields=['status', 'approval_notes', 'approved_at', 'approved_by', 'updated_at'])
            _audit(request.user, 'Report returned for revision', report, {'notes': notes})
            messages.success(request, 'Report returned to draft for teacher revision.')

        elif action == 'reject':
            report.status = 'archived'
            report.approval_notes = notes or 'Rejected by admin.'
            report.approved_at = timezone.now()
            report.approved_by = request.user
            report.save(update_fields=['status', 'approval_notes', 'approved_at', 'approved_by', 'updated_at'])
            _audit(request.user, 'Report rejected', report, {'notes': report.approval_notes})
            messages.success(request, 'Report rejected and archived.')

        elif action == 'publish':
            result = BiWeeklyReportService.publish_report(report)
            if result['success']:
                _audit(request.user, 'Report published', report)
                messages.success(request, 'Report published to student dashboard.')
            else:
                messages.error(request, result['message'])

        elif action == 'archive':
            report.archive()
            _audit(request.user, 'Report archived', report)
            messages.success(request, 'Report archived.')

        return redirect('reports:admin_report_review', report_id=report.id)

    return render(request, 'reports/admin_review.html', {
        'report': report,
        'snapshot': snapshot,
        'active_reports_tab': 'admin',
    })


@login_required
def student_reports(request):
    if not hasattr(request.user, 'student_profile'):
        raise Http404

    student = request.user.student_profile
    reports = student.bi_weekly_reports.filter(status='published').select_related(
        'period', 'teacher', 'approved_by'
    ).order_by('-period__start_date')

    metrics = {
        'available': reports.count(),
    }

    return render(request, 'reports/student_reports.html', {
        'reports': reports,
        'metrics': metrics,
        'active_reports_tab': 'student',
    })


@login_required
def report_detail(request, report_id):
    report = get_object_or_404(
        BiWeeklyReport.objects.select_related('student', 'student__user', 'teacher', 'period', 'approved_by'),
        pk=report_id,
    )

    if _is_admin(request.user):
        pass
    elif _is_teacher(request.user):
        if report.teacher != request.user:
            raise Http404
    elif hasattr(request.user, 'student_profile'):
        if report.student != request.user.student_profile or report.status != 'published':
            raise Http404
    else:
        raise Http404

    snapshot = BiWeeklyReportService.build_student_academic_snapshot(report.student, report.period)

    return render(request, 'reports/report_detail.html', {
        'report': report,
        'snapshot': snapshot,
    })


@login_required
def report_print(request, report_id):
    response = report_detail(request, report_id)
    response['X-Frame-Options'] = 'SAMEORIGIN'
    return response


@login_required
def report_download(request, report_id):
    report = get_object_or_404(BiWeeklyReport, pk=report_id)

    if hasattr(request.user, 'student_profile'):
        if report.student != request.user.student_profile or report.status != 'published':
            raise Http404
    elif _is_teacher(request.user):
        if report.teacher != request.user:
            raise Http404
    elif not _is_admin(request.user):
        raise Http404

    snapshot = BiWeeklyReportService.build_student_academic_snapshot(report.student, report.period)

    lines = [
        f"Bi-Weekly Progress Report - {report.period.name}",
        f"Student: {report.student}",
        f"Teacher: {report.teacher.get_full_name() if report.teacher else '-'}",
        f"Status: {report.status}",
        f"Published At: {report.published_at or '-'}",
        '',
        'Academic Performance',
    ]

    for grade in snapshot['grades']:
        lines.append(
            f"- {grade['subject']}: {grade['percentage']}% ({grade['cambridge_letter_grade']})"
        )

    attendance = snapshot['attendance']
    lines.extend([
        '',
        'Attendance',
        f"- Attendance %: {attendance['percentage']}",
        f"- Present: {attendance['present']}",
        f"- Absent: {attendance['absent']}",
        f"- Late: {attendance['late']}",
        '',
        'Teacher Commentary',
        f"- Strengths: {report.content.get('strengths', '')}",
        f"- Areas For Improvement: {report.content.get('areas_for_improvement', '')}",
        f"- Recommendations: {report.content.get('recommendations', '')}",
        f"- General Comments: {report.content.get('general_comments', '')}",
    ])

    content = '\n'.join(lines)
    filename = f"biweekly-report-{report.id}.txt"
    http_response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    http_response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return http_response
