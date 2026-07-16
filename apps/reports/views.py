from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.grades.models import Grade
from apps.grades.services import AcademicService
from apps.students.models import AttendanceRecord, AuditLog, ExamResult, StudentProfile
from apps.teachers.selectors import get_filtered_students

from .forms import ReportingPeriodManageForm
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


def _report_content_defaults():
    return {
        'strengths': '',
        'areas_for_improvement': '',
        'recommendations': '',
        'general_comments': '',
        'additional_comments': '',
        'selected_subjects': [],
        'subject_comments': {},
        'draft_academic_entries': {},
        'grading_format': 'percentage',
        'custom_grading_scale': '',
    }


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_grade_term(student, subject, period, draft_entry):
    if period.term:
        return period.term

    draft_term = (draft_entry or {}).get('term')
    if draft_term:
        return str(draft_term).strip()

    existing = Grade.objects.filter(student=student, subject=subject).order_by('-id').first()
    if existing and existing.term:
        return existing.term
    return ''


def _get_subject_rows(report, academic):
    content = _report_content_defaults()
    content.update(report.content or {})

    selected_subjects = content.get('selected_subjects') or []
    selected_set = set(selected_subjects)
    subject_comments = content.get('subject_comments') or {}

    grade_rows = []
    for grade in academic['grades']:
        subject_name = grade['subject']
        if selected_set and subject_name not in selected_set:
            continue

        row = dict(grade)
        row['comment'] = subject_comments.get(subject_name, '')
        grade_rows.append(row)

    if not selected_subjects:
        return grade_rows, content

    ordered_rows = []
    for subject_name in selected_subjects:
        for row in grade_rows:
            if row['subject'] == subject_name:
                ordered_rows.append(row)
                break
    return ordered_rows, content


def _get_academic_editor_rows(report, academic):
    content = _report_content_defaults()
    content.update(report.content or {})

    official_rows = {row['subject']: dict(row) for row in academic['grades']}
    subject_comments = content.get('subject_comments') or {}
    selected_subjects = set(content.get('selected_subjects') or [])
    draft_entries = content.get('draft_academic_entries') or {}

    rows = []
    all_subjects = set(official_rows.keys()) | set(draft_entries.keys())
    for subject_name in sorted(all_subjects):
        official = official_rows.get(subject_name, {})
        draft = draft_entries.get(subject_name, {})

        percentage = draft.get('percentage', official.get('percentage'))
        percentage_float = _safe_float(percentage)

        if report.status == 'draft':
            display_grade = Grade.calculate_cambridge_grade(percentage_float) if percentage_float is not None else ''
        else:
            display_grade = official.get('cambridge_letter_grade', '')

        row = {
            'subject': subject_name,
            'percentage': '' if percentage is None else str(percentage),
            'term': draft.get('term', official.get('term', '')),
            'cambridge_letter_grade': display_grade,
            'comment': subject_comments.get(subject_name, ''),
            'selected': subject_name in selected_subjects if selected_subjects else True,
            'is_official': subject_name in official_rows,
        }
        rows.append(row)

    if not rows and report.status == 'draft':
        rows.append({
            'subject': '',
            'percentage': '',
            'term': '',
            'cambridge_letter_grade': '',
            'comment': '',
            'selected': True,
            'is_official': False,
        })

    return rows, content


def _collect_draft_academic_from_request(request, report):
    rows = []
    selected_subjects = []
    subject_comments = {}
    draft_entries = {}

    row_count = int(request.POST.get('academic_row_count', '0') or 0)
    for idx in range(row_count):
        subject = (request.POST.get(f'academic_subject_{idx}') or '').strip()
        percentage_raw = (request.POST.get(f'academic_percentage_{idx}') or '').strip()
        term = (request.POST.get(f'academic_term_{idx}') or '').strip()
        comment = request.POST.get(f'academic_comment_{idx}', '').strip()
        included = request.POST.get(f'academic_include_{idx}') == 'on'

        if not subject:
            continue

        subject_comments[subject] = comment
        if included:
            selected_subjects.append(subject)

        percentage = _safe_float(percentage_raw) if percentage_raw else None
        if percentage is not None:
            draft_entries[subject] = {
                'percentage': percentage,
                'term': term,
            }

        row = {
            'subject': subject,
            'percentage': percentage_raw,
            'term': term,
            'comment': comment,
            'selected': included,
            'cambridge_letter_grade': Grade.calculate_cambridge_grade(percentage) if percentage is not None else '',
            'is_official': False,
        }
        rows.append(row)

    content = {
        'selected_subjects': selected_subjects,
        'subject_comments': subject_comments,
        'draft_academic_entries': draft_entries,
    }
    return rows, content


