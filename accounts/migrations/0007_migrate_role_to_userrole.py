from django.db import migrations


def migrate_role_forward(apps, schema_editor):
    CustomUser = apps.get_model("accounts", "CustomUser")
    UserRole = apps.get_model("menus", "UserRole")
    UserRole.objects.bulk_create(
        UserRole(user_id=user_id, role_id=role_id)
        for user_id, role_id in CustomUser.objects.exclude(role__isnull=True).values_list("id", "role_id")
    )


def migrate_role_backward(apps, schema_editor):
    CustomUser = apps.get_model("accounts", "CustomUser")
    UserRole = apps.get_model("menus", "UserRole")
    for user_role in UserRole.objects.filter(valid_from__isnull=True, valid_until__isnull=True):
        CustomUser.objects.filter(pk=user_role.user_id, role__isnull=True).update(role_id=user_role.role_id)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_customuser_route"),
        ("menus", "0004_userrole"),
    ]

    operations = [
        migrations.RunPython(migrate_role_forward, migrate_role_backward),
    ]
