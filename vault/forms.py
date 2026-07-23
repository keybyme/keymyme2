from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.files.uploadedfile import UploadedFile

from .image_compression import compress_image
from .models import (
    Category, Contact, LocationCheckIn, MaintenanceRecord, MediaFile, Reminder, RouteStop, Url,
    VaultPassword, Vehicle,
)

INPUT_CLASSES = (
    "block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 "
    "shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
)
CHECKBOX_CLASSES = "h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
FILE_CLASSES = (
    "block w-full text-sm text-gray-600 file:mr-4 file:rounded-lg file:border-0 file:bg-blue-50 "
    "file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
)


class TailwindFormMixin:
    """Aplica clases de Tailwind a los widgets para que todos los forms se vean consistentes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for bound_field in self.fields.values():
            widget = bound_field.widget
            existing = widget.attrs.get("class", "")
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = f"{existing} {CHECKBOX_CLASSES}".strip()
            elif isinstance(widget, forms.ClearableFileInput):
                widget.attrs["class"] = f"{existing} {FILE_CLASSES}".strip()
            else:
                widget.attrs["class"] = f"{existing} {INPUT_CLASSES}".strip()


class UserCategoryFormMixin:
    """Restringe el choice de 'category' a las categorías del usuario dueño del registro."""

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None and "category" in self.fields:
            self.fields["category"].queryset = Category.objects.filter(owner=user)


class CategoryForm(TailwindFormMixin, UserCategoryFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]


class ContactForm(TailwindFormMixin, UserCategoryFormMixin, forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["name", "phone", "email", "address", "category", "notes"]


class ContactImportForm(TailwindFormMixin, UserCategoryFormMixin, forms.Form):
    file = forms.FileField(
        label="File (.vcf or .csv)",
        help_text="vCard exported from iPhone/iCloud, or a CSV with name/phone/email/address/notes columns.",
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        required=False,
        label="Category",
        help_text="Optional: will be assigned to all imported contacts.",
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        if not uploaded_file.name.lower().endswith((".vcf", ".csv")):
            raise forms.ValidationError("The file must have a .vcf or .csv extension.")
        return uploaded_file


class VaultPasswordForm(TailwindFormMixin, UserCategoryFormMixin, forms.ModelForm):
    password = forms.CharField(
        label="Password",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Leave blank to keep the current password unchanged.",
    )

    class Meta:
        model = VaultPassword
        fields = ["site_name", "site_url", "username", "category", "notes"]

    def clean(self):
        cleaned_data = super().clean()
        # En creación (instance sin pk todavía), el password es obligatorio
        if not self.instance.pk and not cleaned_data.get("password"):
            self.add_error("password", "This field is required when creating a new record.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_password = self.cleaned_data.get("password")
        if raw_password:
            instance.set_password(raw_password)
        if commit:
            instance.save()
        return instance


class UrlForm(TailwindFormMixin, UserCategoryFormMixin, forms.ModelForm):
    class Meta:
        model = Url
        fields = ["name", "url", "category", "notes"]


class MediaFileForm(TailwindFormMixin, UserCategoryFormMixin, forms.ModelForm):
    PHOTO_QUALITY_CHOICES = [
        ("alta", "High (uncompressed)"),
        ("media", "Medium"),
        ("baja", "Low (maximum savings)"),
    ]
    photo_quality = forms.ChoiceField(
        choices=PHOTO_QUALITY_CHOICES,
        initial="alta",
        required=False,
        label="Photo quality",
        help_text="Reduces the size (KB) when uploading or replacing a photo. Does not apply to videos or documents.",
    )

    class Meta:
        model = MediaFile
        fields = ["file", "file_type", "original_name", "category"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(["file", "photo_quality", "file_type", "original_name", "category"])

    def clean(self):
        cleaned_data = super().clean()
        uploaded_file = cleaned_data.get("file")
        quality = cleaned_data.get("photo_quality") or "alta"
        if isinstance(uploaded_file, UploadedFile):
            compressed = compress_image(uploaded_file, quality)
            if compressed is not None:
                cleaned_data["file"] = compressed
        return cleaned_data


class ReminderForm(TailwindFormMixin, UserCategoryFormMixin, forms.ModelForm):
    class Meta:
        model = Reminder
        fields = [
            "title", "description", "category", "remind_at", "frequency",
            "recipient_email", "is_completed",
        ]
        widgets = {
            # format="%Y-%m-%dT%H:%M" fuerza ISO en vez del formato localizado
            # ("05/03/2026 14:30:00"): un <input type="datetime-local"> solo
            # reconoce "YYYY-MM-DDTHH:MM" en su value, si no se ve vacío.
            "remind_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
            "recipient_email": forms.EmailInput(attrs={"placeholder": "Leave empty to use your account email"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        # Al crear (no editar), prellena con la pasarela SMS del usuario (si la
        # configuró en su perfil) para que el aviso le llegue como texto por default.
        if user is not None and self.instance.pk is None and not self.initial.get("recipient_email"):
            self.fields["recipient_email"].initial = user.sms_gateway_email


class StyledAuthenticationForm(TailwindFormMixin, AuthenticationForm):
    """AuthenticationForm de Django con clases Tailwind, usado por la vista de login."""


class QRCodeForm(TailwindFormMixin, forms.Form):
    url = forms.URLField(
        label="URL",
        widget=forms.URLInput(attrs={"placeholder": "https://example.com"}),
    )


class NormalizeRouteTypeMixin:
    """Normaliza route_type (strip + mayúsculas) al guardar, para que 'AM' y
    'Am' no terminen siendo dos rutas distintas por un typo de mayúsculas."""

    def clean_route_type(self):
        return self.cleaned_data["route_type"].strip().upper()


class LocationCheckInForm(NormalizeRouteTypeMixin, TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = LocationCheckIn
        fields = ["stop_number", "seq", "route_type", "remarks", "address", "phone_number"]
        labels = {"remarks": "Name/Act"}
        widgets = {
            "remarks": forms.Textarea(attrs={"rows": 3}),
            "route_type": forms.TextInput(attrs={"placeholder": "AM"}),
        }


class RouteStopForm(NormalizeRouteTypeMixin, TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = RouteStop
        fields = ["stop_number", "route_type", "seq", "planned_time", "remarks", "address", "phone_number"]
        labels = {"remarks": "Name/Act"}
        widgets = {
            "remarks": forms.Textarea(attrs={"rows": 3}),
            "route_type": forms.TextInput(attrs={"placeholder": "AM"}),
            "planned_time": forms.TimeInput(attrs={"type": "time"}),
        }


class VehicleForm(TailwindFormMixin, forms.ModelForm):
    pin = forms.CharField(
        label="PIN",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="4-6 digits. Required to authorize adding a maintenance record from the "
        "public QR page. Leave blank to keep the current PIN unchanged.",
    )

    class Meta:
        model = Vehicle
        fields = ["make", "model", "year", "license_plate", "insurance_broker_phone", "insurance_card"]

    def __init__(self, *args, user=None, **kwargs):
        # user viene de UserFormKwargsMixin (OwnerCreateMixin lo inyecta
        # siempre); VehicleForm no lo necesita, solo lo acepta y descarta.
        super().__init__(*args, **kwargs)

    def clean_pin(self):
        pin = self.cleaned_data["pin"]
        if pin and not pin.isdigit():
            raise forms.ValidationError("PIN must contain only digits.")
        if pin and not (4 <= len(pin) <= 6):
            raise forms.ValidationError("PIN must be 4 to 6 digits long.")
        return pin

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk and not cleaned_data.get("pin"):
            self.add_error("pin", "This field is required when creating a new vehicle.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_pin = self.cleaned_data.get("pin")
        if raw_pin:
            instance.set_pin(raw_pin)
        if commit:
            instance.save()
        return instance


class PublicMaintenanceRecordForm(TailwindFormMixin, forms.ModelForm):
    pin = forms.CharField(
        label="Vehicle PIN",
        widget=forms.PasswordInput(render_value=False),
        help_text="Ask the vehicle owner for the PIN.",
    )

    class Meta:
        model = MaintenanceRecord
        fields = ["service_date", "performed_by", "mileage", "comment"]
        widgets = {
            "service_date": forms.DateInput(attrs={"type": "date"}),
            "comment": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(["pin", "service_date", "performed_by", "mileage", "comment"])
