from django import forms

from apps.students.models import StudentProfile


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
