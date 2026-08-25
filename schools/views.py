from urllib.parse import urlencode

from django.core.mail import EmailMessage
from django.db.models import Q, Value
from django.db.models.functions import Coalesce, Lower, NullIf
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from vault.mixins import AjaxPartialTemplateMixin, ModuleAccessRequiredMixin

from .forms import (
    AmMidPmEntryForm, DepotLinkFormSet, EmployeeForm, LeftRightForm, LeftRightRowFormSet, RouteForm, SchoolForm,
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


class LeftsRightsView(ModuleAccessRequiredMixin, TemplateView):
    """Landing page for MCPS Lefts & Rights: pick a route name — the
    dropdown only lists route names that already have at least one
    LeftRight — and see that route's named LeftRight guides as links. What
    a given LeftRight actually shows once you click it is handled by
    LeftRightDetailView. Route names here are LeftRight.route_name, a
    free-text label independent of the MCPS Routes catalog."""
    template_name = "schools/lefts_rights.html"
    module_codename = "artifacts_mcps"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["route_names"] = (
            LeftRight.objects.order_by("route_name").values_list("route_name", flat=True).distinct()
        )

        route_name = self.request.GET.get("route", "").strip()
        if not route_name:
            return context

        lefts_rights = LeftRight.objects.filter(route_name=route_name).order_by("name")
        if not lefts_rights.exists():
            context["error"] = "Route not found."
            return context
        context["selected_route"] = route_name
        context["lefts_rights"] = lefts_rights
        return context


class LeftRightRouteNamesDatalistMixin:
    """Feeds the `<datalist>` of route names already used by existing
    LeftRight guides, so a user adding another guide to the same route can
    match the existing spelling exactly — purely a suggestion, not
    enforced (LeftRight.route_name isn't tied to any other catalog)."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["route_names"] = (
            LeftRight.objects.order_by("route_name").values_list("route_name", flat=True).distinct()
        )
        return context


class LeftRightCreateView(LeftRightRouteNamesDatalistMixin, ModuleAccessRequiredMixin, CreateView):
    # Route always starts blank (no prefill from the selected route on the
    # Lefts & Rights page) — the user types the route name fresh every
    # time, since one route commonly gets several LeftRights added in a
    # row under different names.
    model = LeftRight
    form_class = LeftRightForm
    template_name = "schools/leftright_form.html"
    module_codename = "artifacts_mcps"

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
        return reverse_lazy("schools:lefts_rights") + "?" + urlencode({"route": self.object.route_name})


class LeftRightUpdateView(ModuleAccessRequiredMixin, DetailView):
    """Edit page for one LeftRight's content rows (LeftRightRowFormSet)
    only — route_name/name are set once at creation (LeftRightCreateView)
    and aren't editable here, so this isn't a ModelForm/UpdateView at all,
    just a DetailView that also handles the formset's POST."""
    model = LeftRight
    template_name = "schools/leftright_form.html"
    module_codename = "artifacts_mcps"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("row_formset", LeftRightRowFormSet(instance=self.object, prefix="rows"))
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        row_formset = LeftRightRowFormSet(request.POST, instance=self.object, prefix="rows")
        if row_formset.is_valid():
            row_formset.save()
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(row_formset=row_formset))

    def get_success_url(self):
        return reverse_lazy("schools:lefts_rights") + "?" + urlencode({"route": self.object.route_name})


class LeftRightDeleteView(ModuleAccessRequiredMixin, DeleteView):
    model = LeftRight
    template_name = "schools/leftright_confirm_delete.html"
    module_codename = "artifacts_mcps"

    def get_success_url(self):
        return reverse_lazy("schools:lefts_rights") + "?" + urlencode({"route": self.object.route_name})


class LeftRightDetailView(DetailView):
    """Renders one LeftRight guide's content rows (LeftRightRow), in order,
    styled per row_type — the driver-facing cheat sheet built on the Edit
    page (LeftRightUpdateView). Bare page (base_bare.html, no KeyByMe
    nav), Print + Depot buttons only.

    Deliberately public — no LoginRequiredMixin/ModuleAccessRequiredMixin
    — same reasoning as DepotListView: a driver who isn't a KeyByMe user
    can open a shared link and see/print the guide."""
    model = LeftRight
    template_name = "schools/leftright_detail.html"
    context_object_name = "leftright"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("rows")


