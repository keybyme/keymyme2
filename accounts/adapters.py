from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse


class KeyByMeAccountAdapter(DefaultAccountAdapter):
    """Self-registered accounts (email/password here, Google in
    KeyByMeSocialAccountAdapter below) stay inactive until the admin
    approves them from /admin — see CLAUDE.md 'centralized user
    administration'. is_suspended (CustomUser) is also enforced here since
    nothing else in the codebase currently checks it.

    NOTE: unlike the Google path, this account is NOT deactivated at
    save_user() time. allauth's pre_login() (below) runs before the mandatory
    email-verification stage on every login attempt, including the implicit
    one right after signup — deactivating this early would block that first
    attempt before the verification email even gets sent. Deactivation
    happens once the email is actually confirmed instead — see
    accounts/signals.py:handle_email_confirmed."""

    def respond_user_inactive(self, request, user):
        messages.info(
            request,
            "Your account is pending administrator approval. "
            "You'll be able to log in once it's approved.",
        )
        return super().respond_user_inactive(request, user)

    def pre_login(self, request, user, **kwargs):
        if user.is_suspended:
            messages.error(
                request, "This account has been suspended. Contact the administrator."
            )
            return HttpResponseRedirect(reverse("account_login"))
        return super().pre_login(request, user, **kwargs)

    def get_login_redirect_url(self, request):
        # Mismo criterio que antes (StyledLoginView.get_default_redirect_url,
        # ahora removido): el primer módulo al que el usuario tenga acceso,
        # no una URL fija — ver CustomUser.default_landing_url.
        return request.user.default_landing_url


class KeyByMeSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Google sign-in: mismo gate is_active=False que el signup por email
    (KeyByMeAccountAdapter) — solo aplica a cuentas nuevas; un login con
    Google de una cuenta ya aprobada no la vuelve a desactivar."""

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        user.is_active = False
        user.save(update_fields=["is_active"])
        return user
