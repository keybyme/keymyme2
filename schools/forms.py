from django import forms

from vault.forms import TailwindFormMixin

from .models import AmMidPmEntry, Employee, Route, School


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
        fields = ["route_number", "bus_number", "driver", "attendant"]


class AmMidPmEntryForm(TailwindFormMixin, forms.ModelForm):
    """`route` is exposed as a free-text field with a `<datalist>` (rendered
    by the view/template, id="mcps-routes-datalist") instead of a plain
    `<select>`, so the user can start typing a route number and quickly pick
    a match from the existing MCPS Routes catalog."""

    route = forms.CharField(
        label="Route",
        widget=forms.TextInput(attrs={"list": "mcps-routes-datalist", "autocomplete": "off", "placeholder": "Start typing a route number…"}),
        help_text="Must match an existing MCPS Route number.",
    )

    class Meta:
        model = AmMidPmEntry
        fields = ["route", "type", "seq", "time", "address", "next"]
        widgets = {
            "time": forms.TimeInput(attrs={"type": "time"}),
            "next": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.route_id:
            self.fields["route"].initial = self.instance.route.route_number

    def clean_route(self):
        route_number = self.cleaned_data["route"].strip()
        try:
            return Route.objects.get(route_number__iexact=route_number)
        except Route.DoesNotExist:
            raise forms.ValidationError("No MCPS Route matches that route number. Pick one from the list.")
