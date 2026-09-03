from urllib.parse import urlencode

from django.core.mail import EmailMessage
from django.db.models import Q, Value
from django.db.models.functions import Coalesce, Lower, NullIf
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from vault.mixins import AjaxPartialTemplateMixin, ModuleAccessRequiredMixin

from .forms import (
    AmMidPmEntryForm, DepotLinkFormSet, EmployeeForm, LeftRightForm, LeftRightRowForm, RouteForm, SchoolForm,
)
from .models import AmMidPmEntry, DepotLink, Employee, LeftRight, LeftRightRow, Route, School

# Not owner-scoped on purpose: School/Employee/Route/AmMidPmEntry/LeftRight
# are shared reference catalogs (MCPS public schools, MCPS transportation
# staff, MCPS bus route stops, MCPS AM/MID/PM stop times, MCPS left/right
# turn-by-turn guides), not per-user vault data — see schools/models.py.

# Documents/photos accepted by DepotUploadView -- no video, so a handful of
# attachments stays well under typical SMTP attachment-size limits.
DEPOT_UPLOAD_ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv",
    "jpg", "jpeg", "png", "gif", "webp", "heic",
}
DEPOT_UPLOAD_MAX_FILES = 10
DEPOT_UPLOAD_MAX_TOTAL_BYTES = 20 * 1024 * 1024  # 20 MB combined

SORTABLE_FIELDS = ("school_type", "address", "city", "zip_code")
EMPLOYEE_SORTABLE_FIELDS = ("phone", "position")
ROUTE_SORTABLE_FIELDS = ("bus_number",)
AMMIDPM_SORTABLE_FIELDS = ("type", "seq", "time", "address", "next")


class SchoolListView(AjaxPartialTemplateMixin, ModuleAccessRequiredMixin, ListView):
    model = School
    template_name = "schools/school_list.html"
    ajax_template_name = "schools/_school_results.html"
    context_object_name = "schools"
    paginate_by = 25
    module_codename = "artifacts_mcps"

    def get_queryset(self):
        queryset = super().get_queryset()

        school_type = self.request.GET.get("type")
        if school_type:
            queryset = queryset.filter(school_type=school_type)

        query = self.request.GET.get("q")
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(address__icontains=query) | Q(city__icontains=query)
            )

        sort = self.request.GET.get("sort", "")
        if sort.lstrip("-") in SORTABLE_FIELDS:
            queryset = queryset.order_by(sort, "name")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "")
        selected_type = self.request.GET.get("type", "")
        sort = self.request.GET.get("sort", "")

        context["school_types"] = School.SchoolType.choices
        context["selected_type"] = selected_type
        context["query"] = query
        context["sort_key"] = sort.lstrip("-")
        context["sort_reverse"] = sort.startswith("-")

        # Base filters (q/type), carried over into sort links and pagination
        # links so switching page/sort never silently drops the current
        # search. Sort links intentionally omit "page" — jumping to a
        # different sort always lands back on page 1.
        base_params = {}
        if query:
            base_params["q"] = query
        if selected_type:
            base_params["type"] = selected_type

        for field in SORTABLE_FIELDS:
            next_sort = f"-{field}" if sort == field else field
            context[f"{field}_sort_url"] = "?" + urlencode({**base_params, "sort": next_sort})

        if sort:
            base_params["sort"] = sort
        context["extra_qs"] = urlencode(base_params)

        return context


class SchoolCreateView(ModuleAccessRequiredMixin, CreateView):
    model = School
    form_class = SchoolForm
    template_name = "schools/school_form.html"
    success_url = reverse_lazy("schools:school_list")
    module_codename = "artifacts_mcps"


class SchoolUpdateView(ModuleAccessRequiredMixin, UpdateView):
    model = School
    form_class = SchoolForm
    template_name = "schools/school_form.html"
    success_url = reverse_lazy("schools:school_list")
    module_codename = "artifacts_mcps"


class SchoolDeleteView(ModuleAccessRequiredMixin, DeleteView):
    model = School
    template_name = "schools/school_confirm_delete.html"
    success_url = reverse_lazy("schools:school_list")
    module_codename = "artifacts_mcps"


