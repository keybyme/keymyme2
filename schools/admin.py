from django.contrib import admin

from .models import AmMidPmEntry, Employee, LeftRight, Route, School


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
    list_display = ("route_number", "bus_number", "driver", "attendant")
    search_fields = ("route_number", "bus_number")


@admin.register(AmMidPmEntry)
class AmMidPmEntryAdmin(admin.ModelAdmin):
    list_display = ("route", "type", "seq", "time", "address", "next")
    list_filter = ("type",)
    search_fields = ("route__route_number", "address")


@admin.register(LeftRight)
class LeftRightAdmin(admin.ModelAdmin):
    list_display = ("route", "name")
    search_fields = ("route__route_number", "name")
