from django.db import migrations

# (model_name, target_kind) -- these used to share a single Category
# catalog before it was split per module (Contact/VaultPassword/Url/
# Reminder by 0034_split_general_categories_per_module; MediaFile earlier
# still, when 0027 first introduced Category.kind at all -- every
# Category row that existed before that point defaulted to 'general',
# including ones actually in use by MediaFile at the time). Both splits
# created the per-kind copies (same owner + name) but deliberately left
# existing FKs still pointing at the old 'general' row -- meaning the
# category-filtered dropdown on each list page (scoped to the new kind)
# never actually matched what was really on the record, silently showing
# "no results" for a category that very much has records, just filed
# under the old 'general' copy instead of the new per-kind one. This
# finishes the job: repoint every such FK to the matching per-kind
# category, creating it if it somehow doesn't already exist (defensive --
# both splits should already have created one for every 'general'
# category that existed when they ran).
MODEL_KINDS = [
    ("Contact", "contacts"),
    ("VaultPassword", "passwords"),
    ("Url", "links"),
    ("Reminder", "reminders"),
    ("MediaFile", "files"),
]


def repoint_forward(apps, schema_editor):
    Category = apps.get_model("vault", "Category")
    for model_name, target_kind in MODEL_KINDS:
        Model = apps.get_model("vault", model_name)
        for obj in Model.objects.filter(category__kind="general").select_related("category"):
            new_category, _ = Category.objects.get_or_create(
                owner_id=obj.category.owner_id, name=obj.category.name, kind=target_kind,
            )
            obj.category = new_category
            obj.save(update_fields=["category"])


def repoint_backward(apps, schema_editor):
    # Not meaningfully reversible -- the fact that a record used to point
    # at the 'general'-kind category isn't recorded anywhere once forward
    # has run. No-op, same as 0034's own backward for the categories it
    # created.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0036_alter_routesheetupload_uploaded_by'),
    ]

    operations = [
        migrations.RunPython(repoint_forward, repoint_backward),
    ]
