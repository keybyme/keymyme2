from django.db import migrations, models


def backfill_approved_at(apps, schema_editor):
    """Every account active as of this migration is either an admin-created
    account or an already-approved signup — none of them should ever be
    touched by accounts/signals.py's email_confirmed handler again. Marks
    them all as approved now, using date_joined as a reasonable stand-in
    for "when" since the real approval time was never recorded before this."""
    CustomUser = apps.get_model("accounts", "CustomUser")
    CustomUser.objects.filter(is_active=True, approved_at__isnull=True).update(
        approved_at=models.F("date_joined")
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_customuser_approved_at"),
    ]

    operations = [
        migrations.RunPython(backfill_approved_at, noop_reverse),
    ]
