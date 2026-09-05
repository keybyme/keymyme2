from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from schools.models import LEFTRIGHT_SHEET_RETENTION_DAYS, LeftRightSheetUpload


class Command(BaseCommand):
    help = (
        f"Deletes LeftRightSheetUpload rows (and their underlying files) more than "
        f"{LEFTRIGHT_SHEET_RETENTION_DAYS} days old. Uploads are only ever a scratch input for "
        f"drafting LeftRightRow rows (see LeftRightGenerateRowsFromSheetView) -- not meant to be "
        f"kept around. Meant to run daily via crontab, same pattern as send_due_reminders."
    )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=LEFTRIGHT_SHEET_RETENTION_DAYS)
        # One at a time, not a bulk queryset .delete() -- LeftRightSheetUpload.delete()
        # is overridden to also delete the underlying file, which a bulk delete would
        # skip (same reasoning as MediaFile.delete() in vault).
        stale_uploads = list(LeftRightSheetUpload.objects.filter(uploaded_at__lt=cutoff))
        for upload in stale_uploads:
            upload.delete()
        self.stdout.write(self.style.SUCCESS(
            f"Deleted {len(stale_uploads)} sheet upload(s) older than {LEFTRIGHT_SHEET_RETENTION_DAYS} days."
        ))