class EmployeeListView(AjaxPartialTemplateMixin, ModuleAccessRequiredMixin, ListView):
    model = Employee
    template_name = "schools/employee_list.html"
    ajax_template_name = "schools/_employee_results.html"
    context_object_name = "employees"
    paginate_by = 25
    module_codename = "artifacts_mcps"

    def get_queryset(self):
        queryset = super().get_queryset()

        position = self.request.GET.get("position")
        if position:
            queryset = queryset.filter(position=position)

        query = self.request.GET.get("q")
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(phone__icontains=query))

        sort = self.request.GET.get("sort", "")
        if sort.lstrip("-") in EMPLOYEE_SORTABLE_FIELDS:
            queryset = queryset.order_by(sort, "name")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "")
        selected_position = self.request.GET.get("position", "")
        sort = self.request.GET.get("sort", "")

        context["positions"] = Employee.Position.choices
        context["selected_position"] = selected_position
        context["query"] = query
        context["sort_key"] = sort.lstrip("-")
        context["sort_reverse"] = sort.startswith("-")

        base_params = {}
        if query:
            base_params["q"] = query
        if selected_position:
            base_params["position"] = selected_position

        for field in EMPLOYEE_SORTABLE_FIELDS:
            next_sort = f"-{field}" if sort == field else field
            context[f"{field}_sort_url"] = "?" + urlencode({**base_params, "sort": next_sort})

        if sort:
            base_params["sort"] = sort
        context["extra_qs"] = urlencode(base_params)

        return context


class EmployeeCreateView(ModuleAccessRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "schools/employee_form.html"
    success_url = reverse_lazy("schools:employee_list")
    module_codename = "artifacts_mcps"


class EmployeeUpdateView(ModuleAccessRequiredMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "schools/employee_form.html"
    success_url = reverse_lazy("schools:employee_list")
    module_codename = "artifacts_mcps"


class EmployeeDeleteView(ModuleAccessRequiredMixin, DeleteView):
    model = Employee
    template_name = "schools/employee_confirm_delete.html"
    success_url = reverse_lazy("schools:employee_list")
    module_codename = "artifacts_mcps"


class RouteListView(AjaxPartialTemplateMixin, ModuleAccessRequiredMixin, ListView):
    model = Route
    template_name = "schools/route_list.html"
    ajax_template_name = "schools/_route_results.html"
    context_object_name = "routes"
    paginate_by = 25
    module_codename = "artifacts_mcps"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("driver", "attendant")

        query = self.request.GET.get("q")
        if query:
            queryset = queryset.filter(
                Q(route_number__icontains=query)
                | Q(bus_number__icontains=query)
                | Q(driver__name__icontains=query)
                | Q(attendant__name__icontains=query)
            )

        sort = self.request.GET.get("sort", "")
        if sort.lstrip("-") in ROUTE_SORTABLE_FIELDS:
            queryset = queryset.order_by(sort, "route_number")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "")
        sort = self.request.GET.get("sort", "")

        context["query"] = query
        context["sort_key"] = sort.lstrip("-")
        context["sort_reverse"] = sort.startswith("-")

        base_params = {}
        if query:
            base_params["q"] = query

        for field in ROUTE_SORTABLE_FIELDS:
            next_sort = f"-{field}" if sort == field else field
            context[f"{field}_sort_url"] = "?" + urlencode({**base_params, "sort": next_sort})

        if sort:
            base_params["sort"] = sort
        context["extra_qs"] = urlencode(base_params)

        return context


class RouteCreateView(ModuleAccessRequiredMixin, CreateView):
    model = Route
    form_class = RouteForm
    template_name = "schools/route_form.html"
    success_url = reverse_lazy("schools:route_list")
    module_codename = "artifacts_mcps"


class RouteUpdateView(ModuleAccessRequiredMixin, UpdateView):
    model = Route
    form_class = RouteForm
    template_name = "schools/route_form.html"
    success_url = reverse_lazy("schools:route_list")
    module_codename = "artifacts_mcps"


class RouteDeleteView(ModuleAccessRequiredMixin, DeleteView):
    model = Route
    template_name = "schools/route_confirm_delete.html"
    success_url = reverse_lazy("schools:route_list")
    module_codename = "artifacts_mcps"


class AmMidPmEntryListView(AjaxPartialTemplateMixin, ModuleAccessRequiredMixin, ListView):
    model = AmMidPmEntry
    template_name = "schools/ammidpm_list.html"
    ajax_template_name = "schools/_ammidpm_results.html"
    context_object_name = "entries"
    paginate_by = 25
    module_codename = "artifacts_mcps"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("route")

        run_type = self.request.GET.get("type")
        if run_type:
            queryset = queryset.filter(type=run_type)

        query = self.request.GET.get("q")
        if query:
            queryset = queryset.filter(
                Q(route__route_number__icontains=query) | Q(address__icontains=query)
            )

        sort = self.request.GET.get("sort", "")
        if sort.lstrip("-") in AMMIDPM_SORTABLE_FIELDS:
            queryset = queryset.order_by(sort, "route__route_number", "seq")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "")
        selected_type = self.request.GET.get("type", "")
        sort = self.request.GET.get("sort", "")

        context["run_types"] = AmMidPmEntry.RunType.choices
        context["selected_type"] = selected_type
        context["query"] = query
        context["sort_key"] = sort.lstrip("-")
        context["sort_reverse"] = sort.startswith("-")

        base_params = {}
        if query:
            base_params["q"] = query
        if selected_type:
            base_params["type"] = selected_type

        for field in AMMIDPM_SORTABLE_FIELDS:
            next_sort = f"-{field}" if sort == field else field
            context[f"{field}_sort_url"] = "?" + urlencode({**base_params, "sort": next_sort})

        if sort:
            base_params["sort"] = sort
        context["extra_qs"] = urlencode(base_params)

        return context


