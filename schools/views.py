import time
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core.mail import EmailMessage
from django.db.models import Count, Max, Q, Value
from django.db.models.functions import Coalesce, Lower, NullIf
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from vault.mixins import AjaxPartialTemplateMixin, ModuleAccessRequiredMixin
from vault.routing import GeocodingRateLimited, geocode_address, get_route_legs

from .forms import (
    AmMidPmEntryForm, DepotLinkFormSet, EmployeeForm, LeftRightAddressListForm, LeftRightForm, LeftRightRowForm,
    LeftRightSheetUploadForm, RouteForm, SchoolForm,
)
from .leftright_sheet_text import extract_sheet_text, parse_sheet_text, validate_sheet_file
from .models import (
    AmMidPmEntry, DepotLink, Employee, LEFTRIGHT_SHEET_ALLOWED_EXTENSIONS, LEFTRIGHT_SHEET_IMAGE_EXTENSIONS,
    LEFTRIGHT_SHEET_RETENTION_DAYS, LeftRight, LeftRightAddressList, LeftRightRow, LeftRightSheetUpload, Route,
    School,
)

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
                         "leftright_addresses", "leftright_generate_rows",
                         "leftright_create_from_addresses", "leftright_route_list",
                         "leftright_route_delete", "leftright_route_rename", "leftright_address_list_delete",
                         "leftright_sheet_upload", "leftright_sheet_upload_delete",
                         "leftright_generate_rows_from_sheet",
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
    lists every route name that has EITHER at least one LeftRight guide
    OR a saved LeftRightAddressList (the "Addresses" page) in THIS
    domain, so a route becomes selectable here as soon as its addresses
    are saved, even before its first guide exists — and see that route's
    named LeftRight guides as links (or, for an addresses-only route, the
    empty state prompting "Add Left & Right"). What a given LeftRight
    actually shows once you click it is handled by LeftRightDetailView.
    Route names here are LeftRight.route_name / LeftRightAddressList.
    route_name, the same free-text label, independent of the MCPS Routes
    catalog.

    Registered twice (see LeftsRightsDomainMixin): once for MCPS at
    schools:lefts_rights (unchanged from before Transportation existed),
    once for Transportation at schools:transportation_lefts_rights — two
    completely independent sets of guides, never mixed."""
    template_name = "schools/lefts_rights.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leftright_route_names = set(
            LeftRight.objects.filter(domain=self.domain).values_list("route_name", flat=True)
        )
        address_route_names = set(
            LeftRightAddressList.objects.filter(domain=self.domain).values_list("route_name", flat=True)
        )
        context["route_names"] = sorted(leftright_route_names | address_route_names)

        route_name = self.request.GET.get("route", "").strip()
        if not route_name:
            return context
        # Set even on the not-found path below: the template's error
        # display is itself gated on selected_route being set (it doubles
        # as "was anything actually searched for" — see lefts_rights.html)
        # — leaving it unset there meant "Route not found" could never
        # actually render. Harmless if the name matches no <option>: the
        # dropdown just falls back to showing its placeholder.
        context["selected_route"] = route_name
        # Drives the "Generate from Addresses" button on the empty state
        # (lefts_rights.html) -- only meaningful when this route has zero
        # LeftRight guides yet, but harmless to set regardless.
        context["has_address_list"] = route_name in address_route_names

        # A route counts as "known" (no "Route not found" error) as soon
        # as it appears from EITHER source above -- an addresses-only
        # route legitimately has zero LeftRight rows yet, that's not an
        # error, the empty state below (leftright_form.html's "Add Left &
        # Right") is what fills it in.
        if route_name not in leftright_route_names and route_name not in address_route_names:
            context["error"] = "Route not found."
            return context
        context["lefts_rights"] = LeftRight.objects.filter(domain=self.domain, route_name=route_name).order_by("name")
        return context


class LeftRightRouteListView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, TemplateView):
    """"Routes" page -- clock + client-side search + list, same look as
    DepotListView/depot_list.html, but with the normal KeyByMe nav (unlike
    Depot/the printable detail page, this is a management page reached
    from within the app, not something meant to look identical to an
    anonymous driver) -- listing every route name known in THIS domain
    (has a LeftRight guide, a saved LeftRightAddressList, or both -- same
    union LeftsRightsView's dropdown uses) with its guide count, each
    linking straight into schools:lefts_rights?route=<name>, plus a trash
    icon (LeftRightRouteDeleteView) to remove the whole route at once. A
    quick way to find/open (or clean up) a route without going through
    the dropdown first."""
    template_name = "schools/leftright_route_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guide_counts = dict(
            LeftRight.objects.filter(domain=self.domain)
            .values_list("route_name").annotate(count=Count("id"))
        )
        address_route_names = set(
            LeftRightAddressList.objects.filter(domain=self.domain).values_list("route_name", flat=True)
        )
        all_route_names = sorted(set(guide_counts) | address_route_names)
        context["routes"] = [{"name": name, "count": guide_counts.get(name, 0)} for name in all_route_names]
        return context


class LeftRightRouteDeleteView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, TemplateView):
    """Confirm-then-delete for one whole route, from the trash icon on
    the "Routes" page (leftright_route_list.html) -- removes every
    LeftRight guide for (domain, route_name) at once (cascades to their
    LeftRightRow rows, per LeftRightRow.leftright's on_delete=CASCADE)
    plus the route's LeftRightAddressList, if any -- everything tied to
    that route name in this domain, gone in one action, since a route
    with several guides (e.g. AM/PM) has no single LeftRight to delete
    from a plain confirm-delete page the way LeftRightDeleteView does for
    one guide.

    `route_name` travels as `?route=`/a POST field, the same convention
    the rest of this file uses, rather than a URL path segment --
    route names are free text and could contain characters that don't
    survive a path segment cleanly."""
    template_name = "schools/leftright_route_confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        route_name = self.request.GET.get("route", "").strip()
        context["route_name"] = route_name
        context["guide_count"] = LeftRight.objects.filter(domain=self.domain, route_name=route_name).count()
        context["has_address_list"] = LeftRightAddressList.objects.filter(
            domain=self.domain, route_name=route_name
        ).exists()
        return context

    def post(self, request, *args, **kwargs):
        route_name = request.POST.get("route", "").strip()
        list_url = reverse_lazy(self.url_name("leftright_route_list"))
        if not route_name:
            return redirect(list_url)

        LeftRight.objects.filter(domain=self.domain, route_name=route_name).delete()
        LeftRightAddressList.objects.filter(domain=self.domain, route_name=route_name).delete()
        messages.success(request, f'Deleted route "{route_name}" — its guides and saved addresses are gone.')
        return redirect(list_url)


class LeftRightRouteRenameView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, TemplateView):
    """Rename a whole route, from the pencil icon next to the route picker
    on the "Lefts & Rights" page (lefts_rights.html), shown once a route
    is selected there -- renames route_name across every LeftRight guide,
    LeftRightAddressList, and LeftRightSheetUpload row for (domain, route
    name) at once, same "everything tied to this route name, in one
    action" scope as LeftRightRouteDeleteView, just updating instead of
    deleting.

    `route` travels as `?route=`/a POST field, same convention as the rest
    of this file. Refuses the rename outright if the new name is already
    in use in this domain (by a guide, a saved address list, or an
    uploaded file) rather than trying to merge the two routes together --
    same conservative call LeftRightCreateFromAddressesView makes for a
    route that already has a guide."""
    template_name = "schools/leftright_route_rename.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["route_name"] = self.request.GET.get("route", "").strip()
        return context

    def post(self, request, *args, **kwargs):
        old_name = request.POST.get("route", "").strip()
        new_name = request.POST.get("new_route_name", "").strip()
        rename_url = reverse_lazy(self.url_name("leftright_route_rename")) + "?" + urlencode({"route": old_name})

        if not old_name:
            return redirect(reverse_lazy(self.url_name("lefts_rights")))
        if not new_name:
            messages.error(request, "Enter a new name for the route.")
            return redirect(rename_url)
        if new_name == old_name:
            return redirect(self.lefts_rights_url(old_name))

        name_taken = (
            LeftRight.objects.filter(domain=self.domain, route_name=new_name).exists()
            or LeftRightAddressList.objects.filter(domain=self.domain, route_name=new_name).exists()
            or LeftRightSheetUpload.objects.filter(domain=self.domain, route_name=new_name).exists()
        )
        if name_taken:
            messages.error(request, f'Route "{new_name}" already exists — pick a different name.')
            return redirect(rename_url)

        LeftRight.objects.filter(domain=self.domain, route_name=old_name).update(route_name=new_name)
        LeftRightAddressList.objects.filter(domain=self.domain, route_name=old_name).update(route_name=new_name)
        LeftRightSheetUpload.objects.filter(domain=self.domain, route_name=old_name).update(route_name=new_name)

        messages.success(request, f'Renamed route "{old_name}" to "{new_name}".')
        return redirect(self.lefts_rights_url(new_name))


class LeftRightAddressListView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, TemplateView):
    """MCPS's "Addresses" page: type/pick a route name and paste 4-15
    addresses, one per line, in visiting order — saved as a
    LeftRightAddressList, always fully replacing whatever was saved
    before for that (domain, route_name). Doesn't touch any LeftRight/
    LeftRightRow itself; LeftRightGenerateRowsView (button on the Edit
    page) is what turns this into a guide's actual turn-by-turn rows
    later, matched purely by route_name + domain -- so addresses can be
    entered here before their LeftRight even exists.

    `?route=` selects which saved list to show/edit (same convention as
    LeftsRightsView) -- typing a brand-new route name and saving creates
    one instead.

    Transportation's flavor of this same page is titled "Uploads"
    instead, and drops the address-list form/picker entirely (see
    leftright_addresses.html's `{% if domain != "transportation" %}` —
    Transportation only ever uses file uploads (LeftRightSheetUploadView)
    to draft a guide's rows, not typed-in addresses) — both domains keep
    the upload panel and the "Uploaded documents" listing below it."""
    template_name = "schools/leftright_addresses.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # `leftright_route_names` (routes with an actual LeftRight guide)
        # is the <datalist> for the free-text route fields on this page
        # (both the MCPS address form below and the upload panel), so
        # typing can match an existing guide's spelling exactly.
        context["leftright_route_names"] = (
            LeftRight.objects.filter(domain=self.domain)
            .order_by("route_name").values_list("route_name", flat=True).distinct()
        )
        route_name = self.request.GET.get("route", "").strip()
        context["selected_route"] = route_name

        # The address-list form/"load a saved list" picker only renders
        # for MCPS now (see leftright_addresses.html) -- Transportation
        # dropped it in favor of file uploads only (LeftRightSheetUploadView),
        # so skip these queries/instance lookups entirely for that domain.
        if self.domain != "transportation":
            # Routes that already HAVE a saved address list, for the
            # "load an existing one" <select>.
            context["route_names"] = (
                LeftRightAddressList.objects.filter(domain=self.domain)
                .order_by("route_name").values_list("route_name", flat=True)
            )
            context.setdefault(
                "form",
                LeftRightAddressListForm(
                    instance=LeftRightAddressList.objects.filter(domain=self.domain, route_name=route_name).first()
                    if route_name else None,
                    initial={"route_name": route_name} if route_name else None,
                ),
            )

        context.setdefault("sheet_upload_form", LeftRightSheetUploadForm())
        # Every uploaded file for this domain, across every route -- not
        # just `route_name` -- so the "Uploaded documents" listing is a
        # full audit list (each row shows its own route_name) rather than
        # a per-route preview.
        context["all_sheet_uploads"] = LeftRightSheetUpload.objects.filter(domain=self.domain).order_by("-uploaded_at")
        context["retention_days"] = LEFTRIGHT_SHEET_RETENTION_DAYS
        return context

    def post(self, request, *args, **kwargs):
        route_name = request.POST.get("route_name", "").strip()
        instance = (
            LeftRightAddressList.objects.filter(domain=self.domain, route_name=route_name).first()
            if route_name else None
        )
        form = LeftRightAddressListForm(request.POST, instance=instance)
        if form.is_valid():
            address_list = form.save(commit=False)
            address_list.domain = self.domain
            address_list.save()
            messages.success(
                request,
                f'Saved {len(address_list.address_lines)} address(es) for route "{address_list.route_name}".',
            )
            return redirect(
                reverse_lazy(self.url_name("leftright_addresses")) + "?" + urlencode({"route": address_list.route_name})
            )
        return self.render_to_response(self.get_context_data(form=form))


class LeftRightAddressListDeleteView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, TemplateView):
    """Confirm-then-delete for one saved address list, from the trash
    icon next to Save on the "Addresses" page (leftright_addresses.html,
    shown only once an existing list is loaded) -- removes the
    LeftRightAddressList for (domain, route_name). Doesn't touch any
    LeftRight/LeftRightRow -- if a guide already exists for this route,
    it's untouched; only the saved addresses (and the "Generate from
    Addresses" button they power, on both the Edit page and the list
    page's empty state) go away.

    `route_name` travels as `?route=`/a POST field, same convention as
    the rest of this file."""
    template_name = "schools/leftright_address_list_confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        route_name = self.request.GET.get("route", "").strip()
        context["route_name"] = route_name
        address_list = LeftRightAddressList.objects.filter(domain=self.domain, route_name=route_name).first()
        context["address_count"] = len(address_list.address_lines) if address_list else 0
        return context

    def post(self, request, *args, **kwargs):
        route_name = request.POST.get("route", "").strip()
        list_url = reverse_lazy(self.url_name("leftright_addresses"))
        if route_name:
            LeftRightAddressList.objects.filter(domain=self.domain, route_name=route_name).delete()
            messages.success(request, f'Deleted the saved addresses for route "{route_name}".')
        return redirect(list_url)


LEFTRIGHT_SHEET_MAX_FILES = 10


def _validate_and_extract_sheet_file(f):
    """Validates one uploaded file for LeftRightSheetUploadView --
    extension whitelist, then a real open-and-verify appropriate to that
    type (Pillow for images via forms.ImageField, schools/
    leftright_sheet_text.validate_sheet_file for PDF/DOCX) -- and extracts
    its text. Returns (cleaned_file, raw_text, warning) on success, where
    `warning` is set (raw_text left empty) instead of failing outright if
    the file is genuinely valid but text extraction itself broke (e.g.
    Tesseract being unavailable) -- a corrupted/mislabeled file is a hard
    reject (raises forms.ValidationError), a valid file with no readable
    text is not. `cleaned_file` is `f` itself for PDF/DOCX, or the
    Pillow-validated/rewound file forms.ImageField.clean() returns for
    images -- either way it's what gets saved to LeftRightSheetUpload.file,
    already rewound to the start."""
    extension = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
    if extension not in LEFTRIGHT_SHEET_ALLOWED_EXTENSIONS:
        raise forms.ValidationError(
            f'"{f.name}": not a supported file type. Allowed: photos, PDF, or DOCX.'
        )

    if extension in LEFTRIGHT_SHEET_IMAGE_EXTENSIONS:
        try:
            cleaned_file = forms.ImageField().clean(f)
        except forms.ValidationError as exc:
            raise forms.ValidationError(f'"{f.name}": ' + " ".join(exc.messages)) from exc
    else:
        try:
            validate_sheet_file(f, extension)
        except ValueError as exc:
            raise forms.ValidationError(f'"{f.name}": {exc}.') from exc
        cleaned_file = f

    cleaned_file.seek(0)
    try:
        raw_text = extract_sheet_text(cleaned_file, extension)
        warning = None
    except Exception as exc:
        raw_text = ""
        warning = f'"{f.name}": couldn\'t read any text from this file ({exc}) — it was saved anyway.'
    cleaned_file.seek(0)  # rewind so the file field save below still writes it to storage
    return cleaned_file, raw_text, warning


class LeftRightSheetUploadView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, View):
    """Backs the "Upload photos or documents" panel on the "Addresses" page
    (leftright_addresses.html) -- extracts text from each uploaded page of
    an already-existing Left & Right sheet (a photo, PDF, or DOCX -- see
    schools/leftright_sheet_text.py) and saves one LeftRightSheetUpload
    row per file, ADDED after whatever's already uploaded for that
    (domain, route_name) rather than replacing it (see
    LeftRightSheetUpload) -- a long route's paper sheet often spans more
    than one file. Each file is validated on its own
    (_validate_and_extract_sheet_file), so one bad file in a multi-file
    upload doesn't sink the good ones. Doesn't touch any LeftRight/
    LeftRightRow itself; LeftRightGenerateRowsFromSheetView (button on the
    Edit page) is what turns the extracted text into a guide's actual rows
    later, matched purely by route_name + domain -- so files can be
    uploaded here before their LeftRight even exists, same as the address
    list."""

    def post(self, request, *args, **kwargs):
        route_name = request.POST.get("route_name", "").strip()
        addresses_url = reverse_lazy(self.url_name("leftright_addresses"))
        redirect_url = (
            str(addresses_url) + "?" + urlencode({"route": route_name}) if route_name else str(addresses_url)
        )
        if not route_name:
            messages.error(request, "Type a route name before uploading a file.")
            return redirect(redirect_url)

        files = request.FILES.getlist("file")
        if not files:
            messages.error(request, "Choose at least one photo or document to upload.")
            return redirect(redirect_url)
        if len(files) > LEFTRIGHT_SHEET_MAX_FILES:
            messages.error(request, f"Please upload at most {LEFTRIGHT_SHEET_MAX_FILES} files at a time.")
            return redirect(redirect_url)

        next_order = (
            LeftRightSheetUpload.objects.filter(domain=self.domain, route_name=route_name)
            .aggregate(Max("order"))["order__max"] or 0
        )
        uploaded_count = 0
        any_text = False
        for f in files:
            try:
                cleaned_file, raw_text, warning = _validate_and_extract_sheet_file(f)
            except forms.ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
                continue
            if warning:
                messages.warning(request, warning)

            next_order += 10
            LeftRightSheetUpload.objects.create(
                domain=self.domain, route_name=route_name, order=next_order, file=cleaned_file, raw_text=raw_text,
            )
            uploaded_count += 1
            any_text = any_text or bool(raw_text.strip())

        if uploaded_count:
            suffix = (
                " — open its Left & Right guide's Edit page and use \"Generate from Sheet\" to draft rows from them."
                if any_text else " — no text could be read from them."
            )
            messages.success(request, f'Uploaded {uploaded_count} file(s) for route "{route_name}"{suffix}')
        return redirect(redirect_url)


class LeftRightSheetUploadDeleteView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, TemplateView):
    """Confirm-then-delete for ONE uploaded file (not the whole route's
    set), from the trash icon on that file's thumbnail on the "Addresses"
    page -- removes that LeftRightSheetUpload (and its underlying file,
    see LeftRightSheetUpload.delete()). Doesn't touch any other upload for
    the route, or any LeftRight/LeftRightRow/LeftRightAddressList."""
    template_name = "schools/leftright_sheet_upload_confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sheet_upload"] = get_object_or_404(LeftRightSheetUpload, pk=kwargs["pk"], domain=self.domain)
        return context

    def post(self, request, *args, **kwargs):
        sheet_upload = get_object_or_404(LeftRightSheetUpload, pk=kwargs["pk"], domain=self.domain)
        route_name = sheet_upload.route_name
        sheet_upload.delete()
        messages.success(request, f'Deleted a file for route "{route_name}".')
        addresses_url = reverse_lazy(self.url_name("leftright_addresses"))
        return redirect(str(addresses_url) + "?" + urlencode({"route": route_name}))


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
        # Only offer "Generate from Addresses" when there's actually
        # something to generate from -- see LeftRightGenerateRowsView.
        context["has_address_list"] = LeftRightAddressList.objects.filter(
            domain=self.domain, route_name=self.object.route_name
        ).exists()
        # Same idea for "Generate from Sheet" -- see
        # LeftRightGenerateRowsFromSheetView.
        context["has_sheet_upload"] = LeftRightSheetUpload.objects.filter(
            domain=self.domain, route_name=self.object.route_name
        ).exists()
        return context


# OSRM maneuver label (see vault.routing.MODIFIER_LABELS) -> the single
# direction letter LeftRightDetailView's icon trick looks for (R/L/S/U,
# followed by a wide gap -- see LeftRightRowSaveView's callers/
# leftright_detail.html). "Slight"/"Sharp" collapse to the same plain
# letter as a straight turn/right -- a driver cheat sheet doesn't need the
# distinction, and LeftRightDetailView only ever renders one icon per
# letter anyway.
GENERATE_ROWS_DIRECTION_LETTERS = {
    "Turn left": "L", "Slight left": "L", "Sharp left": "L",
    "Turn right": "R", "Slight right": "R", "Sharp right": "R",
    "U-turn": "U",
}


def _generate_rows_from_addresses(leftright, domain):
    """Geocodes+routes the LeftRightAddressList matching (domain,
    leftright.route_name) and bulk_creates the resulting rows onto
    `leftright`, appended after whatever's already there -- the shared
    core of LeftRightGenerateRowsView (Edit page button, existing
    LeftRight) and LeftRightCreateFromAddressesView (list page's empty-
    state button, creates the LeftRight too). See GENERATE_ROWS_
    DIRECTION_LETTERS/LeftRightGenerateRowsView's docstring for what this
    actually produces and why it's only ever a draft.

    Returns (row_count, address_count, None) on success, or
    (None, None, error_message) if nothing could be generated (no saved
    address list, too few addresses, a geocoding failure, rate limiting,
    or OSRM being unable to compute a route) -- never raises, callers
    surface the message via django.contrib.messages."""
    address_list = LeftRightAddressList.objects.filter(domain=domain, route_name=leftright.route_name).first()
    if address_list is None:
        return None, None, (
            f'No saved addresses for route "{leftright.route_name}" — add some on the Addresses page first.'
        )

    addresses = address_list.address_lines
    if len(addresses) < 4:
        return None, None, "The saved address list needs at least 4 addresses to generate directions."

    coords = []
    try:
        for address in addresses:
            coord = geocode_address(address)
            if coord is None:
                return None, None, (
                    f'Could not find coordinates for "{address}" — nothing was generated. '
                    f"Fix it on the Addresses page and try again."
                )
            coords.append(coord)
            time.sleep(1)  # stay well under LocationIQ's free-tier rate limit
    except GeocodingRateLimited:
        return None, None, (
            "OpenStreetMap's free geocoding service is rate-limiting this server right now "
            "(HTTP 429) — try again in a few minutes."
        )

    legs = get_route_legs(coords)
    if legs is None:
        return None, None, "Could not compute driving directions between these addresses right now — try again shortly."

    order = leftright.rows.aggregate(Max("order"))["order__max"] or 0
    new_rows = []
    for i, turns in enumerate(legs):
        for turn in turns:
            letter = GENERATE_ROWS_DIRECTION_LETTERS.get(turn["label"])
            if not letter:
                continue
            order += 10
            new_rows.append(LeftRightRow(
                leftright=leftright, order=order, row_type=LeftRightRow.RowType.NORMAL,
                text=f"{letter}     {turn['street']}",
            ))
        order += 10
        new_rows.append(LeftRightRow(
            leftright=leftright, order=order, row_type=LeftRightRow.RowType.LINK,
            text="STOP @", address=addresses[i + 1],
        ))
    LeftRightRow.objects.bulk_create(new_rows)
    return len(new_rows), len(addresses), None


class LeftRightGenerateRowsView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, View):
    """Backs the "Generate from Addresses" button on the Edit page, for a
    LeftRight that already exists -- see _generate_rows_from_addresses for
    what this actually does and why it's only ever a draft. Synchronous:
    a full 15-address list takes on the order of 15-30 seconds
    (LocationIQ's free tier is ~2 req/sec, spaced out to stay well under
    it) -- the browser just waits for the redirect back to the edit page,
    same as LeftRightRowSaveView's callers don't need to since this is a
    one-off action, not per-keystroke."""

    def post(self, request, *args, **kwargs):
        leftright = get_object_or_404(LeftRight, pk=kwargs["pk"], domain=self.domain)
        edit_url = reverse_lazy(self.url_name("leftright_update"), kwargs={"pk": leftright.pk})

        row_count, address_count, error = _generate_rows_from_addresses(leftright, self.domain)
        if error:
            messages.error(request, error)
        else:
            messages.success(
                request, f"Generated {row_count} row(s) from {address_count} addresses — review and adjust as needed."
            )
        return redirect(edit_url)


def _generate_rows_from_sheet_uploads(leftright, domain):
    """Turns every LeftRightSheetUpload matching (domain,
    leftright.route_name) into LeftRightRow rows on `leftright`, appended
    after whatever's already there -- the sheet-upload counterpart to
    _generate_rows_from_addresses, backing LeftRightGenerateRowsFromSheetView.
    When a route has several uploads (one per page of its paper sheet —
    see LeftRightSheetUpload), they're read in `order` and their parsed
    lines concatenated, so the generated rows read as one continuous guide
    rather than per-file. Uses schools/leftright_sheet_text.py's line
    classifier, which -- unlike _generate_rows_from_addresses' OSRM-driven
    directions -- is a rough guess at best; that's fine here since every
    row it creates lands on the Edit page's normal, already-editable rows
    (see LeftRightRowSaveView).

    Returns (row_count, None) on success, or (None, error_message) if
    nothing could be generated -- never raises, callers surface the
    message via django.contrib.messages."""
    sheet_uploads = LeftRightSheetUpload.objects.filter(domain=domain, route_name=leftright.route_name)
    if not sheet_uploads.exists():
        return None, (
            f'No uploaded files for route "{leftright.route_name}" — upload one on the Addresses page first.'
        )

    parsed_lines = []
    for sheet_upload in sheet_uploads:
        parsed_lines.extend(parse_sheet_text(sheet_upload.raw_text))
    if not parsed_lines:
        return None, "No text could be read from the uploaded file(s) — try re-uploading clearer ones."

    order = leftright.rows.aggregate(Max("order"))["order__max"] or 0
    new_rows = []
    for row_type, text, address in parsed_lines:
        order += 10
        new_rows.append(LeftRightRow(leftright=leftright, order=order, row_type=row_type, text=text, address=address))
    LeftRightRow.objects.bulk_create(new_rows)
    return len(new_rows), None


class LeftRightGenerateRowsFromSheetView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, View):
    """Backs the "Generate from Sheet" button on the Edit page, for a
    LeftRight that already exists -- see _generate_rows_from_sheet_uploads
    for what this actually does. Synchronous like LeftRightGenerateRowsView,
    but text extraction already ran at upload time
    (LeftRightSheetUploadView), so this is just a bulk_create -- fast, no
    redirect delay to warn about."""

    def post(self, request, *args, **kwargs):
        leftright = get_object_or_404(LeftRight, pk=kwargs["pk"], domain=self.domain)
        edit_url = reverse_lazy(self.url_name("leftright_update"), kwargs={"pk": leftright.pk})

        row_count, error = _generate_rows_from_sheet_uploads(leftright, self.domain)
        if error:
            messages.error(request, error)
        else:
            messages.success(
                request, f"Generated {row_count} row(s) from the uploaded file(s) — review and adjust as needed."
            )
        return redirect(edit_url)


class LeftRightCreateFromAddressesView(LeftsRightsDomainMixin, ModuleAccessRequiredMixin, View):
    """Backs the "Generate from Addresses" button shown on the list page's
    empty state (lefts_rights.html: "No Lefts & Rights yet for X") when
    that route has a saved LeftRightAddressList but no LeftRight guide at
    all yet -- creates one (name="Draft") and immediately runs
    _generate_rows_from_addresses on it, in one step, so the route no
    longer looks empty by the time the redirect lands back on the list
    page. Opening the new guide's Edit page from there shows the
    generated rows. `route_name` comes from the list page's own
    `?route=` (a hidden field in the button's form, not the URL, since
    there's no LeftRight pk to put in a URL yet)."""

    DRAFT_NAME = "Draft"

    def post(self, request, *args, **kwargs):
        route_name = request.POST.get("route_name", "").strip()
        list_url = reverse_lazy(self.url_name("lefts_rights")) + "?" + urlencode({"route": route_name})

        if not route_name:
            messages.error(request, "No route was specified.")
            return redirect(list_url)
        if not LeftRightAddressList.objects.filter(domain=self.domain, route_name=route_name).exists():
            messages.error(request, f'No saved addresses for route "{route_name}" — add some on the Addresses page first.')
            return redirect(list_url)
        if LeftRight.objects.filter(domain=self.domain, route_name=route_name).exists():
            # Already has at least one guide -- nothing to auto-create;
            # send them to the existing one instead of risking a
            # same-named duplicate (LeftRight's uniqueness is per
            # domain+route_name+name, not just route_name).
            messages.error(
                request,
                f'Route "{route_name}" already has a Left & Right — open it and use '
                f'"Generate from Addresses" there instead.',
            )
            return redirect(list_url)

        leftright = LeftRight.objects.create(domain=self.domain, route_name=route_name, name=self.DRAFT_NAME)
        row_count, address_count, error = _generate_rows_from_addresses(leftright, self.domain)
        if error:
            messages.error(request, error)
        else:
            messages.success(
                request,
                f'Created "{leftright.name}" for route "{route_name}" with {row_count} row(s) from '
                f"{address_count} addresses — review and adjust as needed.",
            )
        return redirect(list_url)


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
