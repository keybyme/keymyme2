from django.conf import settings
from django.db import models

from vault.models import Category, MediaFile


class Cuenta(models.Model):
    """Cuenta o medio donde se mueve el dinero (ej: Efectivo, BBVA Débito, Amex)."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cuentas")
    numero = models.CharField(max_length=50, verbose_name="Número de cuenta")
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
