from dataclasses import dataclass, field


@dataclass(frozen=True)
class EndpointSpec:
    """A single endpoint binding: its path plus any endpoint-specific expectation."""

    path: str
    expected_min: int = 0  # endpoint-specific floor (e.g. Europe -> 40); 0 = n/a


@dataclass(frozen=True)
class CountriesDescriptor:
    """What the REST Countries API exposes and what each endpoint expects.

    Paths and expectation values live here, not in test bodies. No schema/type
    checks belong in a descriptor — those are the validator's job.
    """

    region_path: str = "/region/{region}"
    name_path: str = "/name/{term}"
    all_path: str = "/all"
    all_fields: str = "name,population"
    region_fields: str = "name,region"  # shared projection for /region and the /all cross-reference catalog
    regions: tuple = ("Africa", "Americas", "Antarctic", "Asia", "Europe", "Oceania")
    europe_expected_min: int = 40  # this-endpoint expectation; NOT in YAML

    # Uninhabited territories REST Countries legitimately reports with population 0.
    # The /all population check exempts these (their common name). Brittle by nature:
    # verified against live API data and may need updating if the dataset changes.
    uninhabited_territories: frozenset = field(
        default=frozenset(
            {
                "Bouvet Island",
                "British Indian Ocean Territory",
                "Heard Island and McDonald Islands",
                "South Georgia",
                "United States Minor Outlying Islands",
            }
        )
    )

    def endpoint(self, key):
        if key == "europe_region":
            return EndpointSpec(
                self.region_path.format(region="europe"), self.europe_expected_min
            )
        if key == "all_population":
            return EndpointSpec(self.all_path)
        raise KeyError(key)

    def name_lookup(self, term):
        """Build the /name/<term> path for a search term."""
        return self.name_path.format(term=term)

    def region_lookup(self, region):
        """Build the /region/<region> path (the API is case-insensitive here)."""
        return self.region_path.format(region=region)

    def all_params(self):
        return {"fields": self.all_fields}

    def region_params(self):
        return {"fields": self.region_fields}
