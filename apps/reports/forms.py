from django import forms

from apps.students.models import StudentProfile

from .models import ReportingPeriod


class TeacherReportContentForm(forms.Form):
    field_class = 'w-full rounded-2xl border border-slate-300 px-4 py-3 text-sm text-slate-900 focus:border-academy focus:outline-none focus:ring-2 focus:ring-rose-100'

    strengths = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': field_class}),
        required=False,
        label='Strengths',
    )
    areas_for_improvement = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': field_class}),
        required=False,
        label='Areas For Improvement',
    )
    recommendations = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': field_class}),
        required=False,
        label='Recommendations',
    )
    general_comments = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': field_class}),
        required=False,
        label='General Comments',
    )


class TeacherStudentSelectForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=StudentProfile.objects.none(),
        widget=forms.Select(attrs={'class': TeacherReportContentForm.field_class}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = StudentProfile.objects.filter(approved=True).select_related('user').order_by('student_id')


class TeacherStudentMultiSelectForm(forms.Form):
    students = forms.ModelMultipleChoiceField(
        queryset=StudentProfile.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': TeacherReportContentForm.field_class}),
    )

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop('queryset', None)
        super().__init__(*args, **kwargs)
        self.fields['students'].queryset = queryset or StudentProfile.objects.filter(approved=True).select_related('user').order_by('student_id')


class ReportingPeriodManageForm(forms.ModelForm):
    class Meta:
        model = ReportingPeriod
        fields = [
            'name',
            'reporting_type',
            'term',
            'year',
            'start_date',
            'end_date',
            'submission_opens',
            'submission_deadline',
            'approval_deadline',
            'publish_date',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': TeacherReportContentForm.field_class}),
            'reporting_type': forms.Select(attrs={'class': TeacherReportContentForm.field_class}),
            'term': forms.Select(attrs={'class': TeacherReportContentForm.field_class}),
            'year': forms.NumberInput(attrs={'class': TeacherReportContentForm.field_class, 'min': 2020, 'max': 2100}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': TeacherReportContentForm.field_class}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': TeacherReportContentForm.field_class}),
            'submission_opens': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': TeacherReportContentForm.field_class}),
            'submission_deadline': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': TeacherReportContentForm.field_class}),
            'approval_deadline': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': TeacherReportContentForm.field_class}),
            'publish_date': forms.DateInput(attrs={'type': 'date', 'class': TeacherReportContentForm.field_class}),
        }