class LeftRightShareDetailView(LeftRightDetailView):
    """Identical to LeftRightDetailView except it hides the Depot button
    (which points at the login-gated /depot/ editor) -- this is what
    DepotLink.url should point at instead of the plain detail page, so a
    visitor arriving via the public Depot list has no way to reach the
    editor from here."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hide_depot_button"] = True
        return context


class DepotView(ModuleAccessRequiredMixin, TemplateView):
    """A single page shared by every LeftRight (reached via the "Depot"
    button on LeftRightDetailView) -- a flat, editable list of DepotLink
    rows, not tied to any one route/guide. Same edit-in-place formset
    pattern as LeftRightUpdateView, but modelformset_factory instead of
    inlineformset_factory since DepotLink has no parent FK."""
    template_name = "schools/depot.html"
    module_codename = "artifacts_mcps"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault(
            "formset", DepotLinkFormSet(queryset=DepotLink.objects.all(), prefix="depot")
        )
        return context

    def post(self, request, *args, **kwargs):
        formset = DepotLinkFormSet(request.POST, queryset=DepotLink.objects.all(), prefix="depot")
        if formset.is_valid():
            formset.save()
            return redirect("schools:depot")
        return self.render_to_response(self.get_context_data(formset=formset))


class DepotListView(TemplateView):
    """Read-only rendering of the Depot links ("Listar" button on
    DepotView) -- the "LEFTS & RIGHTS" row plus every DepotLink as an
    actual <a href>, and the Print button (same isolate-and-print trick as
    LeftRightDetailView) lives here instead of on the editable DepotView,
    since printing raw <input> boxes there wouldn't read well.

    Deliberately public — no LoginRequiredMixin/ModuleAccessRequiredMixin,
    unlike every other schools view. Anyone with the link can view/print
    it; base.html's `{% if user.is_authenticated %}` already hides the
    KeyByMe nav/storage bar for anonymous visitors (same pattern as
    vault's public vehicle/medical-record QR pages), so a logged-out
    visitor sees nothing but "Depot" and the links."""
    template_name = "schools/depot_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Alphabetical by the text actually rendered — name, falling back to
        # the raw url when name is blank — matching DepotLink.__str__, not
        # the drag-order used on the editable DepotView.
        context["links"] = DepotLink.objects.annotate(
            display_text=Lower(Coalesce(NullIf("name", Value("")), "url"))
        ).order_by("display_text")
        return context


class DepotUploadView(View):
    """Backs the "Update" icon on DepotListView (fetch() POST, see
    depot_list.html). Lets anyone with the public depot-list link attach
    one or more documents/photos and emails them straight to the dispatch
    inboxes as attachments -- deliberately not wired into MediaFile/storage
    quota, this is a pass-through mailer, not a vault upload.

    Public on purpose, same reasoning as DepotListView: a driver who isn't
    a KeyByMe user still needs to be able to send in paperwork from this
    page. Guarded only by an extension whitelist and size/count caps, since
    there's no login to rate-limit by."""

    DEPOT_UPLOAD_TO = ["wesnetwork@keybyme.com", "wesnetwork@gmail.com"]
    DEPOT_UPLOAD_CC = ["wesnetworking@gmail.com"]

    def post(self, request, *args, **kwargs):
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

        email = EmailMessage(
            subject="Clarksburg Depot — new documents uploaded",
            body=(
                f"{len(files)} file(s) were uploaded from the Clarksburg Depot page:\n\n"
                + "\n".join(f"- {f.name}" for f in files)
            ),
            to=self.DEPOT_UPLOAD_TO,
            cc=self.DEPOT_UPLOAD_CC,
        )
        for f in files:
            email.attach(f.name, f.read(), f.content_type)
        email.send(fail_silently=False)

        return JsonResponse({"ok": True})
