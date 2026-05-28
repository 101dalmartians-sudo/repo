from django import forms

from .models import Assignment


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'subject', 'target_class', 'due_date', 'file_attachment']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'mt-2 w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/20',
            }),
            'subject': forms.TextInput(attrs={
                'class': 'mt-2 w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/20',
            }),
            'target_class': forms.TextInput(attrs={
                'class': 'mt-2 w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/20',
            }),
            'due_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'mt-2 w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/20',
            }),
            'file_attachment': forms.ClearableFileInput(attrs={
                'class': 'mt-2 w-full text-slate-700',
            }),
        }
