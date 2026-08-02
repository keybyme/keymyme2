from django.contrib import admin

from .models import Module, SubModule, Role, RolePermission, UserRole, UserPermissionOverride


class SubModuleInline(admin.TabularInline):
    model = SubModule
    extra = 1


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("name", "codename", "order", "is_active")
    list_editable = ("order", "is_active")
    inlines = [SubModuleInline]


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 1


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "description")
    search_fields = ("name",)
    filter_horizontal = ("modules",)
    inlines = [RolePermissionInline]


@admin.register(SubModule)
class SubModuleAdmin(admin.ModelAdmin):
    list_display = ("name", "module", "codename", "is_active")
    list_filter = ("module", "is_active")


@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ("user", "submodule", "granted")
    list_filter = ("granted",)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "valid_from", "valid_until")
    list_filter = ("role",)
    autocomplete_fields = ("user",)
