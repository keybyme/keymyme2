from django.db import migrations


def renumber_by_tens(apps, schema_editor):
    """Existing LeftRightRow.order values were assigned 0, 1, 2, 3... (one per
    row added). The edit page now shows this as a "sequence" column spaced by
    tens (10, 20, 30...) so a row can be inserted between two others by
    picking a number in between (e.g. 35 between 30 and 40) without having to
    renumber anything else. Re-space every existing LeftRight's rows into
    that scheme once, preserving their current relative order."""
    LeftRightRow = apps.get_model("schools", "LeftRightRow")
    LeftRight = apps.get_model("schools", "LeftRight")
    for leftright in LeftRight.objects.all():
        rows = list(leftright.rows.order_by("order", "pk"))
        for position, row in enumerate(rows, start=1):
            new_order = position * 10
            if row.order != new_order:
                row.order = new_order
                row.save(update_fields=["order"])


def noop_reverse(apps, schema_editor):
    # Not reversible in any meaningful way -- the original 0,1,2,3... spacing
    # carried no information worth restoring.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("schools", "0015_depotlink_name_alter_depotlink_url"),
    ]

    operations = [
        migrations.RunPython(renumber_by_tens, noop_reverse),
    ]
