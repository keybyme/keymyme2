from django.db import migrations


def backfill_address(apps, schema_editor):
    LocationCheckIn = apps.get_model("vault", "LocationCheckIn")
    RouteStop = apps.get_model("vault", "RouteStop")

    stops_by_key = {
        (stop.owner_id, stop.route_type, stop.seq): stop.address
        for stop in RouteStop.objects.exclude(address="")
    }
    if not stops_by_key:
        return

    to_update = []
    for checkin in LocationCheckIn.objects.filter(address="").exclude(route_type=""):
        address = stops_by_key.get((checkin.owner_id, checkin.route_type, checkin.seq))
        if address:
            checkin.address = address
            to_update.append(checkin)
    if to_update:
        LocationCheckIn.objects.bulk_update(to_update, ["address"])


class Migration(migrations.Migration):

    dependencies = [
        ('vault', '0022_locationcheckin_address'),
    ]

    operations = [
        migrations.RunPython(backfill_address, migrations.RunPython.noop),
    ]
