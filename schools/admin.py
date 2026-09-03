from django.contrib import admin

from .models import AmMidPmEntry, DepotLink, Employee, LeftRight, LeftRightAddressList, LeftRightRow, Route, School


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


class LeftRightRowInline(admin.TabularInline):
    model = LeftRightRow
    extra = 0


@admin.register(LeftRight)
class LeftRightAdmin(admin.ModelAdmin):
    list_display = ("route_name", "name")
    search_fields = ("route_name", "name")
    inlines = [LeftRightRowInline]


@admin.register(DepotLink)
class DepotLinkAdmin(admin.ModelAdmin):
    list_display = ("order", "name", "url")
    search_fields = ("name", "url")


@admin.register(LeftRightAddressList)
class LeftRightAddressListAdmin(admin.ModelAdmin):
    list_display = ("route_name", "domain", "updated_at")
    list_filter = ("domain",)
    search_fields = ("route_name", "addresses")
