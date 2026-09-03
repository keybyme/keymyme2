from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView

from .forms import StorageQuotaForm
from .mixins import PrincipalAdminRequiredMixin
from .models import Module, UserModuleOverride

CustomUser = get_user_model()


class UserAccessListView(PrincipalAdminRequiredMixin, ListView):
    """Simpler alternative to /admin for the things the admin actually does
    often: pick a user, turn modules on/off for their account, adjust their
    storage quota. Excludes other main admins — is_admin_principal already
    grants everything, so toggling modules for one would have no visible
    effect."""
    model = CustomUser
    template_name = "menus/user_access_list.html"
    context_object_name = "users"

    def get_queryset(self):
        return CustomUser.objects.filter(is_admin_principal=False).order_by("username")


class UserAccessDetailView(PrincipalAdminRequiredMixin, DetailView):
    model = CustomUser
    template_name = "menus/user_access_detail.html"
    context_object_name = "target_user"

    def get_queryset(self):
        return CustomUser.objects.filter(is_admin_principal=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        modules = Module.objects.filter(is_active=True)
        context["modules"] = modules
        context["granted_codenames"] = {
            module.codename for module in modules if self.object.has_module_access(module.codename)
        }
        context["storage_used_gb"] = round(self.object.storage_used_bytes / (1024 ** 3), 3)
        context.setdefault("quota_form", StorageQuotaForm(instance=self.object))
        return context

    def post(self, request, *args, **kwargs):
        self.object = get_object_or_404(self.get_queryset(), pk=kwargs["pk"])

        quota_form = StorageQuotaForm(request.POST, instance=self.object)
        if not quota_form.is_valid():
            return render(request, self.template_name, self.get_context_data(quota_form=quota_form))
        quota_form.save()

        selected_codenames = set(request.POST.getlist("modules"))

        # Explicit True/False for every module, not just the ones that
        # changed: this page becomes the one place that decides a user's
        # module access from here on, so what's checked here is exactly
        # what they'll have — no surprises from a Role changing later.
        for module in Module.objects.filter(is_active=True):
            UserModuleOverride.objects.update_or_create(
                user=self.object, module=module,
                defaults={"granted": module.codename in selected_codenames},
            )

        messages.success(request, f"Updated access for {self.object.username}.")
        return redirect(reverse("menus:user_access_detail", args=[self.object.pk]))
