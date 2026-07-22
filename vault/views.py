import base64
import datetime as dt
import hmac
import io
import json
from decimal import Decimal, InvalidOperation
from itertools import groupby
from urllib.parse import urlencode

import qrcode
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.mail import send_mail
from django.core.management import call_command
from django.core.paginator import Paginator
from django.db.models import Max, Q
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
    LocationCheckInForm,
    MediaFileForm,
    QRCodeForm,
    ReminderForm,
    RouteStopForm,
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

ADMIN_MIN_ROLE_LEVEL = 70


IM_HERE_ACTIVE_ROUTE_SESSION_KEY = "im_here_active_route_type"


class ImHereView(LoginRequiredMixin, TemplateView):
    """
    Página con el botón que dispara la captura de ubicación en el navegador
    y la tabla con los últimos check-ins (ver im_here.html). El registro del
    check-in y el envío del email de aviso (a location_alert_email, editable
    solo desde /admin) ocurren en ImHereSendLocationView, vía fetch.
    """
    template_name = "vault/im_here.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Solo check-ins de la fecha actual y no cerrados; los de días
        # anteriores, y los de hoy ya cerrados con "Close day" (Dispatch),
        # viven en la página de Historia (LocationCheckInHistoryView).
        checkins = list(
            LocationCheckIn.objects.filter(
                owner=self.request.user, check_date=timezone.localdate(), is_closed=False
            )
        )
        # Si el usuario tiene rutas guardadas (RouteStop, por route_type,
        # administradas desde Dispatch/Rutas), siempre le ofrecemos elegir
        # cuál hacer (LoadRouteView) — incluso si ya hay check-ins hoy, para
        # poder cargar una ruta distinta (p. ej. PM más tarde en el mismo
        # día después de haber hecho AM en la mañana), sin autocargar nada.
        context["route_choices"] = list(
            RouteStop.objects.filter(owner=self.request.user)
            .order_by("route_type").values_list("route_type", flat=True).distinct()
        )
        # Solo se muestra la ruta que el chofer tocó por última vez (guardada
        # en la sesión por LoadRouteView/ImHereSendLocationView) — tocar PM
        # no debe dejar AM visible al mismo tiempo, ni viceversa. Si todavía
        # no tocó nada esta sesión, no se muestra ninguna tabla.
        active_route_type = self.request.session.get(IM_HERE_ACTIVE_ROUTE_SESSION_KEY)
        if active_route_type is not None:
            checkins = [c for c in checkins if c.route_type == active_route_type]
        else:
            checkins = []

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

        groups = {}
        for checkin in checkins:
            groups.setdefault(checkin.route_type, []).append(checkin)
        context["route_groups"] = [
            {"route_type": route_type, "checkins": groups[route_type]}
            for route_type in sorted(groups, key=lambda rt: (rt == "", rt))
        ]
        context["sort"] = sort
        context["sort_key"] = sort_key
        context["sort_reverse"] = reverse
        context["date_sort_next"] = "date" if sort == "-date" else "-date"
        context["remarks_sort_next"] = "-remarks" if sort == "remarks" else "remarks"
        context["seq_sort_next"] = "-seq" if sort == "seq" else "seq"
        context["show_dispatch_link"] = self.request.user.role_level > ADMIN_MIN_ROLE_LEVEL
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
        todays_checkins = LocationCheckIn.objects.filter(
            owner=request.user, check_date=today, is_closed=False
        )
        # Se suma a la ruta que ImHereView está mostrando ahora (guardada en
        # sesión), o si todavía no hay ninguna activa esta sesión, a la que
        # ya tenga check-ins hoy (o "" si "Add stop" es lo único que se usó)
        # — y esa pasa a ser la activa, para que ImHereView la muestre.
        active_route_type = request.session.get(IM_HERE_ACTIVE_ROUTE_SESSION_KEY)
        if active_route_type is None:
            active_route_type = (
                todays_checkins.exclude(route_type="").order_by("seq").values_list("route_type", flat=True).first() or ""
            )
        last_seq = todays_checkins.filter(route_type=active_route_type).aggregate(Max("seq"))["seq__max"]
        next_seq = (last_seq or 0) + 10
        LocationCheckIn.objects.create(
            owner=request.user, latitude=latitude, longitude=longitude,
            check_date=today, created_at=timezone.now(), seq=next_seq, route_type=active_route_type,
        )
        request.session[IM_HERE_ACTIVE_ROUTE_SESSION_KEY] = active_route_type

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
    por LoadRouteView), sin crear un check-in nuevo y sin enviar el email
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


