from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """System user. The Main Admin can create and manage
    all other accounts."""

    is_admin_principal = models.BooleanField(
        default=False,
        help_text="If True, this user can create/manage other accounts and their permissions.",
    )
    role = models.ForeignKey(
        "menus.Role", on_delete=models.SET_NULL, null=True, blank=True, related_name="users"
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

    @property
    def role_level(self):
        return self.role.level if self.role_id else 0

    @property
    def storage_quota_bytes(self):
        return int(self.storage_quota_gb * (1024 ** 3))

    @property
    def storage_available_bytes(self):
        return max(self.storage_quota_bytes - self.storage_used_bytes, 0)

    def has_space_for(self, additional_bytes: int) -> bool:
        return (self.storage_used_bytes + additional_bytes) <= self.storage_quota_bytes

    def has_permission(self, submodule_codename: str) -> bool:
        """Checks whether the user has access to a submodule, honoring
        per-user overrides first, then falling back to the role."""
        override = self.permission_overrides.filter(submodule__codename=submodule_codename).first()
        if override is not None:
            return override.granted
        if self.role_id is None:
            return False
        return self.role.submodules.filter(codename=submodule_codename, is_active=True).exists()

    def __str__(self):
        return self.username
