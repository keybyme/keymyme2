import calendar
import os
import uuid
from datetime import timedelta

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import FileExtensionValidator
from django.db import models

# Whitelist de extensiones permitidas para MediaFile. Deliberadamente NO se
# incluyen ejecutables ni scripts (.exe, .bat, .sh, .js, etc.): solo se listan
# los formatos de documento/foto/video que la vault debe aceptar.
ALLOWED_MEDIA_EXTENSIONS = [
    # Documentos
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "odt", "ods",
    # Fotos
    "jpg", "jpeg", "png", "gif", "webp", "bmp", "heic",
    # Videos
    "mp4", "mov", "avi", "mkv", "webm",
]

# Extensiones permitidas para la tarjeta de seguro de un Vehicle.
ALLOWED_INSURANCE_CARD_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "webp"]


def get_fernet() -> Fernet:
    """Instancia el cifrador usando la llave definida en variables de entorno.
    NUNCA se guarda la llave en el código ni en la base de datos."""
    key = settings.VAULT_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "VAULT_ENCRYPTION_KEY no está configurada. Define esta variable de entorno "
            "antes de guardar o leer passwords."
        )
    return Fernet(key)


def user_upload_path(instance, filename):
    """Organiza los archivos por usuario: media/vault/<user_id>/<filename>"""
    return f"vault/{instance.owner_id}/{filename}"


class Category(models.Model):
    """Categoría definida por el usuario (ej: familia, trabajo, tecnología),
    reutilizable entre Contact, VaultPassword, Url, MediaFile y Reminder."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        unique_together = ("owner", "name")
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Contact(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="contacts"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Contact"
        verbose_name_plural = "Contacts"

    def __str__(self):
        return self.name


class VaultPassword(models.Model):
    """Password cifrado de forma reversible (no hash), porque el usuario
    necesita poder recuperar el valor en texto plano."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="passwords")
    site_name = models.CharField(max_length=150)
    site_url = models.URLField(blank=True)
    username = models.CharField(max_length=150, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="passwords"
    )
    _encrypted_password = models.BinaryField(db_column="encrypted_password")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["site_name"]
        verbose_name = "Password"
        verbose_name_plural = "Passwords"

    def set_password(self, raw_password: str) -> None:
        self._encrypted_password = get_fernet().encrypt(raw_password.encode("utf-8"))

    def get_password(self) -> str:
        return get_fernet().decrypt(bytes(self._encrypted_password)).decode("utf-8")

    def __str__(self):
        return f"{self.site_name} ({self.owner})"


class Url(models.Model):
    """Enlace guardado (bookmark), independiente de los sitios asociados a un password."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="urls")
    name = models.CharField(max_length=150)
    url = models.URLField()
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="urls"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "URL"
        verbose_name_plural = "URLs"

    def __str__(self):
        return self.name


class MediaFile(models.Model):
    """Documentos, fotos y videos. Un solo modelo con un campo 'file_type'
    para simplificar; se puede filtrar por tipo en las vistas."""

    class FileType(models.TextChoices):
        DOCUMENT = "document", "Document"
        PHOTO = "photo", "Photo"
        VIDEO = "video", "Video"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="media_files")
    file = models.FileField(
        upload_to=user_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_MEDIA_EXTENSIONS)],
    )
    file_type = models.CharField(max_length=10, choices=FileType.choices)
    original_name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="media_files"
    )
    file_size_bytes = models.BigIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "File"
        verbose_name_plural = "Files"

    def save(self, *args, **kwargs):
        if self.file and not self.file_size_bytes:
            self.file_size_bytes = self.file.size
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Libera espacio de la cuota del usuario al borrar
        owner = self.owner
        size = self.file_size_bytes
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)
        owner.storage_used_bytes = max(owner.storage_used_bytes - size, 0)
        owner.save(update_fields=["storage_used_bytes"])

    def __str__(self):
        return self.original_name


class Reminder(models.Model):
    FREQUENCY_CHOICES = [
        ("", "One time"),
        ("diario", "Daily"),
        ("semanal", "Weekly"),
        ("mensual", "Monthly"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reminders")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="reminders"
    )
    remind_at = models.DateTimeField()
    frequency = models.CharField(
        max_length=10,
        choices=FREQUENCY_CHOICES,
        blank=True,
        default="",
        verbose_name="Frequency",
        help_text=(
            "One time: the reminder is deleted after it is sent. Daily/Weekly/Monthly: "
            "it is automatically rescheduled for the same time (same day of the week or month as applicable)."
        ),
    )
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    recipient_email = models.EmailField(
        blank=True,
        verbose_name="Recipient email",
        help_text="Who the notification is sent to. If left empty, your account email is used.",
    )
    email_sent_at = models.DateTimeField(
        null=True, blank=True, editable=False,
        help_text="When the notification email was sent. Empty = not sent yet.",
    )

    class Meta:
        ordering = ["remind_at"]
        verbose_name = "Reminder"
        verbose_name_plural = "Reminders"

    def __str__(self):
        return self.title

    @property
    def notification_email(self):
        """Correo efectivo al que se enviará el aviso: el explícito del
        recordatorio; si no se puso, la pasarela SMS del dueño (phone+carrier,
        para que llegue como texto al celular); si tampoco hay, el correo de la cuenta."""
        return self.recipient_email or self.owner.sms_gateway_email or self.owner.email

    def next_occurrence(self):
        """Siguiente remind_at según la frecuencia, o None si no se repite."""
        if self.frequency == "diario":
            return self.remind_at + timedelta(days=1)
        if self.frequency == "semanal":
            return self.remind_at + timedelta(weeks=1)
        if self.frequency == "mensual":
            year = self.remind_at.year + self.remind_at.month // 12
            month = self.remind_at.month % 12 + 1
            last_day = calendar.monthrange(year, month)[1]
            day = min(self.remind_at.day, last_day)
            return self.remind_at.replace(year=year, month=month, day=day)
        return None


class LocationCheckIn(models.Model):
    """Un registro por cada click en el botón 'I am here', con las
    coordenadas que el navegador capturó en ese momento. También puede ser
    una parada precargada desde RouteStop (ver LoadRouteView/ImHereView):
    en ese caso latitude/longitude/created_at quedan en None hasta que el
    usuario la marca con el ícono 'Here'."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="location_checkins")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=30, blank=True, verbose_name="Phone")
    seq = models.PositiveIntegerField(default=10, verbose_name="Seq")
    stop_number = models.PositiveIntegerField(null=True, blank=True, verbose_name="Stop #")
    route_type = models.CharField(
        max_length=30, blank=True, verbose_name="Route type",
        help_text="Which saved route (AM, PM, MID DAY, ...) this stop was loaded from, if any.",
    )
    check_date = models.DateField(verbose_name="Date")
    created_at = models.DateTimeField(null=True, blank=True, verbose_name="Time")
    is_closed = models.BooleanField(
        default=False,
        help_text="Set by Dispatch's 'Close day': moves this check-in from today's "
        "'I am here' table into History, without waiting for the calendar date to change.",
    )

    class Meta:
        ordering = ["-check_date", "seq"]
        verbose_name = "Location check-in"
        verbose_name_plural = "Location check-ins"

    def __str__(self):
        return f"{self.owner} @ {self.check_date}"

    @property
    def maps_url(self):
        if self.latitude is None or self.longitude is None:
            return ""
        return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"


