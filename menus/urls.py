from django.urls import path

from . import views

app_name = "menus"

urlpatterns = [
    path("access/", views.UserAccessListView.as_view(), name="user_access_list"),
    path("access/<int:pk>/", views.UserAccessDetailView.as_view(), name="user_access_detail"),
]
