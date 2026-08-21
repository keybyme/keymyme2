import re
from datetime import time

from django import forms
from django.forms import inlineformset_factory, modelformset_factory

from vault.forms import TailwindFormMixin

from .models import AmMidPmEntry, DepotLink, Employee, LeftRight, LeftRightRow, Route, School

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
    """`route_name` is free text, not tied to the MCPS Routes catalog (see
    LeftRight.route_name) — the `<datalist>` (rendered by the view/template,
    id="lr-route-names-datalist") just suggests route names already used by
    other LeftRight guides, purely so spelling stays consistent when adding
    a second guide to the same route. Nothing enforces a match."""

    class Meta:
        model = LeftRight
        fields = ["route_name", "name"]
        widgets = {
            "route_name": forms.TextInput(attrs={"list": "lr-route-names-datalist", "autocomplete": "off", "placeholder": "Type the route name…"}),
        }

    def clean_route_name(self):
        return self.cleaned_data["route_name"].strip()


#  Extra text-input classes layered on top of TailwindFormMixin's base
# INPUT_CLASSES, per row type — this is what makes the two title rows
# render large, black-weight and centered, and every other row (bold,
# normal, link, including ones added later via "Insertar fila"/"Insertar
# vinculo") extra-bold -- heavy, but a notch below the title's font-black
# so titles still stand out. Applied server-side in
# LeftRightRowForm.__init__ below. Kept in sync with leftright_detail.html
# so the input while editing looks like the rendered result.
ROW_TEXT_CLASSES_DEFAULT = "font-extrabold"
ROW_TEXT_CLASSES = {
    LeftRightRow.RowType.TITLE: "text-2xl font-black text-center text-black",
}


class LeftRightRowForm(TailwindFormMixin, forms.ModelForm):
    """One row in the LeftRightRowFormSet below. `row_type` and `order` are
    hidden inputs set by JS (see leftright_form.html) — not something the
    user picks from a dropdown; which button they click ("Insertar fila" vs
    "Insertar vinculo") decides the type. LINK rows use all three of
    text/address/text_after (see LeftRightRow); other row types only use
    `text`."""

    class Meta:
        model = LeftRightRow
        fields = ["row_type", "order", "text", "address", "text_after"]
        widgets = {
            "row_type": forms.HiddenInput(),
            "order": forms.HiddenInput(),
            "address": forms.TextInput(attrs={"placeholder": "Address…"}),
            "text_after": forms.TextInput(attrs={"placeholder": "Text…"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        extra_classes = ROW_TEXT_CLASSES.get(self.instance.row_type, ROW_TEXT_CLASSES_DEFAULT)
        if extra_classes:
            existing = self.fields["text"].widget.attrs.get("class", "")
            self.fields["text"].widget.attrs["class"] = f"{existing} {extra_classes}".strip()
        self.fields["text"].widget.attrs["placeholder"] = "Text…"


# extra=0: the form only ever adds rows via JS-cloned formset forms
# ("Insertar fila" / "Insertar vinculo" in leftright_form.html), not
# server-rendered blank extras — LeftRightCreateView seeds the initial
# four rows directly instead.
LeftRightRowFormSet = inlineformset_factory(
    LeftRight, LeftRightRow, form=LeftRightRowForm, extra=0, can_delete=True,
)


class DepotLinkForm(TailwindFormMixin, forms.ModelForm):
    """One row in the DepotLinkFormSet below — see DepotLink. Both fields'
    `oninput` call depotSyncPreview() (depot.html) so the live preview link
    next to them — the `<a href="{url}">{name}</a>` that's what actually
    prints — stays in sync with whatever's currently typed, before saving."""

    class Meta:
        model = DepotLink
        fields = ["order", "url", "name"]
        widgets = {
            "order": forms.HiddenInput(),
            "url": forms.TextInput(attrs={"placeholder": "https://…", "oninput": "depotSyncPreview(this)"}),
            "name": forms.TextInput(attrs={"placeholder": "Link text (e.g. TV156)…", "oninput": "depotSyncPreview(this)"}),
        }


# Not an inline formset -- DepotLink has no parent FK, it's a single flat
# list shared by the whole "Depot" page (see DepotView). extra=0: new rows
# are added client-side via JS ("Insertar fila" in depot.html), same
# pattern as LeftRightRowFormSet above.
DepotLinkFormSet = modelformset_factory(
    DepotLink, form=DepotLinkForm, extra=0, can_delete=True,
)