class AmMidPmRoutesDatalistMixin:
    """Feeds the `<datalist>` of existing MCPS Route numbers that the `route`
    text field in AmMidPmEntryForm autocompletes against."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["route_numbers"] = Route.objects.order_by("route_number").values_list(
            "route_number", flat=True
        )
        return context


class AmMidPmEntryCreateView(AmMidPmRoutesDatalistMixin, ModuleAccessRequiredMixin, CreateView):
    model = AmMidPmEntry
    form_class = AmMidPmEntryForm
    template_name = "schools/ammidpm_form.html"
    success_url = reverse_lazy("schools:ammidpm_list")
    module_codename = "artifacts_mcps"


class AmMidPmEntryUpdateView(AmMidPmRoutesDatalistMixin, ModuleAccessRequiredMixin, UpdateView):
    model = AmMidPmEntry
    form_class = AmMidPmEntryForm
    template_name = "schools/ammidpm_form.html"
    success_url = reverse_lazy("schools:ammidpm_list")
    module_codename = "artifacts_mcps"


class AmMidPmEntryDeleteView(ModuleAccessRequiredMixin, DeleteView):
    model = AmMidPmEntry
    template_name = "schools/ammidpm_confirm_delete.html"
    success_url = reverse_lazy("schools:ammidpm_list")
    module_codename = "artifacts_mcps"


class LeftsRightsDomainMixin:
    """MCPS and Transportation each get their OWN, fully independent set of
    Lefts & Rights guides and Depot links — LeftRight.domain / DepotLink.
    domain keeps the actual rows apart (nothing created under one ever
    shows up under the other), and this mixin keeps every queryset,
    create, redirect, and cross-link scoped to `self.domain`. Both
    "flavors" are the exact same view classes, registered TWICE in
    schools/urls.py — once at `lefts-rights/...` (`domain` left at its
    default, `"mcps"`) and once at `transportation/lefts-rights/...` (via
    `.as_view(domain="transportation")`) — so nothing about how a request
    is handled is shared between them beyond the Python code itself.

    `module_codename` is derived from `domain` (not set directly on any of
    these views) so the two always move together: an MCPS URL is gated on
    'artifacts_mcps', a Transportation URL on 'transportation', never
    both — see ModuleAccessRequiredMixin."""
    # Plain strings on purpose (not LeftRight.Domain.MCPS/.TRANSPORTATION)
    # -- .as_view(domain="transportation") in urls.py passes a plain str,
    # and keeping this attribute/dict plain avoids relying on TextChoices'
    # str-equality semantics for what's ultimately just a URL-routing flag.
    domain = "mcps"

    _MODULE_BY_DOMAIN = {
        "mcps": "artifacts_mcps",
        "transportation": "transportation",
    }

    @property
    def module_codename(self):
        return self._MODULE_BY_DOMAIN[self.domain]

    def url_name(self, base):
        """`base` is one of the shared, un-prefixed URL names
        (lefts_rights, leftright_create, leftright_detail,
        leftright_update, leftright_delete, depot, depot_list) — returns
        the fully-qualified name for THIS view's domain."""
        prefix = "" if self.domain == "mcps" else "transportation_"
        return f"schools:{prefix}{base}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["domain"] = self.domain
        context["url_names"] = {
            base: self.url_name(base)
            for base in ("lefts_rights", "leftright_create", "leftright_detail",
                         "leftright_update", "leftright_delete", "leftright_row_save",
                         "depot", "depot_list")
        }
        # depot_upload is a stateless mailer with no LeftRight/DepotLink
        # queries of its own (see DepotUploadView) -- one URL serves both
        # domains, nothing to keep apart.
        context["url_names"]["depot_upload"] = "schools:depot_upload"
        return context

    def get_queryset(self):
        return super().get_queryset().filter(domain=self.domain)

    def lefts_rights_url(self, route_name):
        return reverse_lazy(self.url_name("lefts_rights")) + "?" + urlencode({"route": route_name})


