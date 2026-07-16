from django import forms

from .models import HomepageInquiry


class HomepageInquiryForm(forms.ModelForm):
    class Meta:
        model = HomepageInquiry
        fields = ['full_name', 'email', 'subject', 'message']

    def clean_full_name(self):
        return self.cleaned_data['full_name'].strip()

    def clean_subject(self):
        return self.cleaned_data['subject'].strip()

    def clean_message(self):
        return self.cleaned_data['message'].strip()
