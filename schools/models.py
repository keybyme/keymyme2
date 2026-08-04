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
