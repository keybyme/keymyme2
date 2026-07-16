from django.urls import path

from . import views

app_name = "finanzas"

urlpatterns = [
    # Cuentas
    path("cuentas/", views.CuentaListView.as_view(), name="cuenta_list"),
    path("cuentas/new/", views.CuentaCreateView.as_view(), name="cuenta_create"),
    path("cuentas/<int:pk>/edit/", views.CuentaUpdateView.as_view(), name="cuenta_update"),
    path("cuentas/<int:pk>/delete/", views.CuentaDeleteView.as_view(), name="cuenta_delete"),

    # Transacciones
    path("transacciones/", views.TransaccionListView.as_view(), name="transaccion_list"),
    path("transacciones/new/", views.TransaccionCreateView.as_view(), name="transaccion_create"),
    path("transacciones/<int:pk>/edit/", views.TransaccionUpdateView.as_view(), name="transaccion_update"),
    path("transacciones/<int:pk>/delete/", views.TransaccionDeleteView.as_view(), name="transaccion_delete"),
]
