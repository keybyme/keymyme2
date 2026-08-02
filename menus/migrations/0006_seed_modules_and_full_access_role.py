from django.db import migrations

MODULES = [
    ("contacts", "Contacts", "users", 10),
    ("passwords", "Passwords", "key", 20),
    ("links", "Links", "link", 30),
    ("files", "Files", "paper-clip", 40),
    ("reminders", "Reminders", "bell", 50),
    ("finanzas_transacciones", "Transactions", "banknotes", 60),
    ("finanzas_cuentas", "Accounts", "credit-card", 70),
    ("finanzas_deudas", "Debts", "credit-card", 80),
    ("categories", "Categories", "tag", 90),
    ("artifacts_qr", "QR", "qr-code", 100),
    ("artifacts_imhere", "I am here", "map-pin", 110),
    ("cars", "My Cars", "car", 120),
]

FULL_ACCESS_ROLE_NAME = "Full access"


def seed_forward(apps, schema_editor):
    Module = apps.get_model("menus", "Module")
    Role = apps.get_model("menus", "Role")

    modules = []
    for codename, name, icon, order in MODULES:
        module, _ = Module.objects.get_or_create(
            codename=codename, defaults={"name": name, "icon": icon, "order": order},
        )
        modules.append(module)

    role, _ = Role.objects.get_or_create(
        name=FULL_ACCESS_ROLE_NAME, defaults={"description": "Access to every module.", "level": 100},
    )
    role.modules.set(modules)


def seed_backward(apps, schema_editor):
    Module = apps.get_model("menus", "Module")
    Role = apps.get_model("menus", "Role")
    Role.objects.filter(name=FULL_ACCESS_ROLE_NAME).delete()
    Module.objects.filter(codename__in=[codename for codename, *_ in MODULES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("menus", "0005_role_modules"),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_backward),
    ]
