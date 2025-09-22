from django import forms
from .models import StudentInfo


class  StudentInfoForm(forms.ModelForm):
    class Meta:
        model = StudentInfo
        fields = ['student_id', 'name', 'email', 'phone', 'staff']