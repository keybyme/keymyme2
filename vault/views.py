import base64
import datetime as dt
import hmac
import io
import json
from decimal import Decimal, InvalidOperation
from itertools import groupby

import qrcode
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.mail import send_mail
from django.core.management import call_command
from django.core.paginator import Paginator
from django.db.models import Max
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView, View,
)

from .contact_import import parse_csv, parse_vcard
from .forms import (
    CategoryForm,
    ContactForm,
    ContactImportForm,
    LocationAlertEmailForm,
    LocationCheckInForm,
    MediaFileForm,
    QRCodeForm,
    ReminderForm,
    UrlForm,
    VaultPasswordForm,
)
from .mixins import AjaxPartialTemplateMixin, OwnerCreateMixin, OwnerQuerysetMixin, SearchableListMixin, UserFormKwargsMixin
from .models import Category, Contact, LocationCheckIn, MediaFile, Reminder, RouteStop, Url, VaultPassword


# ---------- Categories ----------

class CategoryListView(OwnerQuerysetMixin, ListView):
    model = Category
    template_name = "vault/category_list.html"
    context_object_name = "categories"
    paginate_by = 15


class CategoryCreateView(OwnerCreateMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "vault/category_form.html"
    success_url = reverse_lazy("vault:category_list")


class CategoryUpdateView(UserFormKwargsMixin, OwnerQuerysetMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "vault/category_form.html"
    success_url = reverse_lazy("vault:category_list")


class CategoryDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Category
    template_name = "vault/category_confirm_delete.html"
    success_url = reverse_lazy("vault:category_list")


# ---------- Contacts ----------

class ContactListView(AjaxPartialTemplateMixin, SearchableListMixin, OwnerQuerysetMixin, ListView):
    model = Contact
    template_name = "vault/contact_list.html"
    ajax_template_name = "vault/_contact_results.html"
    context_object_name = "contacts"
    paginate_by = 15
    search_fields = ("name", "phone", "email", "address", "notes")


class ContactCreateView(OwnerCreateMixin, CreateView):
    model = Contact
    form_class = ContactForm
    template_name = "vault/contact_form.html"
    success_url = reverse_lazy("vault:contact_list")


class ContactUpdateView(UserFormKwargsMixin, OwnerQuerysetMixin, UpdateView):
    model = Contact
    form_class = ContactForm
    template_name = "vault/contact_form.html"
    success_url = reverse_lazy("vault:contact_list")


class ContactDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Contact
    template_name = "vault/contact_confirm_delete.html"
    success_url = reverse_lazy("vault:contact_list")


class ContactImportView(UserFormKwargsMixin, LoginRequiredMixin, FormView):
    """Importa contactos en bloque desde un .vcf (vCard) o un .csv."""
    template_name = "vault/contact_import.html"
    form_class = ContactImportForm
    success_url = reverse_lazy("vault:contact_list")

    def form_valid(self, form):
        uploaded_file = form.cleaned_data["file"]
        category = form.cleaned_data.get("category")
        text = uploaded_file.read().decode("utf-8-sig", errors="replace")

        if uploaded_file.name.lower().endswith(".csv"):
            parsed_contacts = parse_csv(text)
        else:
            parsed_contacts = parse_vcard(text)

        new_contacts = [
            Contact(
                owner=self.request.user,
                name=data["name"][:150],
                phone=data["phone"][:30],
                email=data["email"][:254],
                address=data["address"][:255],
                notes=data["notes"],
                category=category,
            )
            for data in parsed_contacts
        ]
        Contact.objects.bulk_create(new_contacts)

        if new_contacts:
            messages.success(self.request, f"Imported {len(new_contacts)} contact(s).")
        else:
            messages.warning(self.request, "No valid contacts were found in the file.")

        return super().form_valid(form)


# ---------- Vault Passwords ----------

class PasswordListView(AjaxPartialTemplateMixin, SearchableListMixin, OwnerQuerysetMixin, ListView):
    model = VaultPassword
    template_name = "vault/password_list.html"
    ajax_template_name = "vault/_password_results.html"
    context_object_name = "passwords"
    paginate_by = 15
    search_fields = ("site_name", "username", "site_url", "notes")
    # OJO: el template NUNCA debe imprimir get_password() aquí.
    # El password se revela client-side vía fetch a password_reveal_json.


class PasswordCreateView(OwnerCreateMixin, CreateView):
    model = VaultPassword
    form_class = VaultPasswordForm
    template_name = "vault/password_form.html"
    success_url = reverse_lazy("vault:password_list")


class PasswordUpdateView(UserFormKwargsMixin, OwnerQuerysetMixin, UpdateView):
    model = VaultPassword
    form_class = VaultPasswordForm
    template_name = "vault/password_form.html"
    success_url = reverse_lazy("vault:password_list")


class PasswordDeleteView(OwnerQuerysetMixin, DeleteView):
    model = VaultPassword
    template_name = "vault/password_confirm_delete.html"
    success_url = reverse_lazy("vault:password_list")


class PasswordRevealView(OwnerQuerysetMixin, DetailView):
    """
    Vista separada para mostrar el detalle de un password. El valor en texto
    plano ya no se imprime aquí directamente: el template lo pide bajo demanda
    a PasswordRevealJSONView (mismo patrón que la lista), así que esta vista
    ni siquiera llama a get_password().
    """
    model = VaultPassword
    template_name = "vault/password_reveal.html"
    context_object_name = "password_obj"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        next_url = self.request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()
        ):
            context["volver_url"] = next_url
        else:
            context["volver_url"] = reverse("vault:password_list")
        return context


class PasswordRevealJSONView(OwnerQuerysetMixin, DetailView):
    """Endpoint AJAX que usa la lista de passwords para mostrar/copiar el
    valor inline sin navegar a PasswordRevealView. Sigue siendo la única otra
    vía que llama a get_password(): el template de la lista nunca lo imprime."""
    model = VaultPassword

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return JsonResponse({"password": self.object.get_password()})


# ---------- URLs ----------

class UrlListView(AjaxPartialTemplateMixin, SearchableListMixin, OwnerQuerysetMixin, ListView):
    model = Url
    template_name = "vault/url_list.html"
    ajax_template_name = "vault/_url_results.html"
    context_object_name = "urls"
    paginate_by = 15
    search_fields = ("name", "url", "notes")


class UrlCreateView(OwnerCreateMixin, CreateView):
    model = Url
    form_class = UrlForm
    template_name = "vault/url_form.html"
    success_url = reverse_lazy("vault:url_list")


class UrlUpdateView(UserFormKwargsMixin, OwnerQuerysetMixin, UpdateView):
    model = Url
    form_class = UrlForm
    template_name = "vault/url_form.html"
    success_url = reverse_lazy("vault:url_list")


class UrlDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Url
    template_name = "vault/url_confirm_delete.html"
    success_url = reverse_lazy("vault:url_list")


# ---------- Media Files ----------

class MediaFileListView(AjaxPartialTemplateMixin, SearchableListMixin, OwnerQuerysetMixin, ListView):
    model = MediaFile
    template_name = "vault/mediafile_list.html"
    ajax_template_name = "vault/_mediafile_results.html"
    context_object_name = "files"
    paginate_by = 15
    search_fields = ("original_name",)


class MediaFilePhotoGalleryView(SearchableListMixin, OwnerQuerysetMixin, ListView):
    """Vista de galería: solo fotos, en cuadrícula, filtrable por categoría."""
    model = MediaFile
    template_name = "vault/mediafile_gallery.html"
    context_object_name = "files"
    paginate_by = 15
    search_fields = ("original_name",)

    def get_queryset(self):
        return super().get_queryset().filter(file_type=MediaFile.FileType.PHOTO)


class MediaFileCreateView(OwnerCreateMixin, CreateView):
    model = MediaFile
    form_class = MediaFileForm
    template_name = "vault/mediafile_form.html"
    success_url = reverse_lazy("vault:mediafile_list")

    def form_valid(self, form):
        # Chequeo de cuota ANTES de guardar, para no permitir subir de más.
        uploaded_file = form.cleaned_data.get("file")
        user = self.request.user
        quota_bytes = int(user.storage_quota_gb * 1024 ** 3)
        if uploaded_file and (user.storage_used_bytes + uploaded_file.size) > quota_bytes:
            form.add_error("file", "Not enough storage space available in your quota.")
            return self.form_invalid(form)

        response = super().form_valid(form)
        user.storage_used_bytes += self.object.file_size_bytes
        user.save(update_fields=["storage_used_bytes"])
        return response


class MediaFileUpdateView(UserFormKwargsMixin, OwnerQuerysetMixin, UpdateView):
    model = MediaFile
    form_class = MediaFileForm
    template_name = "vault/mediafile_form.html"
    success_url = reverse_lazy("vault:mediafile_list")

    def form_valid(self, form):
        # OJO: para cuando llega aquí, Django ya sobrescribió self.object.file
        # (== form.instance.file) con el archivo nuevo durante form.is_valid().
        # Por eso el estado "viejo" se consulta aparte, directo de la BD.
        user = self.request.user
        old_size, old_file_name = MediaFile.objects.values_list(
            "file_size_bytes", "file"
        ).get(pk=self.object.pk)
        file_replaced = "file" in form.changed_data

        if file_replaced:
            new_file = form.cleaned_data.get("file")
            quota_bytes = int(user.storage_quota_gb * 1024 ** 3)
            if (user.storage_used_bytes - old_size + new_file.size) > quota_bytes:
                form.add_error("file", "Not enough storage space available in your quota.")
                return self.form_invalid(form)

        response = super().form_valid(form)

        if file_replaced:
            self.object.file_size_bytes = self.object.file.size
            self.object.save(update_fields=["file_size_bytes"])
            user.storage_used_bytes = max(user.storage_used_bytes - old_size + self.object.file_size_bytes, 0)
            user.save(update_fields=["storage_used_bytes"])
            if old_file_name and old_file_name != self.object.file.name:
                self.object.file.storage.delete(old_file_name)

        return response


class MediaFileDeleteView(OwnerQuerysetMixin, DeleteView):
    model = MediaFile
    template_name = "vault/mediafile_confirm_delete.html"
    success_url = reverse_lazy("vault:mediafile_list")
    # El modelo ya resta storage_used_bytes en su propio método delete().


# ---------- Reminders ----------

class ReminderListView(AjaxPartialTemplateMixin, SearchableListMixin, OwnerQuerysetMixin, ListView):
    model = Reminder
    template_name = "vault/reminder_list.html"
    ajax_template_name = "vault/_reminder_results.html"
    context_object_name = "reminders"
    paginate_by = 15
    search_fields = ("title", "description")


class ReminderCreateView(OwnerCreateMixin, CreateView):
    model = Reminder
    form_class = ReminderForm
    template_name = "vault/reminder_form.html"
    success_url = reverse_lazy("vault:reminder_list")


class ReminderUpdateView(UserFormKwargsMixin, OwnerQuerysetMixin, UpdateView):
    model = Reminder
    form_class = ReminderForm
    template_name = "vault/reminder_form.html"
    success_url = reverse_lazy("vault:reminder_list")


class ReminderDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Reminder
    template_name = "vault/reminder_confirm_delete.html"
    success_url = reverse_lazy("vault:reminder_list")


@method_decorator(csrf_exempt, name="dispatch")
class SendDueRemindersCronView(View):
    """
    Endpoint sin sesión pensado para un cron externo (ej. GitHub Actions) que
    dispara `manage.py send_due_reminders` vía HTTP. Protegido por un token
    compartido en el header X-Cron-Token, no por login: quien lo llama no es
    un usuario de la app.
    """

    def post(self, request):
        token = request.headers.get("X-Cron-Token", "")
        if not settings.CRON_SECRET or not hmac.compare_digest(token, settings.CRON_SECRET):
            return HttpResponseForbidden()
        call_command("send_due_reminders")
        return JsonResponse({"status": "ok"})


# ---------- QR Codes ----------

class QRCodeGeneratorView(LoginRequiredMixin, FormView):
    """
    Herramienta sin persistencia: genera el QR al vuelo y lo muestra
    como imagen embebida (data URI), sin crear ningún registro en la BD.
    """
    template_name = "vault/qrcode_form.html"
    form_class = QRCodeForm

    def form_valid(self, form):
        url = form.cleaned_data["url"]
        image = qrcode.make(url)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        qr_image_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")
        context = self.get_context_data(form=form, qr_image_base64=qr_image_base64, submitted_url=url)
        return self.render_to_response(context)


# ---------- I am here ----------

HISTORY_MIN_ROLE_LEVEL = 70


class ImHereView(LoginRequiredMixin, FormView):
    """
    Página con el formulario para registrar el email de notificación, el
    botón que dispara la captura de ubicación en el navegador, y la tabla
    con los últimos check-ins (ver im_here.html). El registro del check-in
    y el envío del email ocurren en ImHereSendLocationView, vía fetch, no
    en este form.
    """
    template_name = "vault/im_here.html"
    form_class = LocationAlertEmailForm
    success_url = reverse_lazy("vault:im_here")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Notification email saved.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Solo check-ins de la fecha actual; los de días anteriores viven en
        # la página de Historia (LocationCheckInHistoryView).
        checkins = list(
            LocationCheckIn.objects.filter(
                owner=self.request.user, check_date=timezone.localdate()
            )
        )
        # Si el usuario tiene rutas guardadas (por route_type, vía
        # SaveRouteView), siempre le ofrecemos elegir cuál cargar
        # (LoadRouteView) — incluso si ya hay check-ins hoy, para poder
        # sumar una ruta distinta (p. ej. cargar PM más tarde en el mismo
        # día después de haber hecho AM en la mañana), sin autocargar nada.
        context["route_choices"] = list(
            RouteStop.objects.filter(owner=self.request.user)
            .order_by("route_type").values_list("route_type", flat=True).distinct()
        )
        sort = self.request.GET.get("sort", "-date")
        reverse = sort.startswith("-")
        sort_key = sort.lstrip("-")
        if sort_key == "remarks":
            checkins.sort(key=lambda c: c.remarks.lower(), reverse=reverse)
        elif sort_key == "seq":
            checkins.sort(key=lambda c: c.seq, reverse=reverse)
        else:
            sort_key = "date"
            checkins.sort(key=lambda c: c.created_at or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=reverse)

        paginator = Paginator(checkins, 10)
        context["page_obj"] = paginator.get_page(self.request.GET.get("page"))
        context["sort"] = sort
        context["sort_key"] = sort_key
        context["sort_reverse"] = reverse
        context["date_sort_next"] = "date" if sort == "-date" else "-date"
        context["remarks_sort_next"] = "-remarks" if sort == "remarks" else "remarks"
        context["seq_sort_next"] = "-seq" if sort == "seq" else "seq"
        context["show_history_link"] = self.request.user.role_level > HISTORY_MIN_ROLE_LEVEL
        context["active_route_type"] = checkins[0].route_type if checkins else ""
        return context


class ImHereSendLocationView(LoginRequiredMixin, View):
    """
    Recibe (vía fetch, como JSON) las coordenadas y la hora local que el
    navegador capturó con navigator.geolocation. Siempre crea un
    LocationCheckIn nuevo; si el usuario registró location_alert_email,
    además envía el aviso por correo (best-effort: la falta de email no
    bloquea el registro del check-in).
    """

    def post(self, request):
        try:
            payload = json.loads(request.body)
            latitude = Decimal(str(payload["latitude"]))
            longitude = Decimal(str(payload["longitude"]))
            local_time = str(payload.get("local_time", ""))[:100]
        except (KeyError, TypeError, ValueError, InvalidOperation, json.JSONDecodeError):
            return JsonResponse({"error": "Invalid location data."}, status=400)

        today = timezone.localdate()
        last_seq = LocationCheckIn.objects.filter(
            owner=request.user, check_date=today
        ).aggregate(Max("seq"))["seq__max"]
        next_seq = (last_seq or 0) + 10
        LocationCheckIn.objects.create(
            owner=request.user, latitude=latitude, longitude=longitude,
            check_date=today, created_at=timezone.now(), seq=next_seq,
        )

        recipient = request.user.location_alert_email
        if recipient:
            send_mail(
                subject=f"{request.user.username} shared their location via KeyByMe",
                message=(
                    f"{request.user.username} tapped \"I am here\" in KeyByMe.\n\n"
                    f"Coordinates: {latitude}, {longitude}\n"
                    f"Local time at that location: {local_time}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
        return JsonResponse({"status": "ok"})


class LocationCheckInHereView(LoginRequiredMixin, View):
    """
    Ícono 'Here' de cada fila en la tabla de hoy: captura la ubicación
    actual y actualiza ESE registro (pensado para las paradas precargadas
    por SaveRouteView), sin crear un check-in nuevo y sin enviar el email
    de aviso.
    """

    def post(self, request, pk):
        checkin = get_object_or_404(LocationCheckIn, pk=pk, owner=request.user)
        try:
            payload = json.loads(request.body)
            latitude = Decimal(str(payload["latitude"]))
            longitude = Decimal(str(payload["longitude"]))
        except (KeyError, TypeError, ValueError, InvalidOperation, json.JSONDecodeError):
            return JsonResponse({"error": "Invalid location data."}, status=400)

        checkin.latitude = latitude
        checkin.longitude = longitude
        checkin.created_at = timezone.now()
        checkin.save(update_fields=["latitude", "longitude", "created_at"])
        return JsonResponse({"status": "ok"})


class SaveRouteView(LoginRequiredMixin, View):
    """
    Botón 'Save Route': guarda los check-ins del día actual (seq + remarks)
    como la plantilla de ruta diaria del usuario para el route_type indicado
    (AM, PM, MID DAY, ...) en RouteStop, reemplazando solo las paradas de
    ESE route_type — las de otros tipos guardados quedan intactas, para que
    un mismo usuario pueda mantener varias rutas nombradas en paralelo.
    LoadRouteView usa esa plantilla para precargar las paradas de un
    route_type elegido en un día futuro.
    """

    def post(self, request):
        route_type = request.POST.get("route_type", "").strip()
        if not route_type:
            messages.error(request, "Enter a route type (AM, PM, MID DAY, ...) to save this route as.")
            return redirect("vault:im_here")

        todays_checkins = LocationCheckIn.objects.filter(
            owner=request.user, check_date=timezone.localdate()
        ).order_by("seq")

        if not todays_checkins.exists():
            messages.error(request, "No check-ins today to save as a route.")
            return redirect("vault:im_here")

        RouteStop.objects.filter(owner=request.user, route_type=route_type).delete()
        RouteStop.objects.bulk_create([
            RouteStop(owner=request.user, route_type=route_type, seq=checkin.seq, remarks=checkin.remarks)
            for checkin in todays_checkins
        ])
        messages.success(request, f'Route "{route_type}" saved. You can load it on a future day.')
        return redirect("vault:im_here")


class LoadRouteView(LoginRequiredMixin, View):
    """
    Chooser en ImHereView: el usuario elige qué route_type cargar y esta
    vista precarga esas paradas como check-ins de hoy, sin fecha real/hora/
    ubicación propias — el usuario las va completando con el ícono 'Here' de
    cada fila conforme llega a cada lugar. Si ya hay check-ins hoy (p. ej. la
    ruta AM de la mañana), la ruta elegida se AGREGA a continuación (seq
    corrido para no pisar los existentes) en vez de reemplazarlos, para poder
    sumar una ruta distinta más tarde el mismo día.
    """

    def post(self, request):
        route_type = request.POST.get("route_type", "").strip()
        today = timezone.localdate()

        stops = RouteStop.objects.filter(owner=request.user, route_type=route_type).order_by("seq")
        if not stops:
            messages.error(request, f'No stops saved for route "{route_type}".')
            return redirect("vault:im_here")

        last_seq = LocationCheckIn.objects.filter(
            owner=request.user, check_date=today
        ).aggregate(Max("seq"))["seq__max"] or 0

        LocationCheckIn.objects.bulk_create([
            LocationCheckIn(owner=request.user, check_date=today, seq=last_seq + (index + 1) * 10,
                             remarks=stop.remarks, route_type=stop.route_type)
            for index, stop in enumerate(stops)
        ])
        messages.success(request, f'Route "{route_type}" loaded for today.')
        return redirect("vault:im_here")


class LocationCheckInUpdateView(OwnerQuerysetMixin, UpdateView):
    model = LocationCheckIn
    form_class = LocationCheckInForm
    template_name = "vault/location_checkin_form.html"
    success_url = reverse_lazy("vault:im_here")


class LocationCheckInDeleteView(OwnerQuerysetMixin, DeleteView):
    model = LocationCheckIn
    template_name = "vault/location_checkin_confirm_delete.html"
    success_url = reverse_lazy("vault:im_here")


class LocationCheckInHistoryView(LoginRequiredMixin, TemplateView):
    """Check-ins de días anteriores a hoy, ya fuera de la tabla de
    ImHereView, conservados aquí para análisis posterior. Solo visible
    (link) y accesible (esta vista) para roles con level > HISTORY_MIN_ROLE_LEVEL."""
    template_name = "vault/im_here_history.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role_level <= HISTORY_MIN_ROLE_LEVEL:
            return HttpResponseForbidden("You don't have access to this page.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Rutas guardadas (RouteStop) por route_type, tal como quedaron tras
        # el último "Save Route" de cada tipo — vive aquí, no solo como
        # plantilla invisible de precarga, para que el usuario pueda auditar
        # qué quedó guardado bajo cada tipo (AM, PM, MID DAY, ...).
        saved_stops = RouteStop.objects.filter(owner=self.request.user).order_by("route_type", "seq")
        context["saved_routes"] = [
            (route_type, list(stops))
            for route_type, stops in groupby(saved_stops, key=lambda s: s.route_type)
        ]

        checkins = list(
            LocationCheckIn.objects.filter(
                owner=self.request.user, check_date__lt=timezone.localdate()
            )
        )
        sort = self.request.GET.get("sort", "-date")
        reverse = sort.startswith("-")
        sort_key = sort.lstrip("-")
        if sort_key == "remarks":
            checkins.sort(key=lambda c: c.remarks.lower(), reverse=reverse)
        elif sort_key == "seq":
            checkins.sort(key=lambda c: c.seq, reverse=reverse)
        else:
            sort_key = "date"
            checkins.sort(key=lambda c: c.created_at or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=reverse)

        paginator = Paginator(checkins, 15)
        context["page_obj"] = paginator.get_page(self.request.GET.get("page"))
        context["sort"] = sort
        context["sort_key"] = sort_key
        context["sort_reverse"] = reverse
        context["date_sort_next"] = "date" if sort == "-date" else "-date"
        context["remarks_sort_next"] = "-remarks" if sort == "remarks" else "remarks"
        context["seq_sort_next"] = "-seq" if sort == "seq" else "seq"
        return context
