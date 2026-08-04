from django.contrib import admin

from .models import School


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "school_type", "address", "city", "zip_code")
    list_filter = ("school_type", "city")
    search_fields = ("name", "address", "city", "zip_code")
