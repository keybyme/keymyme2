import re
from datetime import time

from django import forms

from vault.forms import TailwindFormMixin

from .models import AmMidPmEntry, Employee, LeftRight, Route, School

MINUTES_SECONDS_RE = re.compile(r"^([0-5]?\d):([0-5]\d)$")


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
    # `next` is minutes:seconds (how long until the next stop), not a clock
    # time, so it's exposed as free text in MM:SS rather than an <input
    # type="time"> (which reads as HH:MM). Stored on the model's TimeField
    # with hour fixed at 0 — see clean_next().
    next = forms.CharField(
        required=False,
        label="Next",
        widget=forms.TextInput(attrs={"placeholder": "00:00", "autocomplete": "off", "inputmode": "numeric"}),
        help_text="Minutes and seconds until the next stop, format MM:SS (e.g. 05:30).",
    )

    class Meta:
        model = AmMidPmEntry
        fields = ["route", "type", "seq", "time", "address", "next"]
        widgets = {
            "time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.route_id:
            self.fields["route"].initial = self.instance.route.route_number
        if self.instance.pk and self.instance.next is not None:
            self.fields["next"].initial = self.instance.next.strftime("%M:%S")

    def clean_route(self):
        route_number = self.cleaned_data["route"].strip()
        try:
            return Route.objects.get(route_number__iexact=route_number)
        except Route.DoesNotExist:
            raise forms.ValidationError("No MCPS Route matches that route number. Pick one from the list.")

    def clean_next(self):
        value = self.cleaned_data.get("next", "").strip()
        if not value:
            return None
        match = MINUTES_SECONDS_RE.match(value)
        if not match:
            raise forms.ValidationError("Enter minutes and seconds as MM:SS, e.g. 05:30.")
        minutes, seconds = int(match.group(1)), int(match.group(2))
        return time(0, minutes, seconds)


class LeftRightForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = LeftRight
        fields = ["route", "name"]
