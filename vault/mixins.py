from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q

from .models import Category


class OwnerQuerysetMixin(LoginRequiredMixin):
    """
    Para ListView, DetailView, UpdateView, DeleteView.
    Garantiza que el usuario SOLO pueda ver/editar/borrar sus propios registros,
    sin importar qué ID pongan en la URL.
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


class OwnerCreateMixin(LoginRequiredMixin, UserFormKwargsMixin):
    """
    Para CreateView. Asigna automáticamente el owner = usuario actual,
    para que no se pueda crear un registro a nombre de otro usuario
    manipulando el formulario.
    """

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class SearchableListMixin:
    """
    Para ListView (junto con OwnerQuerysetMixin). Agrega filtros opcionales
    por categoría (?category=<id>) y texto libre (?q=) sobre los campos
    declarados en `search_fields`.
    """
    search_fields = ()

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
        context["categories"] = Category.objects.filter(owner=self.request.user)
        context["selected_category"] = self.request.GET.get("category", "")
        context["query"] = self.request.GET.get("q", "")
        return context
