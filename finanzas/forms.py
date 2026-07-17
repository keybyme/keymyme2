from django import forms
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from vault.forms import TailwindFormMixin, UserCategoryFormMixin
from vault.models import ALLOWED_MEDIA_EXTENSIONS

from .models import Cuenta, Deuda, Transaccion


class CuentaForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Cuenta
        fields = ["numero", "name"]
        widgets = {
            # inputmode/pattern son solo UX (teclado numérico, feedback del navegador);
            # la validación real la hace numero_cuenta_validator en el modelo.
            "numero": forms.TextInput(attrs={"inputmode": "numeric", "pattern": r"\d*"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        # `owner` no es un campo del form, así que Django excluye la
        # unique_together (owner, name)/(owner, numero) de su validación
        # automática — por eso se revalida a mano en clean() usando `user`.
        super().__init__(*args, **kwargs)
        self._user = user

    def clean_name(self):
        name = self.cleaned_data["name"]
        if self._user is not None:
            duplicado = Cuenta.objects.filter(owner=self._user, name=name).exclude(pk=self.instance.pk)
            if duplicado.exists():
                raise forms.ValidationError("Ya tienes una cuenta con este nombre.")
        return name

    def clean_numero(self):
        numero = self.cleaned_data["numero"]
        if self._user is not None:
            duplicado = Cuenta.objects.filter(owner=self._user, numero=numero).exclude(pk=self.instance.pk)
            if duplicado.exists():
                raise forms.ValidationError("Ya tienes una cuenta con este número.")
        return numero


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


class DeudaForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Deuda
        fields = ["deuda", "tipo", "monto", "saldo", "cuenta", "credito", "dia", "flag", "remarks"]

    def __init__(self, *args, user=None, **kwargs):
        # `user` lo pasan siempre OwnerCreateMixin/UserFormKwargsMixin; se usa
        # para limitar el dropdown de 'cuenta' a las cuentas del dueño.
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["cuenta"].queryset = Cuenta.objects.filter(owner=user)
