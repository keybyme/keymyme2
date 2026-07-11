from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """Usuario del sistema. El Admin Principal puede crear y administrar
    todas las demás cuentas."""

    is_admin_principal = models.BooleanField(
        default=False,
        help_text="Si es True, este usuario puede crear/administrar otras cuentas y sus permisos.",
    )
    role = models.ForeignKey(
        "menus.Role", on_delete=models.SET_NULL, null=True, blank=True, related_name="users"
    )
    storage_quota_gb = models.DecimalField(
        max_digits=10, decimal_places=2, default=5.0,
        help_text="Cuota de espacio asignada al usuario, en GB.",
    )
    storage_used_bytes = models.BigIntegerField(
        default=0, help_text="Espacio usado actualmente, en bytes. Se recalcula al subir/borrar archivos.",
    )
    is_suspended = models.BooleanField(
        default=False, help_text="Si es True, el usuario no puede iniciar sesión aunque is_active sea True.",
    )
    created_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="created_users",
        help_text="Admin principal que creó esta cuenta.",
    )

    @property
    def storage_quota_bytes(self):
        return int(self.storage_quota_gb * (1024 ** 3))

    @property
    def storage_available_bytes(self):
        return max(self.storage_quota_bytes - self.storage_used_bytes, 0)

    def has_space_for(self, additional_bytes: int) -> bool:
        return (self.storage_used_bytes + additional_bytes) <= self.storage_quota_bytes

    def has_permission(self, submodule_codename: str) -> bool:
        """Chequea si el usuario tiene acceso a un submódulo, respetando
        primero las excepciones individuales y luego el rol."""
        override = self.permission_overrides.filter(submodule__codename=submodule_codename).first()
        if override is not None:
            return override.granted
        if self.role_id is None:
            return False
        return self.role.submodules.filter(codename=submodule_codename, is_active=True).exists()

    def __str__(self):
        return self.username
