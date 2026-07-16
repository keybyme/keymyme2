from django import forms
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from vault.forms import TailwindFormMixin, UserCategoryFormMixin
from vault.models import ALLOWED_MEDIA_EXTENSIONS

from .models import Cuenta, Transaccion


class CuentaForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Cuenta
        fields = ["numero", "name"]

    def __init__(self, *args, user=None, **kwargs):
        # `user` no se usa aquí (Cuenta no tiene un choice que filtrar por
        # dueño), pero OwnerCreateMixin/UserFormKwargsMixin siempre lo pasan.
        super().__init__(*args, **kwargs)


class TransaccionForm(TailwindFormMixin, UserCategoryFormMixin, forms.ModelForm):
    recibo_file = forms.FileField(
        required=False,
        label="Foto del recibo",
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_MEDIA_EXTENSIONS)],
        help_text="Opcional: adjunta una foto o documento del recibo (se guarda junto con tus Archivos).",
    )

    class Meta:
        model = Transaccion
        fields = ["tipo", "cuenta", "monto", "fecha", "concepto", "category"]
        widgets = {
            # format="%Y-%m-%d" fuerza ISO en vez del formato localizado
            # (dd/mm/aaaa): un <input type="date"> del navegador solo
            # reconoce ISO en el atributo value, si no, se ve vacío.
            "fecha": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        if user is not None:
            self.fields["cuenta"].queryset = Cuenta.objects.filter(owner=user)
        # Precarga la fecha de hoy al capturar (no al editar), para que la
        # captura rápida no requiera ni siquiera tocar este campo.
        if self.instance.pk is None and not self.initial.get("fecha"):
            self.fields["fecha"].initial = timezone.localdate()
        self.order_fields(["tipo", "cuenta", "monto", "fecha", "concepto", "category", "recibo_file"])
