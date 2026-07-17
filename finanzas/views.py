from decimal import Decimal

from django.contrib import messages
from django.db.models import Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from vault.mixins import OwnerCreateMixin, OwnerQuerysetMixin, SearchableListMixin, UserFormKwargsMixin
from vault.models import MediaFile

from .forms import CuentaForm, DeudaForm, TransaccionForm
from .models import Cuenta, Deuda, Transaccion

# Mismas extensiones de foto que vault/models.py (ALLOWED_MEDIA_EXTENSIONS),
# para clasificar el recibo subido aquí como MediaFile.FileType.PHOTO o DOCUMENT.
PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "heic"}


def _attach_recibo(form, request, old_recibo=None):
    """Crea un MediaFile a partir de `recibo_file`, replicando el chequeo/ajuste
    de cuota de MediaFileCreateView (vault/views.py), y lo liga a la transacción.
    Si había un recibo anterior (edición), lo borra después de guardar el nuevo
    (MediaFile.delete() ya descuenta la cuota)."""
    uploaded_file = form.cleaned_data.get("recibo_file")
    if not uploaded_file:
        return True

    user = request.user
    if not user.has_space_for(uploaded_file.size):
        form.add_error("recibo_file", "No tienes espacio suficiente en tu cuota de almacenamiento.")
        return False

    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()
    file_type = MediaFile.FileType.PHOTO if extension in PHOTO_EXTENSIONS else MediaFile.FileType.DOCUMENT

    media_file = MediaFile.objects.create(
        owner=user,
        file=uploaded_file,
        file_type=file_type,
        original_name=uploaded_file.name,
        category=form.cleaned_data.get("category"),
    )
    user.storage_used_bytes += media_file.file_size_bytes
    user.save(update_fields=["storage_used_bytes"])
    form.instance.recibo = media_file
    form.instance._old_recibo_to_delete = old_recibo
    return True


# ---------- Cuentas ----------

class CuentaListView(OwnerQuerysetMixin, ListView):
    model = Cuenta
    template_name = "finanzas/cuenta_list.html"
    context_object_name = "cuentas"
    paginate_by = 20
    SORTABLE_FIELDS = ("name", "numero")

    def get_queryset(self):
        queryset = super().get_queryset()
        sort = self.request.GET.get("sort", "")
        if sort.lstrip("-") in self.SORTABLE_FIELDS:
            queryset = queryset.order_by(sort)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_sort"] = self.request.GET.get("sort", "")
        return context


class CuentaCreateView(OwnerCreateMixin, CreateView):
    model = Cuenta
    form_class = CuentaForm
    template_name = "finanzas/cuenta_form.html"
    success_url = reverse_lazy("finanzas:cuenta_list")


class CuentaUpdateView(UserFormKwargsMixin, OwnerQuerysetMixin, UpdateView):
    model = Cuenta
    form_class = CuentaForm
    template_name = "finanzas/cuenta_form.html"
    success_url = reverse_lazy("finanzas:cuenta_list")


class CuentaDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Cuenta
    template_name = "finanzas/cuenta_confirm_delete.html"
    success_url = reverse_lazy("finanzas:cuenta_list")

    def form_valid(self, form):
        # cuenta.on_delete=PROTECT: no se puede borrar si tiene transacciones.
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "No se puede borrar esta cuenta: tiene transacciones asociadas. "
                "Reasigna o borra esas transacciones primero.",
            )
            return redirect(self.success_url)


# ---------- Transacciones ----------

