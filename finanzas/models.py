from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from vault.models import Category, MediaFile, VaultPassword

numero_cuenta_validator = RegexValidator(
    regex=r"^\d+$",
    message="El número de cuenta solo debe contener dígitos, sin espacios ni caracteres especiales.",
)


class Cuenta(models.Model):
    """Cuenta o medio donde se mueve el dinero (ej: Efectivo, BBVA Débito, Amex)."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cuentas")
    numero = models.CharField(
        max_length=50, verbose_name="Número de cuenta", validators=[numero_cuenta_validator]
    )
    name = models.CharField(max_length=100, verbose_name="Nombre")

    class Meta:
        ordering = ["name"]
        unique_together = [("owner", "name"), ("owner", "numero")]
        verbose_name = "Cuenta"
        verbose_name_plural = "Cuentas"

    def __str__(self):
        return self.name


class Transaccion(models.Model):
    """Registro de un ingreso o egreso de dinero, ligado a una Cuenta."""

    class Tipo(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"
        EGRESO = "egreso", "Egreso"

    class MetodoCaptura(models.TextChoices):
        MANUAL = "manual", "Manual"
        FOTO = "foto", "Foto de recibo"
        VOZ = "voz", "Voz"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transacciones")
    cuenta = models.ForeignKey(
        Cuenta, on_delete=models.PROTECT, related_name="transacciones", verbose_name="Cuenta"
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices, verbose_name="Tipo")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto")
    fecha = models.DateField(verbose_name="Fecha")
    concepto = models.CharField(max_length=200, verbose_name="Concepto")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="transacciones",
        verbose_name="Categoría",
    )
    recibo = models.ForeignKey(
        MediaFile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transacciones", verbose_name="Recibo",
        help_text="Foto o documento del recibo, reutilizando tus Archivos.",
    )
    metodo_captura = models.CharField(
        max_length=10, choices=MetodoCaptura.choices, default=MetodoCaptura.MANUAL,
        verbose_name="Método de captura",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha", "-created_at"]
        verbose_name = "Transacción"
        verbose_name_plural = "Transacciones"

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.concepto} ({self.monto})"


class Deuda(models.Model):
    """Deuda recurrente (tarjeta, préstamo, etc.) con su pago mensual y estatus del mes en curso."""

    class Tipo(models.TextChoices):
        FIJA = "fija", "Fija"
        VARIABLE = "variable", "Variable"

    class Flag(models.TextChoices):
        PAGADO = "P", "Pagado"
        NO_PAGADO = "N", "Aún sin pagar"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deudas")
    deuda = models.CharField(max_length=150, verbose_name="Deuda")
    tipo = models.CharField(max_length=10, choices=Tipo.choices, verbose_name="Tipo")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto a pagar cada mes")
    saldo = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Saldo"
    )
    cuenta = models.ForeignKey(
        Cuenta, on_delete=models.PROTECT, related_name="deudas", verbose_name="Cuenta #"
    )
    credito = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Crédito"
    )
    dia = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        verbose_name="Día de pago",
        help_text="Día del mes en que vence el pago (1-31).",
    )
    flag = models.CharField(
        max_length=1, choices=Flag.choices, default=Flag.NO_PAGADO,
        verbose_name="Flag", help_text="Estatus de pago del mes en curso.",
    )
    remarks = models.TextField(blank=True, verbose_name="Observaciones")
    password = models.ForeignKey(
        VaultPassword, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="deudas", verbose_name="Password relacionado",
        help_text="Registro de Passwords donde inicias sesión para pagar esta deuda.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["deuda"]
        verbose_name = "Deuda"
        verbose_name_plural = "Deudas"

    @property
    def credito_disponible(self):
        if self.credito is None:
            return None
        return self.credito - (self.saldo or 0)

    def __str__(self):
        return self.deuda