class LoadRouteView(LoginRequiredMixin, View):
    """
    Botón de ruta en ImHereView: el usuario elige qué route_type hacer hoy.
    La plantilla (RouteStop, administrada solo desde Dispatch/Rutas) nunca
    se modifica desde acá — esta vista solo LEE de ella.

    - Si para ESTE route_type todavía no se marcó ningún stop como 'Here'
      hoy (sin importar cuántas veces se haya tocado el botón antes: cero
      veces, o varias sin avanzar), se descarta lo que hubiera y se vuelve
      a copiar la plantilla tal como está AHORA en Rutas — así el usuario
      siempre ve la versión más reciente hasta que empieza a avanzar.
    - En cuanto al menos un stop de hoy para ese route_type ya tiene
      'Here' marcado (created_at), esa es la "otra copia" con el avance del
      día: ya no se toca ni se reemplaza por la plantilla — un load
      posterior el mismo día solo vuelve a mostrar la tabla con ese
      avance, sin perderlo y sin alterar el original de Rutas.
    """

    def post(self, request):
        route_type = request.POST.get("route_type", "").strip()
        today = timezone.localdate()

        existing = LocationCheckIn.objects.filter(
            owner=request.user, check_date=today, route_type=route_type, is_closed=False
        )
        if existing.filter(created_at__isnull=False).exists():
            request.session[IM_HERE_ACTIVE_ROUTE_SESSION_KEY] = route_type
            messages.success(request, f'Route "{route_type}" already has progress today — showing today\'s latest update.')
            return redirect("vault:im_here")

        stops = RouteStop.objects.filter(owner=request.user, route_type=route_type).order_by("seq")
        if not stops:
            messages.error(request, f'No stops saved for route "{route_type}".')
            return redirect("vault:im_here")

        existing.delete()

        # Cada route_type tiene su propia tabla en ImHereView (nunca se
        # mezclan), así que no hace falta correr el seq para no chocar con
        # otra ruta ya cargada — se copia el seq de la plantilla tal cual.
        LocationCheckIn.objects.bulk_create([
            LocationCheckIn(owner=request.user, check_date=today, seq=stop.seq,
                             stop_number=stop.stop_number, remarks=stop.remarks, route_type=stop.route_type)
            for stop in stops
        ])
        # Este es ahora el único route_type que ImHereView muestra — tocar
        # otra ruta después la reemplaza en pantalla (ver ImHereView).
        request.session[IM_HERE_ACTIVE_ROUTE_SESSION_KEY] = route_type
        messages.success(request, f'Route "{route_type}" loaded for today.')
        return redirect("vault:im_here")


class LocationCheckInSuccessUrlMixin:
    """Send the user back to History if the check-in being edited/deleted
    lives there (past day or closed today), otherwise back to today's I am
    here table — matches the filter LocationCheckInHistoryView uses. When
    going back to History, carries the route/type along so the admin lands
    back on the same search instead of the empty prompt."""

    def get_success_url(self):
        checkin = self.object
        if checkin.check_date < timezone.localdate() or checkin.is_closed:
            if checkin.route_type:
                query = urlencode({"route": checkin.owner.route, "route_type": checkin.route_type})
                return f"{reverse('vault:im_here_history')}?{query}"
            return reverse("vault:im_here_history")
        return reverse("vault:im_here")


class LocationCheckInAccessMixin(LoginRequiredMixin):
    """Regular drivers can only edit/delete their own check-ins. Admins
    (role_level > ADMIN_MIN_ROLE_LEVEL) can reach any driver's, since
    History — which links here — is cross-driver like Rutas."""

    def get_queryset(self):
        queryset = LocationCheckIn.objects.all()
        if self.request.user.role_level > ADMIN_MIN_ROLE_LEVEL:
            return queryset
        return queryset.filter(owner=self.request.user)


