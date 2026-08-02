from django.db import migrations

FULL_ACCESS_ROLE_NAME = "Full access"


def assign_forward(apps, schema_editor):
    """Module-based access enforcement is new: without this, every existing
    user would lose access to everything the moment this deploys, since
    nobody has a Role with modules assigned yet. Grant everyone the
    just-seeded 'Full access' role permanently; from here on the admin
    assigns roles by hand going forward."""
    CustomUser = apps.get_model("accounts", "CustomUser")
    Role = apps.get_model("menus", "Role")
    UserRole = apps.get_model("menus", "UserRole")

    role = Role.objects.filter(name=FULL_ACCESS_ROLE_NAME).first()
    if role is None:
        return
    UserRole.objects.bulk_create(
        [UserRole(user=user, role=role) for user in CustomUser.objects.all()],
        ignore_conflicts=True,
    )


def assign_backward(apps, schema_editor):
    UserRole = apps.get_model("menus", "UserRole")
    UserRole.objects.filter(
        role__name=FULL_ACCESS_ROLE_NAME, valid_from__isnull=True, valid_until__isnull=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_remove_customuser_role"),
        ("menus", "0006_seed_modules_and_full_access_role"),
    ]

    operations = [
        migrations.RunPython(assign_forward, assign_backward),
    ]
