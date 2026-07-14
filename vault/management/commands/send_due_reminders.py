from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from vault.models import Reminder


class Command(BaseCommand):
    help = (
        "Envía por correo (y por SMS si el recordatorio tiene teléfono y Twilio está "
        "configurado) los recordatorios pendientes (remind_at ya llegó, no completados "
        "y con algún aviso todavía sin enviar). Pensado para correr periódicamente vía "
        "cron / Scheduled Job (ej. cada 5-15 minutos)."
    )

    def handle(self, *args, **options):
        twilio_client = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        due_reminders = Reminder.objects.filter(
            is_completed=False,
            remind_at__lte=timezone.now(),
        ).filter(
            Q(email_sent_at__isnull=True)
            | (Q(recipient_phone__gt="") & Q(sms_sent_at__isnull=True))
        ).select_related("owner")

        emails_sent = 0
        sms_sent = 0
        now = timezone.now()

        for reminder in due_reminders:
            update_fields = []

            if reminder.email_sent_at is None:
                recipient = reminder.notification_email
                if not recipient:
                    self.stderr.write(
                        f"Recordatorio #{reminder.pk} ({reminder.title!r}) sin correo de destino, se omite."
                    )
                else:
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
                        self.stderr.write(f"Error enviando correo del recordatorio #{reminder.pk} a {recipient}: {exc}")
                    else:
                        reminder.email_sent_at = now
                        update_fields.append("email_sent_at")
                        emails_sent += 1

            if reminder.recipient_phone and reminder.sms_sent_at is None:
                if twilio_client is None:
                    self.stderr.write(
                        f"Recordatorio #{reminder.pk} ({reminder.title!r}) tiene teléfono pero "
                        "Twilio no está configurado (TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN), se omite el SMS."
                    )
                else:
                    try:
                        twilio_client.messages.create(
                            body=f"Recordatorio: {reminder.title}",
                            from_=settings.TWILIO_FROM_NUMBER,
                            to=reminder.recipient_phone,
                        )
                    except TwilioRestException as exc:
                        self.stderr.write(f"Error enviando SMS del recordatorio #{reminder.pk} a {reminder.recipient_phone}: {exc}")
                    else:
                        reminder.sms_sent_at = now
                        update_fields.append("sms_sent_at")
                        sms_sent += 1

            if update_fields:
                reminder.save(update_fields=update_fields)

        self.stdout.write(self.style.SUCCESS(f"Correos enviados: {emails_sent}. SMS enviados: {sms_sent}."))
