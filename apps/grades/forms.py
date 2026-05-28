from django import forms


class GradeEntrySelectionForm(forms.Form):
    field_class = 'mt-2 w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/20'

    subject = forms.CharField(
        max_length=128,
        widget=forms.TextInput(attrs={
            'placeholder': 'Subject',
            'class': field_class,
        })
    )
    term = forms.CharField(
        max_length=32,
        widget=forms.TextInput(attrs={
            'placeholder': 'Term',
            'class': field_class,
        })
    )
    target_class = forms.CharField(
        max_length=64,
        widget=forms.TextInput(attrs={
            'placeholder': 'Class stream',
            'class': field_class,
        })
    )
