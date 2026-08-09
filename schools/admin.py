from django.contrib import admin

from .models import Employee, Route, School


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


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("route_number", "bus_number", "route_type", "driver", "attendant", "stop_number", "seq", "address")
    list_filter = ("route_type",)
    search_fields = ("route_number", "bus_number", "address")
