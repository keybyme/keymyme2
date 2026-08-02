from django.db import migrations


def remove_forward(apps, schema_editor):
    """Categories is now accessible to every logged-in user regardless of
    role (see vault.views.Category*View), so it's no longer a toggleable
    module — keeping it in Role.modules would just be a dead switch."""
    Module = apps.get_model("menus", "Module")
    Module.objects.filter(codename="categories").delete()


def remove_backward(apps, schema_editor):
    Module = apps.get_model("menus", "Module")
    Module.objects.get_or_create(
        codename="categories", defaults={"name": "Categories", "icon": "tag", "order": 90},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("menus", "0006_seed_modules_and_full_access_role"),
    ]

    operations = [
        migrations.RunPython(remove_forward, remove_backward),
    ]
