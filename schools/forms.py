from django import forms

from vault.forms import TailwindFormMixin

from .models import School


class SchoolForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = School
        fields = ["name", "school_type", "address", "city", "zip_code"]
