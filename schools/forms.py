import re
from datetime import time

from django import forms
from django.forms import modelformset_factory

from vault.forms import TailwindFormMixin

from .models import (
    AmMidPmEntry, DepotLink, Employee, LeftRight, LeftRightAddressList, LeftRightRow, LeftRightSheetUpload, Route,
    School,
)

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

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean(self):
        # ModelForm's own validate_unique() can't catch a collision on
        # LeftRight's (domain, route_name, name) constraint here --
        # `domain` isn't a form field, so Django always excludes it from
        # that check (see BaseModelForm._get_validation_exclusions()),
        # which means the constraint is silently skipped rather than
        # checked with the wrong/blank domain. self.instance.domain IS
        # reliably set by the time this runs (both LeftRightCreateView and
        # LeftRightRenameView's get_form() set it before is_valid() ever
        # gets called) -- so check it by hand instead of leaning on a
        # UniqueConstraint that never fires through this form, which would
        # otherwise surface as a raw IntegrityError at save() instead of a
        # normal form error.
        cleaned_data = super().clean()
        route_name = cleaned_data.get("route_name")
        name = cleaned_data.get("name")
        if route_name and name:
            conflict = LeftRight.objects.filter(
                domain=self.instance.domain, route_name=route_name, name=name
            ).exclude(pk=self.instance.pk)
            if conflict.exists():
                raise forms.ValidationError(f'"{name}" already exists for route "{route_name}".')
        return cleaned_data


class LeftRightAddressListForm(TailwindFormMixin, forms.ModelForm):
    """The "Addresses" page (LeftRightAddressListView). `route_name` is
    the same free-text convention as LeftRightForm.route_name (not tied
    to any other catalog) -- the `<datalist>` (rendered by the view/
    template, id="lr-addr-route-names-datalist") suggests route names
    already used by either an existing LeftRight or a previously-saved
    address list. `addresses` is validated to 4-15 non-blank lines --
    LeftRightGenerateRowsView needs at least 2 to compute even one leg,
    but the point of this page is a full route, hence 4 as the practical
    floor; 15 keeps a single "Generate" action's LocationIQ geocoding (~1
    req/sec, see vault/routing.py) under half a minute."""

    class Meta:
        model = LeftRightAddressList
        fields = ["route_name", "addresses"]
        widgets = {
            "route_name": forms.TextInput(attrs={"list": "lr-addr-route-names-datalist", "autocomplete": "off", "placeholder": "Type the route name…"}),
            "addresses": forms.Textarea(attrs={
                "rows": 14, "placeholder": "One address per line, in visiting order…\n123 Main St, City, MD 20874\n456 Oak Ave, City, MD 20874\n…",
            }),
        }

    def clean_route_name(self):
        return self.cleaned_data["route_name"].strip()

    def clean_addresses(self):
        lines = [line.strip() for line in self.cleaned_data["addresses"].splitlines() if line.strip()]
        if len(lines) < 4:
            raise forms.ValidationError("Enter at least 4 addresses (one per line).")
        if len(lines) > 15:
            raise forms.ValidationError("Enter at most 15 addresses (one per line).")
        return "\n".join(lines)


class MultipleFileInput(forms.FileInput):
    """`allow_multiple_selected = True` is what tells Django's own FileInput
    to actually render the `multiple` HTML attribute (passing `multiple`
    via `attrs` directly raises ValueError -- FileInput refuses it unless
    the widget opts in this way, since a plain FileInput's
    value_from_datadict only ever reads one file). Plain FileInput rather
    than ClearableFileInput -- there's no single "existing file" here to
    offer clearing (see LeftRightSheetUploadForm)."""
    allow_multiple_selected = True


class LeftRightSheetUploadForm(TailwindFormMixin, forms.ModelForm):
    """Renders the file input in the "Upload photos or documents" panel on
    the "Addresses" page (leftright_addresses.html) -- used for its widget
    only (styling via TailwindFormMixin + MultipleFileInput, so several
    files can be picked at once), never for validation:
    LeftRightSheetUploadView processes `request.FILES.getlist("file")`
    itself (one LeftRightSheetUpload row per file, each validated on its
    own -- see that view), since a single ModelForm field can't represent
    "0 or more files" the way a multi-file input submits them.
    `route_name`/`domain` aren't form fields either, for the same reason
    -- the view sets them from the panel's own route_name field."""

    class Meta:
        model = LeftRightSheetUpload
        fields = ["file"]
        labels = {"file": "Photos or documents"}
        widgets = {"file": MultipleFileInput(attrs={"accept": "image/*,.pdf,.docx"})}


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
    """One row on the Edit page (leftright_form.html). `row_type` and
    `order` are hidden inputs set by JS -- not something the user picks
    from a dropdown; which button they click ("Insertar fila" vs "Insertar
    vinculo") decides the type. LINK rows use all three of
    text/address/text_after (see LeftRightRow); other row types only use
    `text`.

    Each widget's `class` here (lr-row-type/lr-order/lr-text/lr-address/
    lr-text-after) is the autosave JS's hook -- LeftRightRowSaveView reads
    a row's current values via these same class names, and lrBuildRow() in
    leftright_form.html renders freshly-added rows with the exact same
    classes, so server-rendered and JS-built rows are indistinguishable to
    that JS. Rows are no longer submitted as a Django formset (this form
    is used unbound, purely to render each row with consistent widgets/
    styling) -- see LeftRightUpdateView/LeftRightRowSaveView."""

    class Meta:
        model = LeftRightRow
        fields = ["row_type", "order", "text", "address", "text_after"]
        widgets = {
            "row_type": forms.HiddenInput(attrs={"class": "lr-row-type"}),
            "order": forms.HiddenInput(attrs={"class": "lr-order"}),
            "text": forms.TextInput(attrs={"class": "lr-text"}),
            "address": forms.TextInput(attrs={"class": "lr-address", "placeholder": "Address…"}),
            "text_after": forms.TextInput(attrs={"class": "lr-text-after", "placeholder": "Text…"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        extra_classes = ROW_TEXT_CLASSES.get(self.instance.row_type, ROW_TEXT_CLASSES_DEFAULT)
        if extra_classes:
            existing = self.fields["text"].widget.attrs.get("class", "")
            self.fields["text"].widget.attrs["class"] = f"{existing} {extra_classes}".strip()
        self.fields["text"].widget.attrs["placeholder"] = "Text…"



class DepotLinkForm(TailwindFormMixin, forms.ModelForm):
    """One row in the DepotLinkFormSet below — see DepotLink. Rendered as
    `<a href="{url}">{name}</a>` on the read-only "Listar" page
    (DepotListView / depot_list.html), which is also where printing
    happens; this edit page (depot.html) just has the two raw fields."""

    class Meta:
        model = DepotLink
        fields = ["order", "url", "name"]
        widgets = {
            "order": forms.HiddenInput(),
            "url": forms.TextInput(attrs={"placeholder": "https://…"}),
            "name": forms.TextInput(attrs={"placeholder": "Link text (e.g. TV156)…"}),
        }


# Not an inline formset -- DepotLink has no parent FK, it's a single flat
# list shared by the whole "Depot" page (see DepotView). extra=0: new rows
# are added client-side via JS ("Insertar fila" in depot.html). Unlike
# LeftRightRowForm's rows above, DepotView still submits this whole
# formset in one POST (no autosave here) -- see DepotView.post().
DepotLinkFormSet = modelformset_factory(
    DepotLink, form=DepotLinkForm, extra=0, can_delete=True,
)
