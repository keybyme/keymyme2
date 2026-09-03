from django.db import migrations


def set_keybyme_site(apps, schema_editor):
    """django.contrib.sites ships a default Site row (id=1) pointed at
    'example.com' — used by django-allauth in email templates
    (current_site.domain/.name) and OAuth callback URLs. Point it at the
    real domain."""
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        id=1, defaults={"domain": "keybyme.com", "name": "KeyByMe"}
    )


def revert_to_example_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.filter(id=1).update(domain="example.com", name="example.com")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_customuser_emergency_emails"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(set_keybyme_site, revert_to_example_site),
    ]
