from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CustomUser(AbstractUser):
    """System user. The Main Admin can create and manage
    all other accounts."""

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
