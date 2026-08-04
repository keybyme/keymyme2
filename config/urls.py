from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.urls import include, path, re_path
from django.views.static import serve

from vault.forms import StyledAuthenticationForm


def index(request):
    """Raíz del sitio: portal público para visitantes, dashboard para usuarios."""
    if request.user.is_authenticated:
        return redirect(request.user.default_landing_url)
    return render(request, "landing.html")


class StyledLoginView(auth_views.LoginView):
    template_name = "registration/login.html"
    authentication_form = StyledAuthenticationForm

    def get_default_redirect_url(self):
        # Sin esto, LOGIN_REDIRECT_URL (fijo a Contacts) mandaría a un 403
        # a cualquier usuario sin acceso a ese módulo apenas hace login.
        return self.request.user.default_landing_url


urlpatterns = [
    path("", index, name="index"),
    path("admin/", admin.site.urls),
    path("login/", StyledLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("vault/", include("vault.urls")),
    path("finanzas/", include("finanzas.urls")),
    path("schools/", include("schools.urls")),
]

if not settings.USE_SPACES:
    urlpatterns += [
        re_path(
            rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]