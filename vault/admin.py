from django import forms
from django.contrib import admin

from .models import Category, Contact, LocationCheckIn, VaultPassword, MediaFile, Reminder, RouteStop, Url


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner")
    list_filter = ("owner",)
    search_fields = ("name",)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "category", "phone", "email", "address", "updated_at")
    list_filter = ("owner", "category")
    search_fields = ("name", "phone", "email", "address")


class VaultPasswordAdminForm(forms.ModelForm):
    password = forms.CharField(
        label="Password",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Leave blank to keep the current password unchanged.",
    )

    class Meta:
        model = VaultPassword
        exclude = ("_encrypted_password",)

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_password = self.cleaned_data.get("password")
        if raw_password:
            instance.set_password(raw_password)
        if commit:
            instance.save()
        return instance


@admin.register(VaultPassword)
class VaultPasswordAdmin(admin.ModelAdmin):
    form = VaultPasswordAdminForm
    list_display = ("site_name", "owner", "category", "username", "updated_at")
    list_filter = ("owner", "category")
    search_fields = ("site_name", "username")


@admin.register(Url)
class UrlAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "category", "url", "updated_at")
    list_filter = ("owner", "category")
    search_fields = ("name", "url")


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    list_display = ("original_name", "owner", "category", "file_type", "file_size_bytes", "uploaded_at")
    list_filter = ("file_type", "owner", "category")
    search_fields = ("original_name",)


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "category", "remind_at", "is_completed")
    list_filter = ("is_completed", "owner", "category")


@admin.register(LocationCheckIn)
class LocationCheckInAdmin(admin.ModelAdmin):
    list_display = ("owner", "check_date", "seq", "stop_number", "route_type", "created_at", "owner_route", "latitude", "longitude", "remarks")
    list_filter = ("owner",)

    def owner_route(self, obj):
        return obj.owner.route
    owner_route.short_description = "Route"
    owner_route.admin_order_field = "owner__route"


@admin.register(RouteStop)
class RouteStopAdmin(admin.ModelAdmin):
    list_display = ("owner", "route_type", "seq", "remarks")
    list_filter = ("owner", "route_type")
