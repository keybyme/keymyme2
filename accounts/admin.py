from django.conf import settings
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.auth.admin import UserAdmin
from django.core.mail import send_mail
from django.template.response import TemplateResponse
from django.utils import timezone

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
                "storage_used_bytes", "is_suspended", "created_by", "approved_at",
                "phone", "carrier", "location_alert_email", "emergency_emails",
            )
        }),
    )
    readonly_fields = ("storage_used_bytes", "created_by", "approved_at")
    inlines = [UserRoleInline]
    actions = ["approve_accounts"]

    @admin.action(description="Approve selected accounts (activate + notify by email)")
    def approve_accounts(self, request, queryset):
        pending = queryset.filter(is_active=False)

        # Confirmed: apply and go back to the change list. Shown as a
        # separate step (instead of applying on the first "Go" click) so an
        # admin can double check who's about to be activated before it
        # happens — mirrors Django's own "Delete selected" confirmation.
        if request.POST.get("post"):
            approved_count = 0
            for user in pending:
                user.is_active = True
                user.approved_at = timezone.now()
                user.save(update_fields=["is_active", "approved_at"])
                if user.email:
                    send_mail(
                        subject="Your KeyByMe account has been approved",
                        message=(
                            f"Hi {user.first_name or user.username},\n\n"
                            "Your KeyByMe account has been approved. You can now log in:\n"
                            "https://keybyme.com/accounts/login/"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                    )
                approved_count += 1
            self.message_user(request, f"Approved {approved_count} account(s).")
            return None

        already_active = queryset.filter(is_active=True)
        context = {
            **self.admin_site.each_context(request),
            "title": "Approve accounts?",
            "queryset": pending,
            "already_active": already_active,
            "opts": self.model._meta,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
        }
        return TemplateResponse(
            request, "admin/accounts/customuser/approve_accounts_confirmation.html", context,
        )

    def get_deleted_objects(self, objs, request):
        # Django's own delete-confirm page (both the single-object delete
        # view and the bulk "Delete selected" action) previews what would
        # be deleted with its OWN plain FK-graph collector, independent of
        # CustomUser.delete()'s override below -- that preview hits the
        # exact same PROTECT relations (Category/Cuenta) explained there,
        # and would otherwise show a "Cannot delete" page that blocks
        # deletion outright, for any user who has so much as one Contact
        # filed under a Category or one Transaccion posted to a Cuenta —
        # i.e. almost any real account. Clearing `protected` here is safe
        # specifically because CustomUser.delete() actually does clean
        # all of that up first, in the right order, before those
        # constraints would ever be checked for real.
        deleted_objects, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        return deleted_objects, model_count, perms_needed, []

    def delete_queryset(self, request, queryset):
        # Django's default here is a single bulk queryset.delete() --
        # which, like any bulk delete, never calls a model's own delete()
        # method, only raw SQL DELETEs. CustomUser.delete() is overridden
        # to clean up owned data that plain CASCADE can't handle safely
        # (see its docstring) -- looping and calling .delete() per user is
        # what makes the "Delete selected" bulk action in this list
        # actually run that, same as the single-object delete confirm
        # page already does via obj.delete().
        for user in queryset:
            user.delete()

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
            # Created directly by the admin, so it's implicitly pre-approved
            # — keeps accounts/signals.py's email_confirmed handler from
            # ever touching an account that was never part of the
            # self-registration/approval flow to begin with.
            obj.approved_at = timezone.now()
        super().save_model(request, obj, form, change)
