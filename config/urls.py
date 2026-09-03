from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import include, path, re_path
from django.views.static import serve


def index(request):
    """Raíz del sitio: portal público para visitantes, dashboard para usuarios."""
    if request.user.is_authenticated:
        return redirect(request.user.default_landing_url)
    return render(request, "landing.html")


urlpatterns = [
    path("", index, name="index"),
    path("privacy/", lambda request: render(request, "privacy.html"), name="privacy"),
    path("admin/", admin.site.urls),
    # Login/signup/logout/password-reset, "Sign in with Google" incluido —
    # ver accounts/adapters.py, accounts/forms.py, y config/settings.py.
    path("accounts/", include("allauth.urls")),
    path("menus/", include("menus.urls")),
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