class TransaccionListView(SearchableListMixin, OwnerQuerysetMixin, ListView):
    model = Transaccion
    template_name = "finanzas/transaccion_list.html"
    context_object_name = "transacciones"
    paginate_by = 20
    search_fields = ("concepto",)

    MESES = [
        (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
        (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
        (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
    ]

    def _get_periodo(self):
        # Si no viene 'periodo' en absoluto (primera carga de la página), se
        # asume el mes en curso. Si viene vacío ("Todo el tiempo" elegido a
        # propósito en el dropdown), se respeta y no se filtra por fecha.
        periodo = self.request.GET.get("periodo")
        if periodo is None:
            periodo = str(timezone.localdate().month)
        return periodo

    def _get_periodo_label(self):
        periodo = self._get_periodo()
        if periodo == "ytd":
            return "Lo que va del año"
        if periodo and periodo.isdigit() and 1 <= int(periodo) <= 12:
            return dict(self.MESES)[int(periodo)]
        return ""

    def get_queryset(self):
        queryset = super().get_queryset()

        tipo = self.request.GET.get("tipo")
        if tipo:
            queryset = queryset.filter(tipo=tipo)

        cuenta_id = self.request.GET.get("cuenta")
        if cuenta_id:
            queryset = queryset.filter(cuenta_id=cuenta_id)

        hoy = timezone.localdate()
        periodo = self._get_periodo()
        if periodo == "ytd":
            queryset = queryset.filter(fecha__year=hoy.year, fecha__lte=hoy)
        elif periodo and periodo.isdigit() and 1 <= int(periodo) <= 12:
            queryset = queryset.filter(fecha__year=hoy.year, fecha__month=int(periodo))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Totales sobre el queryset filtrado completo (no solo la página actual).
        totals = self.get_queryset().values("tipo").annotate(total=Sum("monto"))
        total_by_tipo = {row["tipo"]: row["total"] or Decimal("0") for row in totals}
        total_ingresos = total_by_tipo.get(Transaccion.Tipo.INGRESO, Decimal("0"))
        total_egresos = total_by_tipo.get(Transaccion.Tipo.EGRESO, Decimal("0"))
        context["total_ingresos"] = total_ingresos
        context["total_egresos"] = total_egresos
        context["balance"] = total_ingresos - total_egresos

        context["cuentas"] = Cuenta.objects.filter(owner=self.request.user)
        context["selected_tipo"] = self.request.GET.get("tipo", "")
        context["selected_cuenta"] = self.request.GET.get("cuenta", "")
        context["meses"] = self.MESES
        context["selected_periodo"] = self._get_periodo()
        context["periodo_label"] = self._get_periodo_label()
        return context


class TransaccionCreateView(OwnerCreateMixin, CreateView):
    model = Transaccion
    form_class = TransaccionForm
    template_name = "finanzas/transaccion_form.html"
    success_url = reverse_lazy("finanzas:transaccion_list")

    def form_valid(self, form):
        if not _attach_recibo(form, self.request):
            return self.form_invalid(form)
        return super().form_valid(form)


class TransaccionUpdateView(UserFormKwargsMixin, OwnerQuerysetMixin, UpdateView):
    model = Transaccion
    form_class = TransaccionForm
    template_name = "finanzas/transaccion_form.html"
    success_url = reverse_lazy("finanzas:transaccion_list")

    def form_valid(self, form):
        old_recibo = self.object.recibo
        if not _attach_recibo(form, self.request, old_recibo=old_recibo):
            return self.form_invalid(form)
        response = super().form_valid(form)
        # Si se subió un recibo nuevo, el anterior ya quedó reemplazado en el
        # FK; se borra aparte (MediaFile.delete() descuenta su propia cuota).
        pending_old_recibo = getattr(form.instance, "_old_recibo_to_delete", None)
        if pending_old_recibo:
            pending_old_recibo.delete()
        return response


class TransaccionDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Transaccion
    template_name = "finanzas/transaccion_confirm_delete.html"
    success_url = reverse_lazy("finanzas:transaccion_list")
    # OJO: el recibo (MediaFile) NO se borra aquí a propósito — sigue viviendo
    # en Archivos aunque se borre la transacción, por si el usuario lo quiere
    # conservar.


# ---------- Deudas ----------

class DeudaListView(OwnerQuerysetMixin, ListView):
    model = Deuda
    template_name = "finanzas/deuda_list.html"
    context_object_name = "deudas"
    paginate_by = 20


class DeudaCreateView(OwnerCreateMixin, CreateView):
    model = Deuda
    form_class = DeudaForm
    template_name = "finanzas/deuda_form.html"
    success_url = reverse_lazy("finanzas:deuda_list")


class DeudaUpdateView(UserFormKwargsMixin, OwnerQuerysetMixin, UpdateView):
    model = Deuda
    form_class = DeudaForm
    template_name = "finanzas/deuda_form.html"
    success_url = reverse_lazy("finanzas:deuda_list")


class DeudaDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Deuda
    template_name = "finanzas/deuda_confirm_delete.html"
    success_url = reverse_lazy("finanzas:deuda_list")
