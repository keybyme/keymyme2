import json
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from schools.models import School

# Montgomery County, MD Open Data Portal — "Public Schools" dataset (Socrata SODA API).
# https://data.montgomerycountymd.gov/d/772q-4wm8
DATASET_URL = "https://data.montgomerycountymd.gov/resource/772q-4wm8.json?$limit=1000"

CATEGORY_TO_SCHOOL_TYPE = {
    "ELEMENTARY SCHOOLS": School.SchoolType.ELEMENTARY,
    "MIDDLE SCHOOLS": School.SchoolType.MIDDLE,
    "HIGH SCHOOLS": School.SchoolType.HIGH,
}


class Command(BaseCommand):
    help = (
        "Fetches the current list of Montgomery County, MD public schools (elementary/middle/"
        "high) from the county's Open Data Portal and upserts them into the School table, "
        "matching on school name. Safe to re-run any time to refresh addresses or pick up "
        "schools that opened/closed since the last sync."
    )

    def handle(self, *args, **options):
        request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "KeyByMe/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                rows = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not fetch MCPS schools dataset: {exc}")

        created_count = 0
        updated_count = 0
        skipped_count = 0
        seen_names = set()

        for row in rows:
            school_type = CATEGORY_TO_SCHOOL_TYPE.get((row.get("category") or "").strip().upper())
            name = (row.get("school_name") or "").strip()
            address = (row.get("address") or "").strip()

            if not school_type or not name or not address:
                skipped_count += 1
                continue

            seen_names.add(name)
            _, created = School.objects.update_or_create(
                name=name,
                defaults={
                    "school_type": school_type,
                    "address": address,
                    "city": (row.get("city") or "").strip(),
                    "zip_code": str(row.get("zip_code") or "").strip(),
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        stale_count, _ = School.objects.exclude(name__in=seen_names).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Schools synced: {created_count} created, {updated_count} updated, "
                f"{stale_count} removed (no longer in county dataset), {skipped_count} skipped."
            )
        )