def _promote_draft_grades(report, student, period, actor):
    content = _report_content_defaults()
    content.update(report.content or {})
    draft_entries = content.get('draft_academic_entries') or {}

    for subject, entry in draft_entries.items():
        percentage = _safe_float(entry.get('percentage'))
        if percentage is None:
            continue

        term = _resolve_grade_term(student, subject, period, entry)
        if not term:
            return {
                'success': False,
                'message': (
                    f'Cannot submit report. No term is available for subject "{subject}". '
                    'Set a reporting period term or enter/update this subject in an existing term first.'
                ),
            }

        result = AcademicService.create_or_update_grade(
            student,
            subject,
            percentage,
            term,
            user=actor,
        )
        if not result['success']:
            return {
                'success': False,
                'message': result['message'],
            }

        draft_entries[subject]['term'] = term

    report.content = content
    report.save(update_fields=['content', 'updated_at'])
    return {'success': True}


def _get_editor_subject_rows(report, academic):
    _, content = _get_subject_rows(report, academic)
    subject_comments = content.get('subject_comments') or {}

    rows = []
    selected_subjects = set(content.get('selected_subjects') or [])
    for grade in academic['grades']:
        row = dict(grade)
        row['comment'] = subject_comments.get(row['subject'], '')
        row['selected'] = row['subject'] in selected_subjects if selected_subjects else True
        rows.append(row)
    return rows


