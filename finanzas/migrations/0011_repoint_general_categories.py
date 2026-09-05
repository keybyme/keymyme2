from django.db import migrations

# Same fix as vault's 0037_repoint_general_categories, for
# finanzas.Transaccion -- lives here rather than in vault to avoid a
# circular app dependency (finanzas already depends on vault for
# Category; a vault migration reaching into finanzas would depend the
# other way too).


def repoint_forward(apps, schema_editor):
    Category = apps.get_model("vault", "Category")
    Transaccion = apps.get_model("finanzas", "Transaccion")
    for obj in Transaccion.objects.filter(category__kind="general").select_related("category"):
        new_category, _ = Category.objects.get_or_create(
            owner_id=obj.category.owner_id, name=obj.category.name, kind="finanzas",
        )
        obj.category = new_category
        obj.save(update_fields=["category"])


def repoint_backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0010_alter_transaccion_category'),
        ('vault', '0037_repoint_general_categories'),
    ]

    operations = [
        migrations.RunPython(repoint_forward, repoint_backward),
    ]
