from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from vault.models import Reminder


class Command(BaseCommand):
    help = (
        "Envía por correo los recordatorios pendientes (remind_at ya llegó, no completados "
        "y sin correo enviado todavía). Pensado para correr periódicamente vía cron / "
        "Scheduled Job (ej. cada 5-15 minutos)."
    )

    def handle(self, *args, **options):
        due_reminders = Reminder.objects.filter(
            is_completed=False,
            email_sent_at__isnull=True,
            remind_at__lte=timezone.now(),
        ).select_related("owner")

        sent_count = 0
        for reminder in due_reminders:
            recipient = reminder.notification_email
            if not recipient:
                self.stderr.write(
                    f"Recordatorio #{reminder.pk} ({reminder.title!r}) sin correo de destino, se omite."
                )
                continue

            try:
                send_mail(
                    subject=f"Recordatorio: {reminder.title}",
                    message=(
                        f"{reminder.title}\n\n"
                        f"{reminder.description}\n\n"
                        f"Fecha: {timezone.localtime(reminder.remind_at):%d/%m/%Y %H:%M}"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient],
                    fail_silently=False,
                )
            except Exception as exc:
                self.stderr.write(f"Error enviando recordatorio #{reminder.pk} a {recipient}: {exc}")
                continue

            reminder.email_sent_at = timezone.now()
            reminder.save(update_fields=["email_sent_at"])
            sent_count += 1

        self.stdout.write(self.style.SUCCESS(f"Correos enviados: {sent_count}"))
