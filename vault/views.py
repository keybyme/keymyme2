import base64
import io

import qrcode
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView, View

from .forms import CategoryForm, ContactForm, MediaFileForm, QRCodeForm, ReminderForm, UrlForm, VaultPasswordForm
from .mixins import OwnerCreateMixin, OwnerQuerysetMixin, SearchableListMixin, UserFormKwargsMixin
from .models import Category, Contact, MediaFile, Reminder, Url, VaultPassword


# ---------- Categories ----------

class CategoryListView(OwnerQuerysetMixin, ListView):
    model = Category
    template_name = "vault/category_list.html"
    context_object_name = "categories"
    paginate_by = 20


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

class ContactListView(SearchableListMixin, OwnerQuerysetMixin, ListView):
    model = Contact
    template_name = "vault/contact_list.html"
    context_object_name = "contacts"
    paginate_by = 20
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


# ---------- Vault Passwords ----------

class PasswordListView(SearchableListMixin, OwnerQuerysetMixin, ListView):
    model = VaultPassword
    template_name = "vault/password_list.html"
    context_object_name = "passwords"
    paginate_by = 20
    search_fields = ("site_name", "username", "site_url", "notes")
    # OJO: el template NUNCA debe imprimir get_password() aquí.
    # La lista solo debe mostrar site_name, username, site_url.


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
    Vista separada solo para revelar el password en texto plano.
    Al ser una vista aparte (no parte del list/detail normal), es más fácil
    auditar o restringir después (por ejemplo, exigir re-autenticación).
    """
    model = VaultPassword
    template_name = "vault/password_reveal.html"
    context_object_name = "password_obj"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["revealed_password"] = self.object.get_password()
        return context


# ---------- URLs ----------

class UrlListView(SearchableListMixin, OwnerQuerysetMixin, ListView):
    model = Url
    template_name = "vault/url_list.html"
    context_object_name = "urls"
    paginate_by = 20
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

class MediaFileListView(SearchableListMixin, OwnerQuerysetMixin, ListView):
    model = MediaFile
    template_name = "vault/mediafile_list.html"
    context_object_name = "files"
    paginate_by = 20
    search_fields = ("original_name",)


class MediaFilePhotoGalleryView(SearchableListMixin, OwnerQuerysetMixin, ListView):
    """Vista de galería: solo fotos, en cuadrícula, filtrable por categoría."""
    model = MediaFile
    template_name = "vault/mediafile_gallery.html"
    context_object_name = "files"
    paginate_by = 24
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
            form.add_error("file", "No tienes espacio suficiente en tu cuota de almacenamiento.")
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
                form.add_error("file", "No tienes espacio suficiente en tu cuota de almacenamiento.")
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

class ReminderListView(SearchableListMixin, OwnerQuerysetMixin, ListView):
    model = Reminder
    template_name = "vault/reminder_list.html"
    context_object_name = "reminders"
    paginate_by = 20
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
