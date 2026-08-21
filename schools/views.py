from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from vault.mixins import AjaxPartialTemplateMixin, ModuleAccessRequiredMixin

from .forms import AmMidPmEntryForm, EmployeeForm, LeftRightForm, RouteForm, SchoolForm
from .models import AmMidPmEntry, Employee, LeftRight, Route, School

# Not owner-scoped on purpose: School/Employee/Route/AmMidPmEntry/LeftRight
# are shared reference catalogs (MCPS public schools, MCPS transportation
# staff, MCPS bus route stops, MCPS AM/MID/PM stop times, MCPS left/right
# turn-by-turn guides), not per-user vault data — see schools/models.py.

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

    def get_success_url(self):
        return reverse_lazy("schools:lefts_rights") + "?" + urlencode({"route": self.object.route_name})


class LeftRightUpdateView(LeftRightRouteNamesDatalistMixin, ModuleAccessRequiredMixin, UpdateView):
    model = LeftRight
    form_class = LeftRightForm
    template_name = "schools/leftright_form.html"
    module_codename = "artifacts_mcps"

    def get_success_url(self):
        return reverse_lazy("schools:lefts_rights") + "?" + urlencode({"route": self.object.route_name})


class LeftRightDeleteView(ModuleAccessRequiredMixin, DeleteView):
    model = LeftRight
    template_name = "schools/leftright_confirm_delete.html"
    module_codename = "artifacts_mcps"

    def get_success_url(self):
        return reverse_lazy("schools:lefts_rights") + "?" + urlencode({"route": self.object.route_name})


class LeftRightDetailView(ModuleAccessRequiredMixin, DetailView):
    """What one LeftRight guide actually shows is still to be designed —
    this is a placeholder so the link from LeftsRightsView has somewhere
    to go."""
    model = LeftRight
    template_name = "schools/leftright_detail.html"
    context_object_name = "leftright"
    module_codename = "artifacts_mcps"