@login_required
def teacher_periods(request):
    if not _teacher_guard(request):
        raise Http404

    periods = ReportingPeriod.objects.exclude(status='archived').order_by('-year', '-start_date')
    students = get_filtered_students(request.GET)
    my_reports = BiWeeklyReport.objects.filter(teacher=request.user).select_related('period', 'student', 'student__user')
    period_form = ReportingPeriodManageForm(prefix='period')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_period':
            period_form = ReportingPeriodManageForm(request.POST, prefix='period')
            if period_form.is_valid():
                period = period_form.save(commit=False)
                period.created_by = request.user
                period.last_edited_by = request.user
                period.status = 'closed'
                period.save()
                messages.success(request, 'Reporting period created as draft.')
                return redirect('reports:teacher_periods')
            messages.error(request, 'Please correct the reporting period form errors.')

        elif action in {'publish_period', 'archive_period'}:
            period = get_object_or_404(ReportingPeriod, pk=request.POST.get('period_id'))
            if action == 'publish_period':
                period.is_published = True
                period.status = 'open'
                period.publish_date = period.publish_date or timezone.now().date()
                period.last_edited_by = request.user
                period.save(update_fields=['is_published', 'status', 'publish_date', 'last_edited_by', 'updated_at'])
                messages.success(request, 'Reporting period published.')
            else:
                period.status = 'archived'
                period.last_edited_by = request.user
                period.save(update_fields=['status', 'last_edited_by', 'updated_at'])
                messages.success(request, 'Reporting period archived.')
            return redirect('reports:teacher_periods')

        else:
            period_id = request.POST.get('period_id')
            selected_students = request.POST.getlist('selected_students')
            if not selected_students and request.POST.get('student_id'):
                selected_students = [request.POST.get('student_id')]

            if not period_id or not selected_students:
                messages.error(request, 'Select a reporting period and at least one student.')
                return redirect('reports:teacher_periods')

            first_student = None
            period = get_object_or_404(ReportingPeriod, pk=period_id)
            for student_id in selected_students:
                student = get_object_or_404(StudentProfile, pk=student_id, approved=True)
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
                if first_student is None:
                    first_student = student

            messages.success(request, f'Report workspace prepared for {len(selected_students)} student(s).')
            return redirect('reports:teacher_report_editor', period_id=period.id, student_id=first_student.id)

    report_status_groups = {
        'drafts': my_reports.filter(status='draft')[:10],
        'published': my_reports.filter(status='published')[:10],
        'history': my_reports.exclude(status='draft')[:10],
    }

    context = {
        'periods': periods,
        'students': students[:200],
        'my_reports': my_reports[:30],
        'report_status_groups': report_status_groups,
        'period_form': period_form,
        'filters': {
            'search': (request.GET.get('search') or '').strip(),
            'grade': (request.GET.get('grade') or '').strip(),
            'class_stream': (request.GET.get('class_stream') or '').strip(),
            'subject_filter': (request.GET.get('subject_filter') or '').strip(),
        },
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
            'content': _report_content_defaults(),
            'status': 'draft',
        },
    )
    if created:
        _log_report_action(request.user, 'Bi-weekly report draft created', report)

    if report.teacher and report.teacher != request.user and not request.user.is_staff:
        raise Http404

    academic = _compile_academic_snapshot(student, period)
    subject_rows, content = _get_subject_rows(report, academic)
    editor_subject_rows, editor_content = _get_academic_editor_rows(report, academic)
    available_subjects = [grade['subject'] for grade in academic['grades']]

    if request.method == 'POST':
        if report.status == 'draft':
            editor_subject_rows, academic_content = _collect_draft_academic_from_request(request, report)
        else:
            existing_content = _report_content_defaults()
            existing_content.update(report.content or {})
            academic_content = {
                'selected_subjects': existing_content.get('selected_subjects', []),
                'subject_comments': existing_content.get('subject_comments', {}),
                'draft_academic_entries': existing_content.get('draft_academic_entries', {}),
            }

        content = {
            'strengths': request.POST.get('strengths', '').strip(),
            'areas_for_improvement': request.POST.get('areas_for_improvement', '').strip(),
            'recommendations': request.POST.get('recommendations', '').strip(),
            'general_comments': request.POST.get('general_comments', '').strip(),
            'additional_comments': request.POST.get('additional_comments', '').strip(),
            'selected_subjects': academic_content['selected_subjects'],
            'subject_comments': academic_content['subject_comments'],
            'draft_academic_entries': academic_content['draft_academic_entries'],
            'grading_format': request.POST.get('grading_format', 'percentage').strip() or 'percentage',
            'custom_grading_scale': request.POST.get('custom_grading_scale', '').strip(),
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
            promote_result = _promote_draft_grades(report, student, period, request.user)
            if not promote_result['success']:
                messages.error(request, promote_result['message'])
                return redirect('reports:teacher_report_editor', period_id=period.id, student_id=student.id)

            submit_result = BiWeeklyReportService.submit_report(report, request.user)
            if submit_result['success']:
                _log_report_action(request.user, 'Bi-weekly report submitted', report)
                messages.success(request, 'Report submitted for approval.')
                return redirect('reports:teacher_periods')
            messages.error(request, submit_result['message'])
        else:
            messages.success(request, 'Draft saved successfully.')

        academic = _compile_academic_snapshot(student, period)
        subject_rows, content = _get_subject_rows(report, academic)
        editor_subject_rows, editor_content = _get_academic_editor_rows(report, academic)

    return render(
        request,
        'reports/teacher_report_editor.html',
        {
            'period': period,
            'student': student,
            'report': report,
            'academic': academic,
            'subject_rows': subject_rows,
            'editor_subject_rows': editor_subject_rows,
            'report_content': content,
            'editor_content': editor_content,
            'available_subjects': available_subjects,
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
        if request.POST.get('scope') == 'period':
            period = get_object_or_404(ReportingPeriod, pk=request.POST.get('period_id'))
            period_action = request.POST.get('period_action')

            if period_action == 'publish':
                period.is_published = True
                period.status = 'open'
                period.publish_date = period.publish_date or timezone.now().date()
                period.last_edited_by = request.user
                period.save(update_fields=['is_published', 'status', 'publish_date', 'last_edited_by', 'updated_at'])
                messages.success(request, 'Reporting period published.')
            elif period_action == 'unpublish':
                period.is_published = False
                if period.status != 'archived':
                    period.status = 'closed'
                period.last_edited_by = request.user
                period.save(update_fields=['is_published', 'status', 'last_edited_by', 'updated_at'])
                messages.success(request, 'Reporting period unpublished.')
            elif period_action == 'archive':
                period.status = 'archived'
                period.last_edited_by = request.user
                period.save(update_fields=['status', 'last_edited_by', 'updated_at'])
                messages.success(request, 'Reporting period archived.')
            elif period_action == 'delete':
                period.delete()
                messages.success(request, 'Reporting period deleted.')

            return redirect('reports:admin_reports_dashboard')

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
    subject_rows, report_content = _get_subject_rows(report, academic)
    return render(request, 'reports/student_report_detail.html', {
        'report': report,
        'academic': academic,
        'subject_rows': subject_rows,
        'report_content': report_content,
        'print_mode': False,
    })


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
    subject_rows, report_content = _get_subject_rows(report, academic)
    return render(request, 'reports/student_report_detail.html', {
        'report': report,
        'academic': academic,
        'subject_rows': subject_rows,
        'report_content': report_content,
        'print_mode': True,
    })


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
    subject_rows, report_content = _get_subject_rows(report, academic)

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
    for grade in subject_rows:
        line = f"- {grade['subject']}: {grade['percentage']}% ({grade['cambridge_letter_grade']})"
        if grade['comment']:
            line = f"{line} | Comment: {grade['comment']}"
        lines.append(line)

    lines.extend([
        '',
        'Attendance',
        f"Attendance %: {academic['attendance_percentage']:.2f}",
        f"Present: {academic['present_count']}",
        f"Absent: {academic['absent_count']}",
        f"Late: {academic['late_count']}",
        '',
        'Teacher Commentary',
        f"Strengths: {report_content.get('strengths', '')}",
        f"Areas For Improvement: {report_content.get('areas_for_improvement', '')}",
        f"Recommendations: {report_content.get('recommendations', '')}",
        f"General Comments: {report_content.get('general_comments', '')}",
        f"Additional Comments: {report_content.get('additional_comments', '')}",
        '',
        'Approval',
        f"Approved By: {report.approved_by}",
        f"Approved At: {report.approved_at}",
    ])

    response = HttpResponse('\n'.join(lines), content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename=bi-weekly-report-{report.id}.txt'
    return response


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
def legacy_student_reports(request):
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
