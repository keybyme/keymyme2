from django.contrib import admin

from .models import Cuenta, Transaccion


@admin.register(Cuenta)
class CuentaAdmin(admin.ModelAdmin):
    list_display = ("name", "numero", "owner")
    list_filter = ("owner",)
    search_fields = ("name", "numero")


@admin.register(Transaccion)
class TransaccionAdmin(admin.ModelAdmin):
    list_display = ("concepto", "owner", "tipo", "monto", "cuenta", "fecha", "category", "metodo_captura")
    list_filter = ("tipo", "owner", "cuenta", "category", "metodo_captura")
    search_fields = ("concepto",)
    date_hierarchy = "fecha"
