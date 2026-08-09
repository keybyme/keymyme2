from django import forms

from vault.forms import TailwindFormMixin

from .models import Employee, Route, School


class SchoolForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = School
        fields = ["name", "school_type", "address", "city", "zip_code"]


class EmployeeForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["name", "phone", "position"]


class RouteForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Route
        fields = ["route_number", "bus_number", "route_type", "driver", "attendant", "stop_number", "seq", "address"]
