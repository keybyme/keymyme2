from django.db import migrations

MODULE = ("transportation", "Transportation", "car", 115)


def seed_forward(apps, schema_editor):
    """New module for the Transportation section (starts with Lefts &
    Rights — see schools/views.py) — meant to eventually absorb MCPS and I
    am here, which is why it's a module of its own rather than folded into
    either. Granted to every Role that currently has 'artifacts_mcps'
    (Lefts & Rights' old home), so moving it doesn't drop anyone's access."""
    Module = apps.get_model("menus", "Module")
    Role = apps.get_model("menus", "Role")

    codename, name, icon, order = MODULE
    module, _ = Module.objects.get_or_create(
        codename=codename, defaults={"name": name, "icon": icon, "order": order},
    )

    for role in Role.objects.filter(modules__codename="artifacts_mcps"):
        role.modules.add(module)


def seed_backward(apps, schema_editor):
    Module = apps.get_model("menus", "Module")
    Module.objects.filter(codename=MODULE[0]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("menus", "0011_usermoduleoverride"),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_backward),
    ]