class LeftsRightsView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, TemplateView):
    """Landing page for Lefts & Rights: pick a route name — the dropdown
    only lists route names that already have at least one LeftRight in
    THIS domain — and see that route's named LeftRight guides as links.
    What a given LeftRight actually shows once you click it is handled by
    LeftRightDetailView. Route names here are LeftRight.route_name, a
    free-text label independent of the MCPS Routes catalog.

    Registered twice (see LeftsRightsDomainMixin): once for MCPS at
    schools:lefts_rights (unchanged from before Transportation existed),
    once for Transportation at schools:transportation_lefts_rights — two
    completely independent sets of guides, never mixed."""
    template_name = "schools/lefts_rights.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["route_names"] = (
            LeftRight.objects.filter(domain=self.domain)
            .order_by("route_name").values_list("route_name", flat=True).distinct()
        )

        route_name = self.request.GET.get("route", "").strip()
        if not route_name:
            return context

        lefts_rights = LeftRight.objects.filter(domain=self.domain, route_name=route_name).order_by("name")
        if not lefts_rights.exists():
            context["error"] = "Route not found."
            return context
        context["selected_route"] = route_name
        context["lefts_rights"] = lefts_rights
        return context


class LeftRightRouteNamesDatalistMixin:
    """Feeds the `<datalist>` of route names already used by existing
    LeftRight guides IN THIS DOMAIN, so a user adding another guide to the
    same route can match the existing spelling exactly — purely a
    suggestion, not enforced (LeftRight.route_name isn't tied to any other
    catalog)."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["route_names"] = (
            LeftRight.objects.filter(domain=self.domain)
            .order_by("route_name").values_list("route_name", flat=True).distinct()
        )
        return context


class LeftRightCreateView(LeftRightRouteNamesDatalistMixin, LeftsRightsDomainMixin, ModuleAccessRequiredMixin, CreateView):
    # Route always starts blank (no prefill from the selected route on the
    # Lefts & Rights page) — the user types the route name fresh every
    # time, since one route commonly gets several LeftRights added in a
    # row under different names.
    model = LeftRight
    form_class = LeftRightForm
    template_name = "schools/leftright_form.html"

    def get_form(self, form_class=None):
        # Set domain on the instance BEFORE is_valid()/full_clean() runs,
        # not just in form_valid() -- LeftRight's unique_together-style
        # constraint is (domain, route_name, name), so validating
        # uniqueness needs the real domain already on the instance, not
        # the field's bare default.
        form = super().get_form(form_class)
        form.instance.domain = self.domain
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        # Seed the four default content rows every LeftRight opens with on
        # its Edit page — two large-bold title rows, one normal-bold row,
        # one plain row — see LeftRightRow and leftright_form.html. order
        # is spaced by tens (10, 20, 30, 40) to match the edit page's
        # "sequence" column, leaving room to insert rows between them later
        # (e.g. entering 25 to insert between the 20 and 30 rows) without
        # renumbering anything.
        LeftRightRow.objects.bulk_create([
            LeftRightRow(leftright=self.object, order=10, row_type=LeftRightRow.RowType.TITLE),
            LeftRightRow(leftright=self.object, order=20, row_type=LeftRightRow.RowType.TITLE),
            LeftRightRow(leftright=self.object, order=30, row_type=LeftRightRow.RowType.BOLD),
            LeftRightRow(leftright=self.object, order=40, row_type=LeftRightRow.RowType.NORMAL),
        ])
        return response

    def get_success_url(self):
        return self.lefts_rights_url(self.object.route_name)


class LeftRightUpdateView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, DetailView):
    """Edit page for one LeftRight's content rows. GET-only -- rows
    autosave via AJAX (see LeftRightRowSaveView + leftright_form.html's
    JS) the instant each one is added, edited, or removed, so there's no
    Save/Cancel step and no POST handler here at all. route_name/name are
    set once at creation (LeftRightCreateView) and aren't editable here."""
    model = LeftRight
    template_name = "schools/leftright_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # auto_id=False: these are rendered one-per-row with no formset
        # prefix, so Django's default id="id_text" etc. would collide
        # across rows -- the JS targets fields by class (lr-text/
        # lr-address/...) instead, so no ids are needed at all.
        context.setdefault(
            "row_forms", [LeftRightRowForm(instance=row, auto_id=False) for row in self.object.rows.all()]
        )
        return context


