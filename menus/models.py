from django.db import models


class Module(models.Model):
    """Un módulo principal del sistema (ej: Contactos, Passwords, Documentos)."""
    name = models.CharField(max_length=100, unique=True)
    codename = models.SlugField(max_length=100, unique=True, help_text="Identifier used in code, e.g. 'contacts'")
    icon = models.CharField(max_length=50, blank=True, help_text="Icon name (e.g. for Bootstrap Icons or FontAwesome)")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Module"
        verbose_name_plural = "Modules"

    def __str__(self):
        return self.name


class SubModule(models.Model):
    """Una acción o subsección dentro de un módulo (ej: Ver, Crear, Eliminar)."""
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="submodules")
    name = models.CharField(max_length=100)
    codename = models.SlugField(max_length=150, unique=True, help_text="E.g. 'docs.upload'")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["module__order", "order", "name"]
        verbose_name = "Submodule"
        verbose_name_plural = "Submodules"

    def __str__(self):
        return f"{self.module.name} → {self.name}"


class Role(models.Model):
    """Conjunto reutilizable de permisos (ej: 'Usuario estándar', 'Solo lectura')."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    submodules = models.ManyToManyField(SubModule, through="RolePermission", related_name="roles")

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    """Relación explícita entre un Rol y los SubModules que puede usar."""
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    submodule = models.ForeignKey(SubModule, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("role", "submodule")
        verbose_name = "Role permission"
        verbose_name_plural = "Role permissions"

    def __str__(self):
        return f"{self.role.name} → {self.submodule.codename}"


class UserPermissionOverride(models.Model):
    """Excepción puntual: otorga o quita un permiso a un usuario específico,
    sin importar lo que diga su Role."""
    user = models.ForeignKey("accounts.CustomUser", on_delete=models.CASCADE, related_name="permission_overrides")
    submodule = models.ForeignKey(SubModule, on_delete=models.CASCADE)
    granted = models.BooleanField(default=True, help_text="True = grant extra access, False = revoke role access")

    class Meta:
        unique_together = ("user", "submodule")
        verbose_name = "Permission override"
        verbose_name_plural = "Permission overrides"

    def __str__(self):
        estado = "granted" if self.granted else "revoked"
        return f"{self.user} → {self.submodule.codename} ({estado})"
