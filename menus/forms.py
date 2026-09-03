from django import forms

from accounts.models import CustomUser
from vault.forms import TailwindFormMixin


class StorageQuotaForm(TailwindFormMixin, forms.ModelForm):
    """Storage quota field on the simple 'User Access' page (menus/views.py)
    — same field /admin already edits, just reachable without the rest of
    the Django admin user form."""

    class Meta:
        model = CustomUser
        fields = ["storage_quota_gb"]
        labels = {"storage_quota_gb": "Storage quota (GB)"}
        widgets = {
            "storage_quota_gb": forms.NumberInput(attrs={"min": "0", "step": "0.1"}),
        }

    def clean_storage_quota_gb(self):
        quota = self.cleaned_data["storage_quota_gb"]
        if quota < 0:
            raise forms.ValidationError("Storage quota can't be negative.")
        return quota
