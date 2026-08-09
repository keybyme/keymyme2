from django.db import models


class School(models.Model):
    """Reference catalog of Montgomery County, MD public schools (MCPS).

    Not owned by any user — this is shared reference data, unlike vault's per-user
    models. Populated/refreshed from Montgomery County's Open Data Portal via the
    `sync_mcps_schools` management command (see schools/management/commands/).
    """

    class SchoolType(models.TextChoices):
        ELEMENTARY = "ELEMENTARY", "Elementary School"
        MIDDLE = "MIDDLE", "Middle School"
        HIGH = "HIGH", "High School"

    name = models.CharField(max_length=200, unique=True, verbose_name="School name")
    school_type = models.CharField(
        max_length=20, choices=SchoolType.choices, verbose_name="School type"
    )
    address = models.CharField(max_length=255, verbose_name="Address")
    city = models.CharField(max_length=100, blank=True, verbose_name="City")
    zip_code = models.CharField(max_length=10, blank=True, verbose_name="Zip code")

    class Meta:
        ordering = ["school_type", "name"]
        verbose_name = "School"
        verbose_name_plural = "Schools"

    def __str__(self):
        return self.name

    @property
    def full_address(self):
        """Address + city/zip, for the Google Maps link — plain `address` alone
        is often ambiguous (e.g. "6400 Rock Spring Dr" exists in many towns)."""
        parts = [self.address]
        if self.city:
            parts.append(self.city)
        if self.zip_code:
            parts.append(f"MD {self.zip_code}")
        return ", ".join(parts)


class Employee(models.Model):
    """Roster of MCPS transportation staff (drivers, attendants, etc.).

    Same shared-reference pattern as `School` — not owned by any user, just
    gated behind the `artifacts_mcps` Module like the rest of this app.
    """

    class Position(models.IntegerChoices):
        DRIVER = 1, "Driver"
        ATTENDANT = 2, "Attendant"
        BRS = 3, "BRS"
        OTHERS = 4, "Others"

    name = models.CharField(max_length=200, verbose_name="Name")
    phone = models.CharField(max_length=20, verbose_name="Phone")
    position = models.PositiveSmallIntegerField(
        choices=Position.choices, verbose_name="Position"
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Employee"
        verbose_name_plural = "Employees"

    def __str__(self):
        return self.name


class Route(models.Model):
    """Reference catalog of MCPS bus route stops: route number/type plus the
    driver, attendant, and each stop along it. Same shared-reference pattern
    as School/Employee — not owned by any user, just gated behind the
    artifacts_mcps Module. One row per stop (route_number+route_type group
    the stops that make up a single route), mirroring vault.RouteStop's
    field naming, but this catalog is admin-editable reference data rather
    than a per-driver runtime template."""

    class RouteType(models.TextChoices):
        AM = "AM", "AM"
        MID = "MID", "Mid Day"
        PM = "PM", "PM"

    route_number = models.CharField(max_length=30, verbose_name="Route number")
    bus_number = models.CharField(max_length=20, blank=True, verbose_name="Bus #")
    route_type = models.CharField(
        max_length=10, choices=RouteType.choices, verbose_name="Route type"
    )
    driver = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="driver_routes", limit_choices_to={"position": Employee.Position.DRIVER},
        verbose_name="Driver",
    )
    attendant = models.ForeignKey(
        Employee, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="attendant_routes", limit_choices_to={"position": Employee.Position.ATTENDANT},
        verbose_name="Attendant",
    )
    stop_number = models.PositiveIntegerField(null=True, blank=True, verbose_name="Stop #")
    seq = models.PositiveIntegerField(default=10, verbose_name="Seq")
    address = models.CharField(max_length=255, verbose_name="Address")

    class Meta:
        ordering = ["route_number", "route_type", "seq"]
        verbose_name = "Route stop"
        verbose_name_plural = "Routes"

    def __str__(self):
        return f"{self.route_number} {self.route_type} stop #{self.seq}"
