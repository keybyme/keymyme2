from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import include, path, re_path
from django.views.static import serve

from vault.forms import StyledAuthenticationForm


def index(request):
    """Raíz del sitio: sin esto, '/' da 404 (no hay vista de inicio propia)."""
    if request.user.is_authenticated:
        return redirect("vault:contact_list")
    return redirect("login")


urlpatterns = [
    path("", index, name="index"),
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html", authentication_form=StyledAuthenticationForm
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("vault/", include("vault.urls")),
]

if not settings.USE_SPACES:
    urlpatterns += [
        re_path(
            rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]