from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Category


class ModuleAccessRequiredMixin(LoginRequiredMixin):
    """
    Para cualquier CBV. Requiere que el usuario logueado tenga acceso al
    Module `module_codename` (vía uno de sus Roles activos, o automático
    para is_admin_principal) — ver CustomUser.has_module_access(). Dejar
    `module_codename = None` (default) para no exigir ningún módulo.

    `module_codename` también acepta una tupla/lista de codenames — el
    usuario pasa si tiene acceso a CUALQUIERA de ellos (OR, no AND). Usado
    por ejemplo en schools' Lefts & Rights/Depot, accesible tanto vía
    'artifacts_mcps' como vía 'transportation' mientras ambos módulos
    conviven (ver schools/views.py).
    """
    module_codename = None

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.module_codename is not None:
            codenames = (
                self.module_codename if isinstance(self.module_codename, (list, tuple))
                else (self.module_codename,)
            )
            if not any(request.user.has_module_access(codename) for codename in codenames):
                raise PermissionDenied("You don't have access to this section.")
        return super().dispatch(request, *args, **kwargs)


class OwnerQuerysetMixin(ModuleAccessRequiredMixin):
    """
    Para ListView, DetailView, UpdateView, DeleteView.
    Garantiza que el usuario SOLO pueda ver/editar/borrar sus propios registros,
    sin importar qué ID pongan en la URL. Setear `module_codename` en la vista
    para además exigir acceso a ese módulo (ver ModuleAccessRequiredMixin).
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(owner=self.request.user)


class UserFormKwargsMixin:
    """
    Para CreateView/UpdateView cuyo form acepta `user` (ej. para filtrar el
    queryset de 'category' a las del dueño). NO usar en DeleteView: en
    Django su form por defecto no acepta `user`.
    """

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class OwnerCreateMixin(ModuleAccessRequiredMixin, UserFormKwargsMixin):
    """
    Para CreateView. Asigna automáticamente el owner = usuario actual,
    para que no se pueda crear un registro a nombre de otro usuario
    manipulando el formulario. Setear `module_codename` en la vista para
    además exigir acceso a ese módulo (ver ModuleAccessRequiredMixin).
    """

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class AjaxPartialTemplateMixin:
    """
    Para ListView con búsqueda "en vivo" (ver _live_search.html: hace fetch
    con header X-Requested-With en vez de recargar la página). Sirve
    ajax_template_name (solo la tabla de resultados, sin el layout de
    base.html) cuando la request viene de ese fetch; si no, el template
    normal de la vista.
    """
    ajax_template_name = None

    def get_template_names(self):
        if self.ajax_template_name and self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return [self.ajax_template_name]
        return super().get_template_names()


class SearchableListMixin:
    """
    Para ListView (junto con OwnerQuerysetMixin). Agrega filtros opcionales
    por categoría (?category=<id>) y texto libre (?q=) sobre los campos
    declarados en `search_fields`.
    """
    search_fields = ()
    category_kind = Category.Kind.GENERAL

    def get_queryset(self):
        queryset = super().get_queryset()

        category_id = self.request.GET.get("category")
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        query = self.request.GET.get("q")
        if query and self.search_fields:
            text_filter = Q()
            for field in self.search_fields:
                text_filter |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(text_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(owner=self.request.user, kind=self.category_kind)
        context["selected_category"] = self.request.GET.get("category", "")
        context["query"] = self.request.GET.get("q", "")
        return context
