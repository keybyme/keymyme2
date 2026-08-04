from django.urls import path

from . import views

app_name = "schools"

urlpatterns = [
    path("", views.SchoolListView.as_view(), name="school_list"),
    path("new/", views.SchoolCreateView.as_view(), name="school_create"),
    path("<int:pk>/edit/", views.SchoolUpdateView.as_view(), name="school_update"),
    path("<int:pk>/delete/", views.SchoolDeleteView.as_view(), name="school_delete"),
]
