from django.db import migrations

MODULE = ("artifacts_medical", "Medical Records", "heart", 107)

FULL_ACCESS_ROLE_NAME = "Full access"


def seed_forward(apps, schema_editor):
    Module = apps.get_model("menus", "Module")
    Role = apps.get_model("menus", "Role")

    codename, name, icon, order = MODULE
    module, _ = Module.objects.get_or_create(
        codename=codename, defaults={"name": name, "icon": icon, "order": order},
    )

    role = Role.objects.filter(name=FULL_ACCESS_ROLE_NAME).first()
    if role is not None:
        role.modules.add(module)


def seed_backward(apps, schema_editor):
    Module = apps.get_model("menus", "Module")
    Module.objects.filter(codename=MODULE[0]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("menus", "0009_seed_mcps_module"),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_backward),
    ]
