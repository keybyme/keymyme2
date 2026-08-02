from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from menus.models import UserRole

from .models import CustomUser


class UserRoleInline(admin.TabularInline):
    model = UserRole
    fk_name = "user"
    extra = 1
    fields = ("role", "valid_from", "valid_until")
    autocomplete_fields = ("role",)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username", "email", "roles_display", "route", "storage_quota_gb",
        "storage_used_display", "is_admin_principal", "is_suspended", "is_active",
    )
    list_filter = ("is_admin_principal", "is_suspended", "is_active", "user_roles__role")
    fieldsets = UserAdmin.fieldsets + (
        ("KeyByMe", {
            "fields": (
                "is_admin_principal", "route", "storage_quota_gb",
                "storage_used_bytes", "is_suspended", "created_by",
                "phone", "carrier", "location_alert_email",
            )
        }),
    )
    readonly_fields = ("storage_used_bytes", "created_by")
    inlines = [UserRoleInline]

    def storage_used_display(self, obj):
        gb = obj.storage_used_bytes / (1024 ** 3)
        return f"{gb:.3f} GB of {obj.storage_quota_gb} GB"
    storage_used_display.short_description = "Storage used"

    def roles_display(self, obj):
        return ", ".join(role.name for role in obj.active_roles) or "—"
    roles_display.short_description = "Active roles"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
