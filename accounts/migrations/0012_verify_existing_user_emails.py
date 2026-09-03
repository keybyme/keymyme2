from django.db import migrations


def verify_existing_emails(apps, schema_editor):
    """Every account created before django-allauth was added (i.e. every
    account that exists as of this migration) never went through allauth's
    signup flow, so none of them have an EmailAddress row — and with
    ACCOUNT_EMAIL_VERIFICATION='mandatory', allauth treats a missing/
    unverified EmailAddress as reason to block login, regardless of whether
    the password is correct. These accounts were created directly by the
    admin (or via createsuperuser), so their email is already trusted;
    back-fill a verified, primary EmailAddress for each so login keeps
    working exactly as it did before this feature shipped."""
    CustomUser = apps.get_model("accounts", "CustomUser")
    EmailAddress = apps.get_model("account", "EmailAddress")
    for user in CustomUser.objects.exclude(email=""):
        EmailAddress.objects.get_or_create(
            user=user, email=user.email, defaults={"verified": True, "primary": True}
        )


def noop_reverse(apps, schema_editor):
    # Deliberately not deleting EmailAddress rows on reverse: by the time
    # anyone would roll this back, they may belong to genuine allauth
    # signups too, and this migration can't tell the two apart.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_update_site_domain"),
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(verify_existing_emails, noop_reverse),
    ]
