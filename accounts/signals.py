from allauth.account.signals import email_confirmed, user_signed_up
from django.conf import settings
from django.core.mail import send_mail
from django.dispatch import receiver
from django.urls import reverse


def _notify_admins_pending_approval(user):
    """Emails every active main-admin that a new signup is waiting for them
    in /admin. Called once a signup is actually ready for a human to look
    at — see the two receivers below for why that point differs by path."""
    from .models import CustomUser

    admin_emails = list(
        CustomUser.objects.filter(is_admin_principal=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not admin_emails:
        return

    admin_path = reverse("admin:accounts_customuser_change", args=[user.pk])
    display_name = user.get_full_name() or user.username
    send_mail(
        subject=f"KeyByMe: new signup pending approval ({user.email})",
        message=(
            f"{display_name} ({user.email}) just signed up for KeyByMe and is "
            f"waiting for your approval.\n\n"
            f"Review and activate the account here:\n"
            f"https://keybyme.com{admin_path}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=admin_emails,
    )


@receiver(user_signed_up)
def handle_user_signed_up(request, user, **kwargs):
    """Google signups skip email verification entirely (Google already
    verified the address — see SOCIALACCOUNT_EMAIL_VERIFICATION), and
    KeyByMeSocialAccountAdapter.save_user already set is_active=False by the
    time this fires, so this signal is the only one they ever get; notify
    right away. Email/password signups are handled by handle_email_confirmed
    below instead, once they've actually verified — notifying here would be
    premature (and the account isn't deactivated yet either, see
    KeyByMeAccountAdapter)."""
    if kwargs.get("sociallogin") is not None:
        _notify_admins_pending_approval(user)


@receiver(email_confirmed)
def handle_email_confirmed(request, email_address, **kwargs):
    """Fires both for a brand-new signup's first verification AND for an
    already-approved user re-verifying a changed email (see account/email
    management) — only the former should gate the account and notify the
    admin. user.last_login is None exactly for the first case: a self-
    registered account that has never completed a login, because the
    mandatory-verification stage was blocking it until just now."""
    user = email_address.user
    if user.last_login is not None or not user.is_active:
        return
    user.is_active = False
    user.save(update_fields=["is_active"])
    _notify_admins_pending_approval(user)
