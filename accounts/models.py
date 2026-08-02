from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CustomUser(AbstractUser):
    """System user. The Main Admin can create and manage
    all other accounts."""

    # Módulo -> URL a donde mandar al usuario después del login (o al
    # tocar el logo): el primero de esta lista al que tenga acceso, en el
    # mismo orden en que aparecen en el nav (ver base.html). Categories
    # nunca falla porque Category*View no exige ningún módulo.
    LANDING_MODULE_URLS = [
        ("contacts", "vault:contact_list"),
        ("passwords", "vault:password_list"),
        ("links", "vault:url_list"),
        ("files", "vault:mediafile_list"),
        ("reminders", "vault:reminder_list"),
        ("finanzas_transacciones", "finanzas:transaccion_list"),
        ("finanzas_cuentas", "finanzas:cuenta_list"),
        ("finanzas_deudas", "finanzas:deuda_list"),
        ("artifacts_qr", "vault:qrcode_generate"),
        ("artifacts_imhere", "vault:im_here"),
        ("cars", "vault:vehicle_list"),
    ]

    is_admin_principal = models.BooleanField(
        default=False,
        help_text="If True, this user can create/manage other accounts and their permissions.",
    )
    storage_quota_gb = models.DecimalField(
        max_digits=10, decimal_places=2, default=5.0,
        help_text="Storage quota assigned to the user, in GB.",
    )
    storage_used_bytes = models.BigIntegerField(
        default=0, help_text="Space currently used, in bytes. Recalculated when files are uploaded/deleted.",
    )
    is_suspended = models.BooleanField(
        default=False, help_text="If True, the user cannot log in even if is_active is True.",
    )
    created_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="created_users",
        help_text="Main admin who created this account.",
    )
    phone = models.CharField(
        max_length=20, blank=True,
        verbose_name="Mobile phone",
        help_text="Your mobile number, without spaces (e.g. 2407939353).",
    )
    carrier = models.CharField(
        max_length=30, blank=True,
        verbose_name="Carrier / SMS gateway",
        help_text=(
            "Your phone carrier's email-to-SMS domain, including the at sign "
            "(e.g. @tmomail.net for T-Mobile, @vtext.com for Verizon, @txt.att.net for AT&T). "
            "Combined with your phone number, this builds the address KeyByMe can use to send you "
            "notifications as if they were an SMS, without needing Twilio or any other service."
        ),
    )
    location_alert_email = models.EmailField(
        blank=True,
        verbose_name="Location alert email",
        help_text="Where the 'I am here' button sends your coordinates and local time.",
    )
    emergency_emails = models.CharField(
        max_length=500, blank=True,
        verbose_name="Emergency alert email(s)",
        help_text=(
            "Where the 'Emergency' button sends your GPS location, date, and time. "
            "Separate multiple addresses with commas."
        ),
    )
    route = models.CharField(
        max_length=100, default="9999", blank=True,
        verbose_name="Route",
        help_text="Route number assigned to this user, shown on their 'I am here' check-ins.",
    )

    @property
    def sms_gateway_email(self):
        """Address like '2407939353@tmomail.net' built from phone+carrier,
        or '' if the user is missing either setting."""
        if self.phone and self.carrier:
            return f"{self.phone}{self.carrier}"
        return ""

    def _active_user_roles(self):
        """UserRole assignments currently in effect: permanent ones (no dates
        set) plus temporary ones whose date range includes today."""
        today = timezone.localdate()
        return self.user_roles.filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=today)
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=today)
        )

    @property
    def active_roles(self):
        """Roles currently active for this user (excludes assignments that
        haven't started yet or have already expired)."""
        from menus.models import Role
        return Role.objects.filter(user_roles__in=self._active_user_roles()).distinct()

    @property
    def role_level(self):
        """Highest level among the user's currently active roles, or 0 if none."""
        levels = self._active_user_roles().values_list("role__level", flat=True)
        return max(levels, default=0)

    @property
    def emergency_email_list(self):
        """emergency_emails split on commas into a clean list of addresses."""
        return [addr.strip() for addr in self.emergency_emails.split(",") if addr.strip()]

    @property
    def storage_quota_bytes(self):
        return int(self.storage_quota_gb * (1024 ** 3))

    @property
    def storage_available_bytes(self):
        return max(self.storage_quota_bytes - self.storage_used_bytes, 0)

    def has_space_for(self, additional_bytes: int) -> bool:
        return (self.storage_used_bytes + additional_bytes) <= self.storage_quota_bytes

    def has_module_access(self, module_codename: str) -> bool:
        """Whether the user's currently active roles grant access to a
        Module (e.g. 'contacts', 'passwords'). The main admin always has
        access to every module."""
        if self.is_admin_principal:
            return True
        return self._active_user_roles().filter(role__modules__codename=module_codename).exists()

    @property
    def default_landing_url(self):
        """Where to send this user after login, or where the nav logo
        should point: the first module they have access to, in nav order.
        Falls back to Categories, which every logged-in user can always
        reach — so this never lands the user on a page they're denied."""
        from django.urls import reverse
        for module_codename, url_name in self.LANDING_MODULE_URLS:
            if self.has_module_access(module_codename):
                return reverse(url_name)
        return reverse("vault:category_list")

    def has_permission(self, submodule_codename: str) -> bool:
        """Checks whether the user has access to a submodule, honoring
        per-user overrides first, then falling back to the user's active roles."""
        override = self.permission_overrides.filter(submodule__codename=submodule_codename).first()
        if override is not None:
            return override.granted
        return self._active_user_roles().filter(
            role__submodules__codename=submodule_codename, role__submodules__is_active=True
        ).exists()

    def __str__(self):
        return self.username