class RouteStop(models.Model):
    """Plantilla de ruta diaria de un chofer: seq + remarks de las paradas,
    agrupadas por route_type (AM, PM, MID DAY, etc.) para poder tener varias
    rutas nombradas en paralelo. Sin fecha/hora/ubicación propias (esas se
    capturan cada día). Administrada solo desde Dispatch/Rutas (Admin*
    views); ImHereView/LoadRouteView solo LEEN de acá para precargar el
    día — nunca la modifican."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="route_stops")
    route_type = models.CharField(max_length=30, default="AM", verbose_name="Route type")
    seq = models.PositiveIntegerField(default=10, verbose_name="Seq")
    stop_number = models.PositiveIntegerField(null=True, blank=True, verbose_name="Stop #")
    planned_time = models.TimeField(
        null=True, blank=True, verbose_name="Time",
        help_text="Reference time this stop is expected to happen — not the actual captured time.",
    )
    remarks = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=30, blank=True, verbose_name="Phone")

    class Meta:
        ordering = ["route_type", "seq"]
        verbose_name = "Daily route stop"
        verbose_name_plural = "Daily route stops"

    def __str__(self):
        return f"{self.owner} {self.route_type} route stop #{self.seq}"


class Vehicle(models.Model):
    """Un vehículo del usuario. Tiene una URL pública (por public_token, no
    por pk, para que no sea adivinable) que muestra su historial de
    mantenimiento sin necesidad de login — pensada para imprimirse como QR
    y pegarse en el carro. Agregar un MaintenanceRecord desde esa página
    pública requiere conocer el PIN (ver set_pin/verify_pin)."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vehicles")
    make = models.CharField(max_length=100, verbose_name="Make")
    model = models.CharField(max_length=100, verbose_name="Model")
    year = models.PositiveIntegerField(verbose_name="Year")
    license_plate = models.CharField(max_length=20, blank=True, verbose_name="License plate")
    insurance_broker_phone = models.CharField(max_length=30, blank=True, verbose_name="Insurance broker phone")
    insurance_card = models.FileField(
        upload_to=user_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_INSURANCE_CARD_EXTENSIONS)],
        blank=True, null=True,
        verbose_name="Insurance card",
    )
    _pin_hash = models.CharField(max_length=128, db_column="pin_hash", editable=False)
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["make", "model", "-year"]
        verbose_name = "Vehicle"
        verbose_name_plural = "Vehicles"

    def __str__(self):
        return f"{self.year} {self.make} {self.model}"

    def set_pin(self, raw_pin: str) -> None:
        self._pin_hash = make_password(raw_pin)

    def verify_pin(self, raw_pin: str) -> bool:
        return bool(raw_pin) and check_password(raw_pin, self._pin_hash)


class MaintenanceRecord(models.Model):
    """Un evento de mantenimiento (reparación, cambio de aceite, llantas,
    etc.) de un Vehicle. Puede haber sido agregado por el dueño logueado o,
    con el PIN correcto, desde la página pública del vehículo — ver
    created_via_public_link."""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="maintenance_records")
    service_date = models.DateField(verbose_name="Date")
    performed_by = models.CharField(max_length=150, verbose_name="Performed by (company or person)")
    mileage = models.PositiveIntegerField(verbose_name="Mileage")
    comment = models.TextField(blank=True, verbose_name="Comment")
    created_via_public_link = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-service_date", "-created_at"]
        verbose_name = "Maintenance record"
        verbose_name_plural = "Maintenance records"

    def __str__(self):
        return f"{self.vehicle} — {self.service_date}"
