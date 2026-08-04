from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from vault.mixins import ModuleAccessRequiredMixin

from .forms import SchoolForm
from .models import School

# Not owner-scoped on purpose: School is a shared reference catalog (MCPS
# public schools), not per-user vault data — see schools/models.py.


class SchoolListView(ModuleAccessRequiredMixin, ListView):
    model = School
    template_name = "schools/school_list.html"
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
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["school_types"] = School.SchoolType.choices
        context["selected_type"] = self.request.GET.get("type", "")
        context["query"] = self.request.GET.get("q", "")
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
