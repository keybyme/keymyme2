from django.db import migrations

# Kinds that used to share the single 'general' catalog (Contact, VaultPassword,
# Url, Reminder) plus finanzas.Transaccion, which also pointed at 'general'.
NEW_KINDS = ["contacts", "passwords", "links", "reminders", "finanzas"]


def split_forward(apps, schema_editor):
    """Categories used to be shared: 'general' served Contacts/Passwords/
    Links/Reminders/Finances all at once. Each of those now has its own
    catalog (Category.kind), so this copies every existing 'general' category
    into each new kind, per owner — preserving the data (the category names)
    without losing anything. Existing records still point at their old
    'general'-kind Category row via FK; that link is NOT rewritten here, so
    it'll show as uncategorized in its own module's dropdown until manually
    reassigned to the new copy (expected — see the CLAUDE.md/PR notes)."""
    Category = apps.get_model("vault", "Category")
    general_categories = Category.objects.filter(kind="general")
    for category in general_categories:
        for kind in NEW_KINDS:
            Category.objects.get_or_create(owner=category.owner, name=category.name, kind=kind)


def split_backward(apps, schema_editor):
    Category = apps.get_model("vault", "Category")
    general_categories = Category.objects.filter(kind="general")
    for category in general_categories:
        Category.objects.filter(
            owner_id=category.owner_id, name=category.name, kind__in=NEW_KINDS
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("vault", "0033_alter_category_kind"),
    ]

    operations = [
        migrations.RunPython(split_forward, split_backward),
    ]