class LocationCheckInUpdateView(LocationCheckInSuccessUrlMixin, LocationCheckInAccessMixin, UpdateView):
    model = LocationCheckIn
    form_class = LocationCheckInForm
    template_name = "vault/location_checkin_form.html"


class LocationCheckInDeleteView(LocationCheckInSuccessUrlMixin, LocationCheckInAccessMixin, DeleteView):
    model = LocationCheckIn
    template_name = "vault/location_checkin_confirm_delete.html"


class AdminRoleRequiredMixin(LoginRequiredMixin):
    """Para las vistas administrativas (Dispatch, Rutas, History): solo
    visibles (link) y accesibles (dispatch) para roles con level > ADMIN_MIN_ROLE_LEVEL."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role_level <= ADMIN_MIN_ROLE_LEVEL:
            return HttpResponseForbidden("You don't have access to this page.")
        return super().dispatch(request, *args, **kwargs)


def _find_driver_by_route(route_number):
    """Busca la cuenta de chofer dueña de un número de ruta (CustomUser.route).
    Rutas es administrado por roles >70 para CUALQUIER chofer, no solo el
    propio del admin logueado — por eso todo lo que crea/edita una ruta
    necesita resolver primero a qué cuenta pertenece ese número."""
    return get_user_model().objects.filter(route=route_number).first()


class AdminRoutesView(AdminRoleRequiredMixin, TemplateView):
    """Rutas guardadas (RouteStop) de TODOS los choferes, agrupadas por
    número de ruta (owner.route) + route_type, tal como quedaron tras el
    último 'Save Route' de cada tipo (o creadas a mano aquí) — vive aquí,
    no solo como plantilla invisible de precarga, para que un admin pueda
    auditar y administrar la ruta de cualquier chofer."""
    template_name = "vault/admin_routes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        saved_stops = RouteStop.objects.select_related("owner").order_by("owner__route", "route_type", "seq")
        saved_routes = []
        for (route_number, route_type), stops in groupby(saved_stops, key=lambda s: (s.owner.route, s.route_type)):
            stops = list(stops)
            saved_routes.append((route_number, route_type, stops, stops[-1].seq + 10))
        context["saved_routes"] = saved_routes
        return context


class RouteStopCreateView(AdminRoleRequiredMixin, CreateView):
    """Agrega una parada a una ruta existente (identificada por número +
    tipo) o, vía el link suelto 'Add stop', a una ruta cualquiera que el
    admin indique a mano."""
    model = RouteStop
    form_class = RouteStopForm
    template_name = "vault/route_stop_form.html"
    success_url = reverse_lazy("vault:im_here_admin_routes")

    def get_initial(self):
        initial = super().get_initial()
        route_type = self.request.GET.get("route_type")
        if route_type:
            initial["route_type"] = route_type
        return initial

    def form_valid(self, form):
        route_number = self.request.POST.get("route_number", "").strip()
        owner = _find_driver_by_route(route_number)
        if owner is None:
            form.add_error(None, f'No driver account found with route number "{route_number}".')
            return self.form_invalid(form)
        form.instance.owner = owner
        return super().form_valid(form)


class RouteStopUpdateView(AdminRoleRequiredMixin, UpdateView):
    model = RouteStop
    form_class = RouteStopForm
    template_name = "vault/route_stop_form.html"
    success_url = reverse_lazy("vault:im_here_admin_routes")


class RouteStopDeleteView(AdminRoleRequiredMixin, DeleteView):
    model = RouteStop
    template_name = "vault/route_stop_confirm_delete.html"
    success_url = reverse_lazy("vault:im_here_admin_routes")


class RouteCreateView(AdminRoleRequiredMixin, View):
    """Crea una ruta nueva (número + route_type) con una primera parada en
    blanco, para que aparezca de inmediato en la grilla de Rutas lista para
    editar. El número debe ser el Route de una cuenta de chofer existente."""

    def post(self, request):
        route_number = request.POST.get("route_number", "").strip()
        route_type = request.POST.get("route_type", "").strip().upper()
        stop_number = request.POST.get("stop_number", "").strip() or None
        planned_time = request.POST.get("planned_time", "").strip() or None
        if not route_number or not route_type:
            messages.error(request, "Enter both a route number and a route type (AM, PM, MID DAY, ...) to create.")
            return redirect("vault:im_here_admin_routes")
        owner = _find_driver_by_route(route_number)
        if owner is None:
            messages.error(request, f'No driver account found with route number "{route_number}".')
            return redirect("vault:im_here_admin_routes")
        if RouteStop.objects.filter(owner=owner, route_type=route_type).exists():
            messages.error(request, f'Route "{route_number} {route_type}" already exists.')
            return redirect("vault:im_here_admin_routes")
        RouteStop.objects.create(
            owner=owner, route_type=route_type, seq=10,
            stop_number=stop_number, planned_time=planned_time, remarks="",
        )
        messages.success(request, f'Route "{route_number} {route_type}" created.')
        return redirect("vault:im_here_admin_routes")


class RouteDeleteView(AdminRoleRequiredMixin, TemplateView):
    """Borra TODAS las paradas (RouteStop) de un número + route_type de una
    vez, en vez de tener que borrarlas una por una desde RouteStopDeleteView."""
    template_name = "vault/route_confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["route_number"] = self.kwargs["route_number"]
        context["route_type"] = self.kwargs["route_type"]
        context["stop_count"] = RouteStop.objects.filter(
            owner__route=self.kwargs["route_number"], route_type=self.kwargs["route_type"]
        ).count()
        return context

    def post(self, request, route_number, route_type):
        deleted, _ = RouteStop.objects.filter(owner__route=route_number, route_type=route_type).delete()
        messages.success(request, f'Route "{route_number} {route_type}" deleted ({deleted} stop(s)).')
        return redirect("vault:im_here_admin_routes")


class LocationCheckInHistoryView(AdminRoleRequiredMixin, TemplateView):
    """Check-ins de días anteriores a hoy, más los de hoy ya cerrados con
    'Close day' (ver DispatchCloseDayView) — ya fuera de la tabla de
    ImHereView, conservados aquí para análisis posterior. Cross-driver como
    Rutas (AdminRoleRequiredMixin ya exige role_level > ADMIN_MIN_ROLE_LEVEL):
    en vez de listar todo mezclado, el admin busca un número de ruta + tipo
    (AM/PM/...) a la vez — con más choferes activos, la lista de rutas solo
    va a crecer, así que cada búsqueda queda separada."""
    template_name = "vault/im_here_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_route = self.request.GET.get("route", "").strip()
        search_route_type = self.request.GET.get("route_type", "").strip().upper()
        searched = bool(search_route and search_route_type)

        checkins = []
        if searched:
            checkins = list(
                LocationCheckIn.objects.filter(
                    owner__route=search_route, route_type__iexact=search_route_type
                ).filter(
                    Q(check_date__lt=timezone.localdate()) | Q(check_date=timezone.localdate(), is_closed=True)
                )
            )
        context["search_route"] = search_route
        context["search_route_type"] = search_route_type
        context["searched"] = searched

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


class DispatchView(AdminRoleRequiredMixin, TemplateView):
    """Panel de despacho: solo rutas que YA salieron del depot hoy (al menos
    una parada marcada 'Here'), con cuántas paradas completaron, si van
    atrasadas y una ETA de la última parada, ordenadas por delay descendente.

    RouteStop no tiene un link directo a los LocationCheckIn del día (Load
    Route recalcula el seq al copiar), así que el 'Time' de referencia
    (RouteStop.planned_time) se empareja con cada check-in POR POSICIÓN
    dentro de la ruta (mismo orden en que se cargó) — un best-effort mientras
    no exista un FK explícito. Si el admin reordena o agrega paradas después
    de cargar la ruta, ese emparejamiento puede desalinearse."""
    template_name = "vault/dispatch.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        now = timezone.localtime()

        checkins_by_route = {}
        todays_checkins = LocationCheckIn.objects.select_related("owner").filter(
            check_date=today, is_closed=False
        ).exclude(route_type="").order_by("seq")
        for checkin in todays_checkins:
            checkins_by_route.setdefault((checkin.owner_id, checkin.route_type), []).append(checkin)

        template_stops_by_route = {}
        for stop in RouteStop.objects.order_by("seq"):
            template_stops_by_route.setdefault((stop.owner_id, stop.route_type), []).append(stop)

        def planned_time_at(template_stops, index):
            if 0 <= index < len(template_stops):
                return template_stops[index].planned_time
            return None

        rows = []
        for (owner_id, route_type), stops in checkins_by_route.items():
            done = [c for c in stops if c.created_at]
            if not done:
                continue  # todavía no salió del depot

            total = len(stops)
            template_stops = template_stops_by_route.get((owner_id, route_type), [])
            pending = next((c for c in stops if not c.created_at), None)

            delay_minutes = None
            if pending is not None:
                planned = planned_time_at(template_stops, stops.index(pending))
                if planned:
                    planned_dt = timezone.make_aware(dt.datetime.combine(today, planned))
                    delay_minutes = int((now - planned_dt).total_seconds() // 60)

            eta = None
            last_planned = planned_time_at(template_stops, total - 1)
            if last_planned:
                eta_dt = timezone.make_aware(dt.datetime.combine(today, last_planned))
                if delay_minutes and delay_minutes > 0:
                    eta_dt += dt.timedelta(minutes=delay_minutes)
                eta = eta_dt

            if pending is None:
                status = "Completed"
            elif delay_minutes is None:
                status = "In progress"
            elif delay_minutes > 0:
                status = "Late"
            else:
                status = "On time"

            last_checkin = done[-1]
            rows.append({
                "owner": last_checkin.owner,
                "route_type": route_type,
                "status": status,
                "done": len(done),
                "total": total,
                "delay_minutes": delay_minutes,
                "eta": eta,
                "last_checkin": last_checkin,
            })

        rows.sort(key=lambda r: (r["delay_minutes"] is None, -(r["delay_minutes"] or 0)))
        context["rows"] = rows
        return context


class DispatchCloseDayView(AdminRoleRequiredMixin, View):
    """Botón 'Close day' por fila en Dispatch: le permite a un admin cerrar
    el día de un chofer/route_type puntual — el único lugar donde un día se
    cierra ahora (ya no existe un botón de Close day del lado del chofer en
    'I am here'). Solo manda a History lo abierto de hoy; mañana el primer
    load-route de esa ruta se refresca solo desde la plantilla (ver
    LoadRouteView), sin que este botón tenga que preparar nada."""

    def post(self, request):
        route_number = request.POST.get("route_number", "").strip()
        route_type = request.POST.get("route_type", "").strip()
        owner = _find_driver_by_route(route_number)
        if owner is None:
            messages.error(request, f'No driver account found with route number "{route_number}".')
            return redirect("vault:im_here_dispatch")

        updated = LocationCheckIn.objects.filter(
            owner=owner, check_date=timezone.localdate(), route_type=route_type, is_closed=False
        ).update(is_closed=True)
        if not updated:
            messages.error(request, f'No open stops today for route "{route_number} {route_type}".')
        else:
            messages.success(request, f'Day closed for route "{route_number} {route_type}" — {updated} stop(s) moved to History.')
        return redirect("vault:im_here_dispatch")


class DispatchCloseDriverDayView(AdminRoleRequiredMixin, View):
    """Botón 'Close day' por chofer en Dispatch (no por fila de ruta):
    cierra TODO lo abierto de HOY para ese chofer, incluidas paradas
    sueltas sin route_type (Add stop antes de cargar cualquier ruta) que
    DispatchCloseDayView no puede alcanzar porque exige un route_type
    puntual."""

    def post(self, request):
        route_number = request.POST.get("route_number", "").strip()
        owner = _find_driver_by_route(route_number)
        if owner is None:
            messages.error(request, f'No driver account found with route number "{route_number}".')
            return redirect("vault:im_here_dispatch")

        updated = LocationCheckIn.objects.filter(
            owner=owner, check_date=timezone.localdate(), is_closed=False
        ).update(is_closed=True)
        if not updated:
            messages.error(request, f'No open stops today for driver "{route_number}".')
        else:
            messages.success(request, f'Day closed for driver "{route_number}" — {updated} stop(s) moved to History.')
        return redirect("vault:im_here_dispatch")
