from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.files.uploadedfile import UploadedFile

from .image_compression import compress_image
from .models import Category, Contact, MediaFile, Reminder, Url, VaultPassword

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
        label="Archivo (.vcf o .csv)",
        help_text="vCard exportada de iPhone/iCloud, o un CSV con columnas nombre/telefono/email/direccion/notas.",
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        required=False,
        label="Categoría",
        help_text="Opcional: se asignará a todos los contactos importados.",
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        if not uploaded_file.name.lower().endswith((".vcf", ".csv")):
            raise forms.ValidationError("El archivo debe tener extensión .vcf o .csv.")
        return uploaded_file


class VaultPasswordForm(TailwindFormMixin, UserCategoryFormMixin, forms.ModelForm):
    password = forms.CharField(
        label="Password",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Dejar en blanco para no modificar el password actual.",
    )

    class Meta:
        model = VaultPassword
        fields = ["site_name", "site_url", "username", "category", "notes"]

    def clean(self):
        cleaned_data = super().clean()
        # En creación (instance sin pk todavía), el password es obligatorio
        if not self.instance.pk and not cleaned_data.get("password"):
            self.add_error("password", "Este campo es obligatorio al crear un nuevo registro.")
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
        ("alta", "Alta (sin comprimir)"),
        ("media", "Media"),
        ("baja", "Baja (máximo ahorro)"),
    ]
    photo_quality = forms.ChoiceField(
        choices=PHOTO_QUALITY_CHOICES,
        initial="alta",
        required=False,
        label="Calidad de la foto",
        help_text="Reduce el tamaño (KB) al subir o reemplazar una foto. No aplica a videos ni documentos.",
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
            "remind_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "recipient_email": forms.EmailInput(attrs={"placeholder": "Dejar vacío para usar tu correo de cuenta"}),
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
        widget=forms.URLInput(attrs={"placeholder": "https://ejemplo.com"}),
    )
