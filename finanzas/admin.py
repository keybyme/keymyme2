from django.contrib import admin

from .models import Cuenta, Deuda, Transaccion


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


@admin.register(Deuda)
class DeudaAdmin(admin.ModelAdmin):
    list_display = ("deuda", "owner", "tipo", "monto", "saldo", "cuenta", "credito", "dia", "flag")
    list_filter = ("tipo", "flag", "owner", "cuenta")
    search_fields = ("deuda",)
