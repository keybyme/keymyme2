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
    # MCPS's own Lefts & Rights / Depot -- domain left at its default
    # ("mcps"), exactly as this worked before Transportation existed.
    path("lefts-rights/", views.LeftsRightsView.as_view(), name="lefts_rights"),
    path("lefts-rights/routes/", views.LeftRightRouteListView.as_view(), name="leftright_route_list"),
    path("lefts-rights/routes/delete/", views.LeftRightRouteDeleteView.as_view(), name="leftright_route_delete"),
    path("lefts-rights/routes/rename/", views.LeftRightRouteRenameView.as_view(), name="leftright_route_rename"),
    path("lefts-rights/addresses/", views.LeftRightAddressListView.as_view(), name="leftright_addresses"),
    path("lefts-rights/addresses/delete/", views.LeftRightAddressListDeleteView.as_view(), name="leftright_address_list_delete"),
    path("lefts-rights/addresses/generate/", views.LeftRightCreateFromAddressesView.as_view(), name="leftright_create_from_addresses"),
    path("lefts-rights/addresses/sheet/", views.LeftRightSheetUploadView.as_view(), name="leftright_sheet_upload"),
    path("lefts-rights/addresses/sheet/<int:pk>/delete/", views.LeftRightSheetUploadDeleteView.as_view(), name="leftright_sheet_upload_delete"),
    path("lefts-rights/new/", views.LeftRightCreateView.as_view(), name="leftright_create"),
    path("lefts-rights/depot/", views.DepotView.as_view(), name="depot"),
    path("lefts-rights/depot/list/", views.DepotListView.as_view(), name="depot_list"),
    path("lefts-rights/depot/upload/", views.DepotUploadView.as_view(), name="depot_upload"),
    path("lefts-rights/<int:pk>/", views.LeftRightDetailView.as_view(), name="leftright_detail"),
    path("lefts-rights/<int:pk>/share/", views.LeftRightShareDetailView.as_view(), name="leftright_share"),
    path("lefts-rights/<int:pk>/edit/", views.LeftRightUpdateView.as_view(), name="leftright_update"),
    path("lefts-rights/<int:pk>/delete/", views.LeftRightDeleteView.as_view(), name="leftright_delete"),
    path("lefts-rights/<int:pk>/rows/save/", views.LeftRightRowSaveView.as_view(), name="leftright_row_save"),
    path("lefts-rights/<int:pk>/rows/generate/", views.LeftRightGenerateRowsView.as_view(), name="leftright_generate_rows"),
    path("lefts-rights/<int:pk>/rows/generate-from-sheet/", views.LeftRightGenerateRowsFromSheetView.as_view(), name="leftright_generate_rows_from_sheet"),

    # Transportation's own Lefts & Rights / Depot -- same view classes,
    # registered again with domain="transportation" (see
    # LeftsRightsDomainMixin in views.py): fully independent data from
    # MCPS's above, never mixed. depot_upload has no domain-specific data
    # of its own, so it's shared rather than duplicated -- see
    # DepotUploadView.
    path("transportation/lefts-rights/", views.LeftsRightsView.as_view(domain="transportation"), name="transportation_lefts_rights"),
    path("transportation/lefts-rights/routes/", views.LeftRightRouteListView.as_view(domain="transportation"), name="transportation_leftright_route_list"),
    path("transportation/lefts-rights/routes/delete/", views.LeftRightRouteDeleteView.as_view(domain="transportation"), name="transportation_leftright_route_delete"),
    path("transportation/lefts-rights/routes/rename/", views.LeftRightRouteRenameView.as_view(domain="transportation"), name="transportation_leftright_route_rename"),
    path("transportation/lefts-rights/addresses/", views.LeftRightAddressListView.as_view(domain="transportation"), name="transportation_leftright_addresses"),
    path("transportation/lefts-rights/addresses/delete/", views.LeftRightAddressListDeleteView.as_view(domain="transportation"), name="transportation_leftright_address_list_delete"),
    path("transportation/lefts-rights/addresses/generate/", views.LeftRightCreateFromAddressesView.as_view(domain="transportation"), name="transportation_leftright_create_from_addresses"),
    path("transportation/lefts-rights/addresses/sheet/", views.LeftRightSheetUploadView.as_view(domain="transportation"), name="transportation_leftright_sheet_upload"),
    path("transportation/lefts-rights/addresses/sheet/<int:pk>/delete/", views.LeftRightSheetUploadDeleteView.as_view(domain="transportation"), name="transportation_leftright_sheet_upload_delete"),
    path("transportation/lefts-rights/new/", views.LeftRightCreateView.as_view(domain="transportation"), name="transportation_leftright_create"),
    path("transportation/lefts-rights/depot/", views.DepotView.as_view(domain="transportation"), name="transportation_depot"),
    path("transportation/lefts-rights/depot/list/", views.DepotListView.as_view(domain="transportation"), name="transportation_depot_list"),
    path("transportation/lefts-rights/<int:pk>/", views.LeftRightDetailView.as_view(domain="transportation"), name="transportation_leftright_detail"),
    path("transportation/lefts-rights/<int:pk>/edit/", views.LeftRightUpdateView.as_view(domain="transportation"), name="transportation_leftright_update"),
    path("transportation/lefts-rights/<int:pk>/delete/", views.LeftRightDeleteView.as_view(domain="transportation"), name="transportation_leftright_delete"),
    path("transportation/lefts-rights/<int:pk>/rows/save/", views.LeftRightRowSaveView.as_view(domain="transportation"), name="transportation_leftright_row_save"),
    path("transportation/lefts-rights/<int:pk>/rows/generate/", views.LeftRightGenerateRowsView.as_view(domain="transportation"), name="transportation_leftright_generate_rows"),
    path("transportation/lefts-rights/<int:pk>/rows/generate-from-sheet/", views.LeftRightGenerateRowsFromSheetView.as_view(domain="transportation"), name="transportation_leftright_generate_rows_from_sheet"),
]
