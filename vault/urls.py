from django.urls import path

from . import views

app_name = "vault"

urlpatterns = [
    # Categories
    path("categories/", views.CategoryListView.as_view(), name="category_list"),
    path("categories/new/", views.CategoryCreateView.as_view(), name="category_create"),
    path("categories/<int:pk>/edit/", views.CategoryUpdateView.as_view(), name="category_update"),
    path("categories/<int:pk>/delete/", views.CategoryDeleteView.as_view(), name="category_delete"),

    # Contacts
    path("contacts/", views.ContactListView.as_view(), name="contact_list"),
    path("contacts/new/", views.ContactCreateView.as_view(), name="contact_create"),
    path("contacts/import/", views.ContactImportView.as_view(), name="contact_import"),
    path("contacts/<int:pk>/edit/", views.ContactUpdateView.as_view(), name="contact_update"),
    path("contacts/<int:pk>/delete/", views.ContactDeleteView.as_view(), name="contact_delete"),

    # Passwords
    path("passwords/", views.PasswordListView.as_view(), name="password_list"),
    path("passwords/new/", views.PasswordCreateView.as_view(), name="password_create"),
    path("passwords/<int:pk>/edit/", views.PasswordUpdateView.as_view(), name="password_update"),
    path("passwords/<int:pk>/delete/", views.PasswordDeleteView.as_view(), name="password_delete"),
    path("passwords/<int:pk>/reveal/", views.PasswordRevealView.as_view(), name="password_reveal"),
    path("passwords/<int:pk>/reveal.json", views.PasswordRevealJSONView.as_view(), name="password_reveal_json"),

    # URLs
    path("urls/", views.UrlListView.as_view(), name="url_list"),
    path("urls/new/", views.UrlCreateView.as_view(), name="url_create"),
    path("urls/<int:pk>/edit/", views.UrlUpdateView.as_view(), name="url_update"),
    path("urls/<int:pk>/delete/", views.UrlDeleteView.as_view(), name="url_delete"),

    # Media files
    path("files/", views.MediaFileListView.as_view(), name="mediafile_list"),
    path("files/gallery/", views.MediaFilePhotoGalleryView.as_view(), name="mediafile_gallery"),
    path("files/new/", views.MediaFileCreateView.as_view(), name="mediafile_create"),
    path("files/<int:pk>/edit/", views.MediaFileUpdateView.as_view(), name="mediafile_update"),
    path("files/<int:pk>/delete/", views.MediaFileDeleteView.as_view(), name="mediafile_delete"),

    # Reminders
    path("reminders/", views.ReminderListView.as_view(), name="reminder_list"),
    path("reminders/new/", views.ReminderCreateView.as_view(), name="reminder_create"),
    path("reminders/<int:pk>/edit/", views.ReminderUpdateView.as_view(), name="reminder_update"),
    path("reminders/<int:pk>/delete/", views.ReminderDeleteView.as_view(), name="reminder_delete"),

    # QR Codes
    path("qrcode/", views.QRCodeGeneratorView.as_view(), name="qrcode_generate"),

    # I am here
    path("im-here/", views.ImHereView.as_view(), name="im_here"),
    path("im-here/send/", views.ImHereSendLocationView.as_view(), name="im_here_send"),
    path("im-here/save-route/", views.SaveRouteView.as_view(), name="im_here_save_route"),
    path("im-here/load-route/", views.LoadRouteView.as_view(), name="im_here_load_route"),
    path("im-here/checkins/<int:pk>/edit/", views.LocationCheckInUpdateView.as_view(), name="location_checkin_update"),
    path("im-here/checkins/<int:pk>/delete/", views.LocationCheckInDeleteView.as_view(), name="location_checkin_delete"),
    path("im-here/checkins/<int:pk>/here/", views.LocationCheckInHereView.as_view(), name="location_checkin_here"),
    path("im-here/history/", views.LocationCheckInHistoryView.as_view(), name="im_here_history"),
    path("im-here/administrator/", views.AdministratorView.as_view(), name="im_here_administrator"),
    path("im-here/administrator/routes/", views.AdminRoutesView.as_view(), name="im_here_admin_routes"),

    # Cron externo (ver config/settings.py CRON_SECRET)
    path("cron/send-reminders/", views.SendDueRemindersCronView.as_view(), name="cron_send_reminders"),
]
