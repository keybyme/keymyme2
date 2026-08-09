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
    phone = models.CharField(
        max_length=20, blank=True, verbose_name="Phone",
        help_text="Optional — some rosters (e.g. bus assignment sheets) list drivers without a phone number.",
    )
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
    """Reference catalog of MCPS bus routes: route number/bus number plus the
    driver and attendant assigned to it. Same shared-reference pattern as
    School/Employee — not owned by any user, just gated behind the
    artifacts_mcps Module.

    Originally also carried route type, stop #, seq, and address, but those
    turned out to belong to a different table entirely (mixed up when this
    model was designed) and were removed."""

    route_number = models.CharField(max_length=30, verbose_name="Route number")
    bus_number = models.CharField(max_length=20, blank=True, verbose_name="Bus #")
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

    class Meta:
        ordering = ["route_number"]
        verbose_name = "Route"
        verbose_name_plural = "Routes"

    def __str__(self):
        return self.route_number


class AmMidPmEntry(models.Model):
    """Reference catalog of MCPS AM/MID/PM stop times per route: for a given
    Route, the sequence of stops (Seq #) run at a given time of day (Type),
    each with a Time, an Address, and the Time the bus needs to leave for the
    Next stop. Same shared-reference pattern as School/Employee/Route — not
    owned by any user, just gated behind the artifacts_mcps Module.
    """

    class RunType(models.TextChoices):
        AM = "AM", "AM"
        MID = "MID", "MID"
        PM = "PM", "PM"

    route = models.ForeignKey(
        Route, on_delete=models.PROTECT, related_name="am_mid_pm_entries",
        verbose_name="Route",
    )
    type = models.CharField(max_length=3, choices=RunType.choices, verbose_name="Type")
    seq = models.PositiveIntegerField(verbose_name="Seq #")
    time = models.TimeField(verbose_name="Time")
    address = models.CharField(max_length=255, verbose_name="Address")
    next = models.TimeField(
        null=True, blank=True, verbose_name="Next",
        help_text="Minutes and seconds until the next stop (MM:SS), if applicable.",
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Geocoded from address by the MCPS Lefts & Rights view the first time it's opened; cached here to avoid re-geocoding on every visit.",
    )
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["route__route_number", "type", "seq"]
        verbose_name = "AM-MID-PM entry"
        verbose_name_plural = "AM-MID-PM entries"

    def __str__(self):
        return f"{self.route.route_number} {self.type} #{self.seq}"

    def save(self, *args, **kwargs):
        # Invalidate the cached geocode when the address changes, so the
        # Lefts & Rights view re-geocodes instead of routing to the old
        # location. Skipped when the caller is *only* writing
        # latitude/longitude (that view itself caching a fresh geocode —
        # nothing to invalidate there). Same pattern as vault.RouteStop.save().
        update_fields = kwargs.get("update_fields")
        geocode_only = update_fields is not None and set(update_fields) <= {"latitude", "longitude"}
        if not geocode_only and self.pk:
            old_address = AmMidPmEntry.objects.filter(pk=self.pk).values_list("address", flat=True).first()
            if old_address is not None and old_address != self.address:
                self.latitude = None
                self.longitude = None
        super().save(*args, **kwargs)
