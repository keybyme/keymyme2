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

    class Meta:
        ordering = ["route__route_number", "type", "seq"]
        verbose_name = "AM-MID-PM entry"
        verbose_name_plural = "AM-MID-PM entries"

    def __str__(self):
        return f"{self.route.route_number} {self.type} #{self.seq}"


class LeftRight(models.Model):
    """A named, driver-facing left/right turn-by-turn guide for one route.
    A route can have several of these (e.g. different variants or times of
    day), each identified by its own name — see LeftsRightsView, where
    picking a route lists its LeftRight guides as links. What each guide
    actually contains (the turn-by-turn steps) is added separately; this
    model is just the named, per-route catalog entry for now.

    `route_name` is a free-text label scoped to this module only —
    deliberately NOT a FK to Route (the MCPS bus route catalog used by
    AmMidPmEntry etc.): a LeftRight's route doesn't need a matching MCPS
    Route to already exist.

    Same shared-reference pattern as School/Employee/Route/AmMidPmEntry —
    not owned by any user. Gated behind BOTH the artifacts_mcps Module (like
    the rest of this app) and the newer 'transportation' Module — see
    schools/views.py and menus/migrations/0012_seed_transportation_module.py.
    MCPS itself isn't being retired yet ("eventually", not now), so this
    stays reachable exactly as it always was from there, with Transportation
    as an additional path rather than a replacement.
    """

    route_name = models.CharField(max_length=100, verbose_name="Route")
    name = models.CharField(max_length=100, verbose_name="Name")

    class Meta:
        ordering = ["route_name", "name"]
        verbose_name = "Left & Right"
        verbose_name_plural = "Lefts & Rights"
        constraints = [
            models.UniqueConstraint(fields=["route_name", "name"], name="unique_leftright_name_per_route"),
        ]

    def __str__(self):
        return f"{self.route_name} — {self.name}"


class LeftRightRow(models.Model):
    """One row of freeform content in a LeftRight guide — the driver-facing
    cheat sheet (LeftRightDetailView) is built entirely from these, in
    `order`. LeftRightCreateView seeds every new LeftRight with four blank
    rows (two TITLE, one BOLD, one NORMAL) as a starting scaffold; the Edit
    page's "Insertar fila" / "Insertar vinculo" buttons add more (NORMAL /
    LINK respectively) on top of that.

    `text` holds the row's text for TITLE/BOLD/NORMAL rows, and doubles as
    the leading text on a LINK row (three fields: `text` before, `address`
    in the middle, `text_after` trailing). `address` is a plain address —
    not a URL the user pastes in — LeftRightDetailView turns it into a
    driving-directions link at render time
    (maps.apple.com/?saddr=Current+Location&daddr=... -- see
    LeftRightDetailView's link markup for why `saddr` is that literal
    keyword rather than a lat/lng or omitted), so clicking it opens Apple
    Maps GPS navigation to that address from wherever the driver actually
    is when they tap it.
    """

    class RowType(models.TextChoices):
        TITLE = "title", "Title (large, bold)"
        BOLD = "bold", "Bold"
        NORMAL = "normal", "Normal"
        LINK = "link", "Link"

    leftright = models.ForeignKey(LeftRight, on_delete=models.CASCADE, related_name="rows")
    order = models.PositiveIntegerField(default=0)
    row_type = models.CharField(max_length=10, choices=RowType.choices, default=RowType.NORMAL, verbose_name="Type")
    text = models.CharField(max_length=255, blank=True, verbose_name="Text")
    address = models.CharField(max_length=255, blank=True, verbose_name="Address")
    text_after = models.CharField(max_length=255, blank=True, verbose_name="Text after")

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = "Left & Right row"
        verbose_name_plural = "Left & Right rows"

    def __str__(self):
        return f"{self.leftright} — row {self.order} ({self.row_type})"


class DepotLink(models.Model):
    """One row in the "Depot" directory — a single page shared by every
    LeftRight (reached via the "Depot" button on LeftRightDetailView),
    not tied to any one route/guide. Renders as `<a href="{url}">{name}</a>`
    (name falls back to the raw url if left blank) — see DepotView /
    schools/depot.html, where editing shows both fields but printing shows
    only the rendered link."""

    order = models.PositiveIntegerField(default=0)
    url = models.CharField(max_length=500, verbose_name="Link URL")
    name = models.CharField(max_length=255, blank=True, verbose_name="Link text")

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = "Depot link"
        verbose_name_plural = "Depot links"

    def __str__(self):
        return self.name or self.url
