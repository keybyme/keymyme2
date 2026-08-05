from django.contrib import admin

from .models import Employee, School


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "school_type", "address", "city", "zip_code")
    list_filter = ("school_type", "city")
    search_fields = ("name", "address", "city", "zip_code")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "position")
    list_filter = ("position",)
    search_fields = ("name", "phone")
