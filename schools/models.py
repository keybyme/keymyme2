from datetime import timedelta

from django.core.validators import FileExtensionValidator
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
    not owned by any user. Reachable from both the MCPS module
    (artifacts_mcps) and the newer Transportation module, but NOT the same
    data either way — `domain` splits the rows into two fully independent
    sets, one per module, so nothing created/edited/deleted under one ever
    shows up under the other. See LeftsRightsDomainMixin in schools/views.py
    (which view flavor sets `domain`) and menus/migrations/
    0012_seed_transportation_module.py (how Transportation itself was
    added). MCPS itself isn't being retired yet ("eventually", not now) —
    this is a parallel, separate space, not a takeover of MCPS's existing
    guides.
    """

    class Domain(models.TextChoices):
        MCPS = "mcps", "MCPS"
        TRANSPORTATION = "transportation", "Transportation"

    domain = models.CharField(
        max_length=20, choices=Domain.choices, default=Domain.MCPS, verbose_name="Domain",
        help_text=(
            "Which module owns this guide — MCPS and Transportation each only ever see their "
            "own. Existing rows default to MCPS, since that's the only module this ever lived "
            "under before Transportation existed."
        ),
    )
    route_name = models.CharField(max_length=100, verbose_name="Route")
    name = models.CharField(max_length=100, verbose_name="Name")

    class Meta:
        ordering = ["route_name", "name"]
        verbose_name = "Left & Right"
        verbose_name_plural = "Lefts & Rights"
        constraints = [
            models.UniqueConstraint(fields=["domain", "route_name", "name"], name="unique_leftright_name_per_route_per_domain"),
        ]

    def __str__(self):
        return f"{self.route_name} — {self.name}"


class LeftRightAddressList(models.Model):
    """A draft list of addresses for one route (domain + route_name),
    entered on the "Addresses" page (LeftRightAddressListView) so
    LeftRightGenerateRowsView can turn them into a first-draft set of
    turn-by-turn LeftRightRow rows later, on the Edit page for whichever
    LeftRight actually gets created for that route — see schools/views.py.
    There's no FK to LeftRight: the two are associated purely by matching
    `route_name` (+ `domain`), the same free-text convention
    LeftRight.route_name already uses, since an address list is often
    entered before its LeftRight even exists, and one route can still
    have several LeftRight guides.

    Saving always fully replaces whatever was saved before for that
    (domain, route_name) — same "always overrides" pattern as Rutas' Save
    Route — rather than keeping any history.

    `addresses` is one address per line, deliberately not split into a
    child table: order is everything (this becomes stop 1, 2, 3... in
    that order) and it's never queried/filtered per-line, just read back
    whole and split in Python (see address_lines)."""

    domain = models.CharField(
        max_length=20, choices=LeftRight.Domain.choices, default=LeftRight.Domain.MCPS, verbose_name="Domain",
        help_text="Which module this address list belongs to — see LeftRight.domain.",
    )
    route_name = models.CharField(max_length=100, verbose_name="Route")
    addresses = models.TextField(
        verbose_name="Addresses",
        help_text="One address per line, 4 to 15 addresses, in the order they should be visited.",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Last updated")

    class Meta:
        ordering = ["route_name"]
        verbose_name = "Address list"
        verbose_name_plural = "Address lists"
        constraints = [
            models.UniqueConstraint(fields=["domain", "route_name"], name="unique_address_list_per_route_per_domain"),
        ]

    def __str__(self):
        return f"{self.route_name} ({self.get_domain_display()})"

    @property
    def address_lines(self):
        return [line.strip() for line in self.addresses.splitlines() if line.strip()]


# Whitelist, not blacklist -- same reasoning as vault's ALLOWED_MEDIA_
# EXTENSIONS. HEIC/HEIF need SchoolsConfig.ready() to have registered
# pillow-heif's opener (iPhones save photos in this format by default);
# PDF/DOCX are extracted as text directly (or OCR'd per page for a
# scanned/image-only PDF) rather than via Tesseract -- see
# schools/leftright_sheet_text.py.
LEFTRIGHT_SHEET_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "tif", "heic", "heif"]
LEFTRIGHT_SHEET_DOCUMENT_EXTENSIONS = ["pdf", "docx"]
LEFTRIGHT_SHEET_ALLOWED_EXTENSIONS = LEFTRIGHT_SHEET_IMAGE_EXTENSIONS + LEFTRIGHT_SHEET_DOCUMENT_EXTENSIONS

# Uploads are only ever a scratch input for drafting LeftRightRow rows
# (see LeftRightGenerateRowsFromSheetView) -- not meant to be kept around
# -- so the `purge_old_leftright_sheet_uploads` management command
# (crontab, daily) deletes them this long after upload. Shared with
# LeftRightSheetUpload.expires_at so the "Uploaded documents" listing
# (leftright_addresses.html) shows the same date the cron job will
# actually act on.
LEFTRIGHT_SHEET_RETENTION_DAYS = 3


class LeftRightSheetUpload(models.Model):
    """One page of an already-existing Left & Right turn-by-turn sheet
    (e.g. a paper guide already in use for a route) -- a photo, or a PDF/
    DOCX export of it -- uploaded on the "Addresses" page
    (LeftRightAddressListView) and its text extracted (schools/
    leftright_sheet_text.py: OCR via vault.route_sheet_ocr's Tesseract
    setup for images, direct text extraction for PDF/DOCX) into
    `raw_text` so LeftRightGenerateRowsFromSheetView can turn it into a
    first-draft set of LeftRightRow rows later, on the Edit page for
    whichever LeftRight actually gets created for that route -- same
    "enter it here, generate it there" split as LeftRightAddressList /
    LeftRightGenerateRowsView, and there's no FK to LeftRight for the same
    reason: a sheet is often uploaded before its LeftRight even exists.

    UNLIKE LeftRightAddressList, uploading here always ADDS another file
    rather than replacing what's there -- a long route's paper sheet often
    doesn't fit on a single page, so a route can have several of these,
    ordered by `order` (upload order, spaced by tens like
    LeftRightRow.order). LeftRightGenerateRowsFromSheetView reads every
    upload for a route in that order and concatenates their extracted
    text before generating rows. Delete one at a time (see
    LeftRightSheetUploadDeleteView) rather than "replace" if a page needs
    redoing."""

    domain = models.CharField(
        max_length=20, choices=LeftRight.Domain.choices, default=LeftRight.Domain.MCPS, verbose_name="Domain",
        help_text="Which module this upload belongs to — see LeftRight.domain.",
    )
    route_name = models.CharField(max_length=100, verbose_name="Route")
    order = models.PositiveIntegerField(default=0, verbose_name="Order")
    file = models.FileField(
        upload_to="leftright_sheets/%Y/%m/",
        validators=[FileExtensionValidator(allowed_extensions=LEFTRIGHT_SHEET_ALLOWED_EXTENSIONS)],
        verbose_name="File",
        help_text="A photo, PDF, or DOCX of one page of the sheet.",
    )
    raw_text = models.TextField(blank=True, help_text="Raw extracted text, kept for troubleshooting a bad parse.")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Uploaded")

    class Meta:
        ordering = ["route_name", "order", "id"]
        verbose_name = "Left & Right sheet upload"
        verbose_name_plural = "Left & Right sheet uploads"

    def __str__(self):
        return f"{self.route_name} ({self.get_domain_display()}) — page {self.order}"

    @property
    def is_image(self):
        """Whether `file` is a photo (vs. a PDF/DOCX) -- drives how the
        "Addresses" page and the delete-confirm page render it (an <img>
        thumbnail vs. a paper-clip icon + filename)."""
        extension = self.file.name.rsplit(".", 1)[-1].lower() if self.file and "." in self.file.name else ""
        return extension in LEFTRIGHT_SHEET_IMAGE_EXTENSIONS

    @property
    def filename(self):
        """Just the original-ish basename (upload_to nests it under
        leftright_sheets/<year>/<month>/), for display next to the
        paper-clip icon on a non-image upload."""
        return self.file.name.rsplit("/", 1)[-1] if self.file else ""

    @property
    def expires_at(self):
        """When `purge_old_leftright_sheet_uploads` (crontab, daily) will
        delete this upload -- see LEFTRIGHT_SHEET_RETENTION_DAYS. Purely
        informational here (the "Uploaded documents" listing shows it);
        the command itself recomputes its own cutoff rather than reading
        this per-row."""
        return self.uploaded_at + timedelta(days=LEFTRIGHT_SHEET_RETENTION_DAYS)

    def delete(self, *args, **kwargs):
        # Django doesn't delete the underlying file on model delete --
        # same pattern as vault.RouteSheetUpload.delete().
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)


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
    """One row in the "Depot" directory — a page shared by every LeftRight
    IN THE SAME DOMAIN (reached via the "Depot" button on
    LeftRightDetailView), not tied to any one route/guide. Renders as
    `<a href="{url}">{name}</a>` (name falls back to the raw url if left
    blank) — see DepotView / schools/depot.html, where editing shows both
    fields but printing shows only the rendered link.

    `domain` splits this the same way as LeftRight.domain — MCPS's Depot
    and Transportation's Depot are two independent lists, never mixed."""

    domain = models.CharField(
        max_length=20, choices=LeftRight.Domain.choices, default=LeftRight.Domain.MCPS, verbose_name="Domain",
        help_text="Which module's Depot list this link belongs to — see LeftRight.domain.",
    )
    order = models.PositiveIntegerField(default=0)
    url = models.CharField(max_length=500, verbose_name="Link URL")
    name = models.CharField(max_length=255, blank=True, verbose_name="Link text")

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = "Depot link"
        verbose_name_plural = "Depot links"

    def __str__(self):
        return self.name or self.url
