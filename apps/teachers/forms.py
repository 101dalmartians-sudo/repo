from django import forms


class AttendanceWorkspaceForm(forms.Form):
    field_class = (
        'mt-2 w-full rounded-2xl border border-slate-300 bg-slate-50 '
        'px-4 py-3 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/20'
    )

    title = forms.CharField(max_length=120, widget=forms.TextInput(attrs={'class': field_class}))
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': field_class}))
    term = forms.CharField(max_length=32, widget=forms.TextInput(attrs={'class': field_class, 'placeholder': 'Term 2'}))
    year = forms.IntegerField(widget=forms.NumberInput(attrs={'class': field_class, 'min': 2020, 'max': 2100}))
    class_stream = forms.CharField(max_length=64, widget=forms.TextInput(attrs={'class': field_class, 'placeholder': 'Grade 6A'}))
    subject = forms.CharField(max_length=128, required=False, widget=forms.TextInput(attrs={'class': field_class, 'placeholder': 'Optional subject'}))


class ExamScheduleWorkspaceForm(forms.Form):
    field_class = AttendanceWorkspaceForm.field_class

    exam_name = forms.CharField(max_length=128, widget=forms.TextInput(attrs={'class': field_class}))
    subject = forms.CharField(max_length=128, widget=forms.TextInput(attrs={'class': field_class}))
    class_stream = forms.CharField(max_length=64, widget=forms.TextInput(attrs={'class': field_class}))
    term = forms.CharField(max_length=32, widget=forms.TextInput(attrs={'class': field_class, 'placeholder': 'Term 2'}))
    year = forms.IntegerField(widget=forms.NumberInput(attrs={'class': field_class, 'min': 2020, 'max': 2100}))
    exam_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': field_class}))
    instructions = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3, 'class': field_class}))
