from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from vault.models import Reminder


class Command(BaseCommand):
    help = (
        "Emails pending reminders (remind_at already reached, not completed, and no email sent "
        "yet). Reminders with no frequency are deleted after being sent; those with a frequency "
        "(daily/weekly/monthly) are rescheduled for the next occurrence. Meant to run "
        "periodically via cron / Scheduled Job (e.g. every 5-15 minutes)."
    )

    def handle(self, *args, **options):
        due_reminders = Reminder.objects.filter(
            is_completed=False,
            email_sent_at__isnull=True,
            remind_at__lte=timezone.now(),
        ).select_related("owner")

        sent_count = 0
        deleted_count = 0

        for reminder in due_reminders:
            recipient = reminder.notification_email
            if not recipient:
                self.stderr.write(
                    f"Reminder #{reminder.pk} ({reminder.title!r}) has no destination email, skipping."
                )
                continue

            try:
                send_mail(
                    subject=f"Reminder: {reminder.title}",
                    message=(
                        f"{reminder.title}\n\n"
                        f"{reminder.description}\n\n"
                        f"Date: {timezone.localtime(reminder.remind_at):%m/%d/%Y %I:%M %p}"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient],
                    fail_silently=False,
                )
            except Exception as exc:
                self.stderr.write(f"Error sending reminder #{reminder.pk} to {recipient}: {exc}")
                continue

            sent_count += 1
            next_at = reminder.next_occurrence()
            if next_at is None:
                reminder.delete()
                deleted_count += 1
            else:
                reminder.remind_at = next_at
                reminder.email_sent_at = None
                reminder.save(update_fields=["remind_at", "email_sent_at"])

        self.stdout.write(self.style.SUCCESS(
            f"Emails sent: {sent_count}. Reminders deleted (no frequency): {deleted_count}."
        ))
