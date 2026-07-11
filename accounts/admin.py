from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username", "email", "role", "storage_quota_gb",
        "storage_used_display", "is_admin_principal", "is_suspended", "is_active",
    )
    list_filter = ("is_admin_principal", "is_suspended", "is_active", "role")
    fieldsets = UserAdmin.fieldsets + (
        ("KeyByMe", {
            "fields": (
                "is_admin_principal", "role", "storage_quota_gb",
                "storage_used_bytes", "is_suspended", "created_by",
            )
        }),
    )
    readonly_fields = ("storage_used_bytes", "created_by")

    def storage_used_display(self, obj):
        gb = obj.storage_used_bytes / (1024 ** 3)
        return f"{gb:.3f} GB de {obj.storage_quota_gb} GB"
    storage_used_display.short_description = "Espacio usado"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