class LeftRightRowSaveView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, View):
    """Autosave endpoint backing every row on the Edit page
    (leftright_form.html) -- POSTed to immediately on blur, and right when
    a new row is added via Insertar fila/vinculo/Post Trip, so there's no
    explicit Save step left to forget. `pk` in the URL is the parent
    LeftRight (scoped to self.domain like everything else in this file so
    a row can never be attached to the wrong domain's guide); `row_id` in
    the POST body identifies the LeftRightRow being saved, blank for a
    brand-new row -- in which case one is created here and its id handed
    back in the JSON response so the page can target that same row (not
    create a duplicate) on its next edit. `delete=1` deletes `row_id`
    instead of saving it."""

    def post(self, request, *args, **kwargs):
        leftright = get_object_or_404(LeftRight, pk=kwargs["pk"], domain=self.domain)
        row_id = request.POST.get("row_id") or None

        if request.POST.get("delete") == "1":
            if row_id:
                LeftRightRow.objects.filter(pk=row_id, leftright=leftright).delete()
            return JsonResponse({"ok": True, "deleted": True})

        row_type = request.POST.get("row_type", "")
        if row_type not in LeftRightRow.RowType.values:
            return JsonResponse({"ok": False, "error": "Invalid row type."}, status=400)

        try:
            order = int(request.POST.get("order") or 0)
        except ValueError:
            order = 0

        if row_id:
            row = get_object_or_404(LeftRightRow, pk=row_id, leftright=leftright)
        else:
            row = LeftRightRow(leftright=leftright)

        row.row_type = row_type
        row.order = order
        row.text = request.POST.get("text", "")[:255]
        row.address = request.POST.get("address", "")[:255]
        row.text_after = request.POST.get("text_after", "")[:255]
        row.save()

        return JsonResponse({"ok": True, "id": row.pk})


class LeftRightDeleteView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, DeleteView):
    model = LeftRight
    template_name = "schools/leftright_confirm_delete.html"

    def get_success_url(self):
        return self.lefts_rights_url(self.object.route_name)


class LeftRightDetailView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, DetailView):
    """Renders one LeftRight guide's content rows (LeftRightRow), in order,
    styled per row_type — the driver-facing cheat sheet built on the Edit
    page (LeftRightUpdateView). Bare page (base_bare.html, no KeyByMe
    nav), Print + Depot buttons only.

    Used to be deliberately public — no LoginRequiredMixin/
    ModuleAccessRequiredMixin — same reasoning as DepotListView below, so a
    driver without a KeyByMe account could open a shared link and see/print
    the guide. Transportation's policy is different on purpose: every
    driver needs their own KeyByMe account now (self-signup + admin
    approval makes that easy — see accounts/adapters.py), so this requires
    one like the rest of the module."""
    model = LeftRight
    template_name = "schools/leftright_detail.html"
    context_object_name = "leftright"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("rows")


