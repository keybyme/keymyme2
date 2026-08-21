from django.urls import path

from . import views

app_name = "schools"

urlpatterns = [
    path("", views.SchoolListView.as_view(), name="school_list"),
    path("new/", views.SchoolCreateView.as_view(), name="school_create"),
    path("<int:pk>/edit/", views.SchoolUpdateView.as_view(), name="school_update"),
    path("<int:pk>/delete/", views.SchoolDeleteView.as_view(), name="school_delete"),
    path("employees/", views.EmployeeListView.as_view(), name="employee_list"),
    path("employees/new/", views.EmployeeCreateView.as_view(), name="employee_create"),
    path("employees/<int:pk>/edit/", views.EmployeeUpdateView.as_view(), name="employee_update"),
    path("employees/<int:pk>/delete/", views.EmployeeDeleteView.as_view(), name="employee_delete"),
    path("routes/", views.RouteListView.as_view(), name="route_list"),
    path("routes/new/", views.RouteCreateView.as_view(), name="route_create"),
    path("routes/<int:pk>/edit/", views.RouteUpdateView.as_view(), name="route_update"),
    path("routes/<int:pk>/delete/", views.RouteDeleteView.as_view(), name="route_delete"),
    path("am-mid-pm/", views.AmMidPmEntryListView.as_view(), name="ammidpm_list"),
    path("am-mid-pm/new/", views.AmMidPmEntryCreateView.as_view(), name="ammidpm_create"),
    path("am-mid-pm/<int:pk>/edit/", views.AmMidPmEntryUpdateView.as_view(), name="ammidpm_update"),
    path("am-mid-pm/<int:pk>/delete/", views.AmMidPmEntryDeleteView.as_view(), name="ammidpm_delete"),
    path("lefts-rights/", views.LeftsRightsView.as_view(), name="lefts_rights"),
    path("lefts-rights/new/", views.LeftRightCreateView.as_view(), name="leftright_create"),
    path("lefts-rights/<int:pk>/", views.LeftRightDetailView.as_view(), name="leftright_detail"),
    path("lefts-rights/<int:pk>/edit/", views.LeftRightUpdateView.as_view(), name="leftright_update"),
    path("lefts-rights/<int:pk>/delete/", views.LeftRightDeleteView.as_view(), name="leftright_delete"),
]
