from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class PrincipalAdminRequiredMixin(LoginRequiredMixin):
    """For views that manage OTHER users' access (e.g. the 'User Access'
    page) — not just a regular module-gated feature. Only the main admin
    (CustomUser.is_admin_principal) can reach these."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_admin_principal:
            raise PermissionDenied("Only the administrator can access this page.")
        return super().dispatch(request, *args, **kwargs)