class LeftRightShareDetailView(LeftRightDetailView):
    """Identical to LeftRightDetailView except it hides the Depot button —
    DepotLink.url can point here instead of the plain detail page for a
    cleaner read-only view (no editor button). Both require login now (see
    LeftRightDetailView); this no longer has anything to do with public vs.
    private access. MCPS-only for now — nothing in Transportation links to
    it yet, but it inherits the same domain scoping regardless."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hide_depot_button"] = True
        return context


class DepotView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, TemplateView):
    """A single page shared by every LeftRight IN THIS DOMAIN (reached via
    the "Depot" button on LeftRightDetailView) -- a flat, editable list of
    DepotLink rows, not tied to any one route/guide. Same edit-in-place
    formset pattern as LeftRightUpdateView, but modelformset_factory
    instead of inlineformset_factory since DepotLink has no parent FK."""
    template_name = "schools/depot.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault(
            "formset", DepotLinkFormSet(queryset=DepotLink.objects.filter(domain=self.domain), prefix="depot")
        )
        return context

    def post(self, request, *args, **kwargs):
        formset = DepotLinkFormSet(
            request.POST, queryset=DepotLink.objects.filter(domain=self.domain), prefix="depot"
        )
        if formset.is_valid():
            # commit=False so the domain can be stamped onto new rows
            # before they're actually saved -- formset.save() alone has
            # no way to know which domain a brand-new DepotLink belongs
            # to, since it isn't a form field (see DepotLinkForm).
            instances = formset.save(commit=False)
            for obj in instances:
                obj.domain = self.domain
                obj.save()
            for obj in formset.deleted_objects:
                obj.delete()
            return redirect(self.url_name("depot"))
        return self.render_to_response(self.get_context_data(formset=formset))


class DepotListView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, TemplateView):
    """Read-only rendering of the Depot links ("Listar" button on
    DepotView) -- the "LEFTS & RIGHTS" row plus every DepotLink IN THIS
    DOMAIN as an actual <a href>, and the Print button (same
    isolate-and-print trick as LeftRightDetailView) lives here instead of
    on the editable DepotView, since printing raw <input> boxes there
    wouldn't read well.

    Used to be deliberately public, same reasoning as LeftRightDetailView
    above — now requires login (+ the matching module) like the rest of
    it."""
    template_name = "schools/depot_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Alphabetical by the text actually rendered — name, falling back to
        # the raw url when name is blank — matching DepotLink.__str__, not
        # the drag-order used on the editable DepotView.
        context["links"] = DepotLink.objects.filter(domain=self.domain).annotate(
            display_text=Lower(Coalesce(NullIf("name", Value("")), "url"))
        ).order_by("display_text")
        return context


class DepotUploadView(ModuleAccessRequiredMixin, View):
    """Backs the per-row "Update" icon on DepotListView (fetch() POST, see
    depot_list.html) -- one button per DepotLink/route, so documents can be
    sent in for that specific route. Emails the selected files straight to
    the dispatch inboxes as attachments, tagged with the route's name --
    deliberately not wired into MediaFile/storage quota, this is a
    pass-through mailer, not a vault upload.

    Doesn't read or write LeftRight/DepotLink at all (route_name here is
    just free text typed into the upload dialog, not a DB lookup), so
    unlike the rest of this file there's nothing domain-specific to keep
    apart — one URL/view serves both MCPS and Transportation.

    Used to be public on the same reasoning as DepotListView — now requires
    login (+ either the artifacts_mcps or transportation module) too, same
    as the rest of it. Still guarded by an extension whitelist and
    size/count caps regardless."""
    module_codename = ("artifacts_mcps", "transportation")

    DEPOT_UPLOAD_TO = ["wesnetwork@keybyme.com", "wesnetwork@gmail.com"]
    DEPOT_UPLOAD_CC = ["wesnetworking@gmail.com"]

    def post(self, request, *args, **kwargs):
        route_name = (request.POST.get("route_name") or "").strip()[:255]

        files = request.FILES.getlist("files")
        if not files:
            return JsonResponse({"ok": False, "error": "No files were selected."}, status=400)
        if len(files) > DEPOT_UPLOAD_MAX_FILES:
            return JsonResponse(
                {"ok": False, "error": f"Please upload at most {DEPOT_UPLOAD_MAX_FILES} files at a time."},
                status=400,
            )

        total_size = 0
        for f in files:
            extension = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
            if extension not in DEPOT_UPLOAD_ALLOWED_EXTENSIONS:
                return JsonResponse(
                    {"ok": False, "error": f'"{f.name}" is not an allowed file type.'}, status=400
                )
            total_size += f.size
        if total_size > DEPOT_UPLOAD_MAX_TOTAL_BYTES:
            return JsonResponse({"ok": False, "error": "Total upload size is too large (20 MB max)."}, status=400)

        route_suffix = f" — {route_name}" if route_name else ""
        email = EmailMessage(
            subject=f"Clarksburg Depot — new documents{route_suffix}",
            body=(
                f"{len(files)} file(s) were uploaded from the Clarksburg Depot page"
                + (f' for "{route_name}"' if route_name else "")
                + ":\n\n"
                + "\n".join(f"- {f.name}" for f in files)
            ),
            to=self.DEPOT_UPLOAD_TO,
            cc=self.DEPOT_UPLOAD_CC,
        )
        for f in files:
            email.attach(f.name, f.read(), f.content_type)
        email.send(fail_silently=False)

        return JsonResponse({"ok": True})
