from django.db import models


class Module(models.Model):
    """Un módulo principal del sistema (ej: Contactos, Passwords, Documentos)."""
    name = models.CharField(max_length=100, unique=True)
    codename = models.SlugField(max_length=100, unique=True, help_text="Identificador usado en el código, ej: 'contacts'")
    icon = models.CharField(max_length=50, blank=True, help_text="Nombre de ícono (ej: para Bootstrap Icons o FontAwesome)")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Módulo"
        verbose_name_plural = "Módulos"

    def __str__(self):
        return self.name


class SubModule(models.Model):
    """Una acción o subsección dentro de un módulo (ej: Ver, Crear, Eliminar)."""
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="submodules")
    name = models.CharField(max_length=100)
    codename = models.SlugField(max_length=150, unique=True, help_text="Ej: 'docs.upload'")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["module__order", "order", "name"]
        verbose_name = "Submódulo"
        verbose_name_plural = "Submódulos"

    def __str__(self):
        return f"{self.module.name} → {self.name}"


class Role(models.Model):
    """Conjunto reutilizable de permisos (ej: 'Usuario estándar', 'Solo lectura')."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    submodules = models.ManyToManyField(SubModule, through="RolePermission", related_name="roles")

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    """Relación explícita entre un Rol y los SubModules que puede usar."""
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    submodule = models.ForeignKey(SubModule, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("role", "submodule")
        verbose_name = "Permiso de rol"
        verbose_name_plural = "Permisos de rol"

    def __str__(self):
        return f"{self.role.name} → {self.submodule.codename}"


class UserPermissionOverride(models.Model):
    """Excepción puntual: otorga o quita un permiso a un usuario específico,
    sin importar lo que diga su Role."""
    user = models.ForeignKey("accounts.CustomUser", on_delete=models.CASCADE, related_name="permission_overrides")
    submodule = models.ForeignKey(SubModule, on_delete=models.CASCADE)
    granted = models.BooleanField(default=True, help_text="True = otorgar acceso extra, False = revocar acceso del rol")

    class Meta:
        unique_together = ("user", "submodule")
        verbose_name = "Excepción de permiso"
        verbose_name_plural = "Excepciones de permiso"

    def __str__(self):
        estado = "otorgado" if self.granted else "revocado"
        return f"{self.user} → {self.submodule.codename} ({estado})"
