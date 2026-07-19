from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from vault.models import Category, MediaFile, VaultPassword

numero_cuenta_validator = RegexValidator(
    regex=r"^\d+$",
    message="The account number must contain only digits, no spaces or special characters.",
)


class Cuenta(models.Model):
    """Cuenta o medio donde se mueve el dinero (ej: Efectivo, BBVA Débito, Amex)."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cuentas")
    numero = models.CharField(
        max_length=50, verbose_name="Account number", validators=[numero_cuenta_validator]
    )
    name = models.CharField(max_length=100, verbose_name="Name")

    class Meta:
        ordering = ["name"]
        unique_together = [("owner", "name"), ("owner", "numero")]
        verbose_name = "Account"
        verbose_name_plural = "Accounts"

    def __str__(self):
        return self.name


class Transaccion(models.Model):
    """Registro de un ingreso o egreso de dinero, ligado a una Cuenta."""

    class Tipo(models.TextChoices):
        INGRESO = "ingreso", "Income"
        EGRESO = "egreso", "Expense"

    class MetodoCaptura(models.TextChoices):
        MANUAL = "manual", "Manual"
        FOTO = "foto", "Receipt photo"
        VOZ = "voz", "Voice"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transacciones")
    cuenta = models.ForeignKey(
        Cuenta, on_delete=models.PROTECT, related_name="transacciones", verbose_name="Account"
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices, verbose_name="Type")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Amount")
    fecha = models.DateField(verbose_name="Date")
    concepto = models.CharField(max_length=200, verbose_name="Description")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="transacciones",
        verbose_name="Category",
    )
    recibo = models.ForeignKey(
        MediaFile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transacciones", verbose_name="Receipt",
        help_text="Photo or document of the receipt, reusing your Files.",
    )
    metodo_captura = models.CharField(
        max_length=10, choices=MetodoCaptura.choices, default=MetodoCaptura.MANUAL,
        verbose_name="Capture method",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha", "-created_at"]
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.concepto} ({self.monto})"


class Deuda(models.Model):
    """Deuda recurrente (tarjeta, préstamo, etc.) con su pago mensual y estatus del mes en curso."""

    class Tipo(models.TextChoices):
        FIJA = "fija", "Fixed"
        VARIABLE = "variable", "Variable"

    class Flag(models.TextChoices):
        PAGADO = "P", "Paid"
        NO_PAGADO = "N", "Not paid yet"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deudas")
    deuda = models.CharField(max_length=150, verbose_name="Debt")
    tipo = models.CharField(max_length=10, choices=Tipo.choices, verbose_name="Type")
    monto = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="Monthly payment amount",
        help_text="Required if the debt is Fixed; optional if it's Variable.",
    )
    saldo = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Balance"
    )
    cuenta = models.ForeignKey(
        Cuenta, on_delete=models.PROTECT, related_name="deudas", verbose_name="Account #"
    )
    credito = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Credit limit"
    )
    dia = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        verbose_name="Payment day",
        help_text="Day of the month the payment is due (1-31).",
    )
    flag = models.CharField(
        max_length=1, choices=Flag.choices, default=Flag.NO_PAGADO,
        verbose_name="Paid this month", help_text="Payment status for the current month.",
    )
    remarks = models.TextField(blank=True, verbose_name="Remarks")
    password = models.ForeignKey(
        VaultPassword, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="deudas", verbose_name="Related password",
        help_text="Password record you use to log in and pay this debt.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["deuda"]
        verbose_name = "Debt"
        verbose_name_plural = "Debts"

    @property
    def credito_disponible(self):
        if self.credito is None:
            return None
        return self.credito - (self.saldo or 0)

    def __str__(self):
        return self.deuda
