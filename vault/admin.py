from django import forms
from django.contrib import admin

from .models import Category, Contact, LocationCheckIn, VaultPassword, MediaFile, Reminder, Url


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
    list_display = ("owner", "created_at", "latitude", "longitude", "ruta", "remarks")
    list_filter = ("owner",)
