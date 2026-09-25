"""Multi-university open-science snapshots (GitHub Pages tenants)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path


ROOT_SITE_BASE_URL = "https://xiaoouwang.github.io/hal-unica"


@dataclass(frozen=True)
class University:
    """One institutional HAL collection + its static snapshot site."""

    id: str
    collection: str
    short_name: str
    display_name: str
    site_name: str
    tagline: str
    org_url: str
    # Path under the Pages root ("" for UniCA at docs/, "ube" for docs/ube/).
    site_path: str
    logo: str | None
    census_dir: Path
    links_path: Path
    harvest_path: Path
    site_dir: Path
    stats_fallback: Path
    log_path: Path
    # DataCite institutional dataset census (optional — empty = skip).
    ror_ids: tuple[str, ...] = ()
    affiliation_names: tuple[str, ...] = ()

    @property
    def site_base_url(self) -> str:
        if not self.site_path:
            return ROOT_SITE_BASE_URL
        return f"{ROOT_SITE_BASE_URL}/{self.site_path.strip('/')}"

    @property
    def collection_url(self) -> str:
        return f"https://hal.science/{self.collection}"

    @property
    def absolute_home_url(self) -> str:
        return f"{self.site_base_url}/"

    @property
    def has_datacite_census(self) -> bool:
        return bool(self.ror_ids or self.affiliation_names)

    def snapshot_href_from(self, viewer: University) -> str:
        """Relative link from ``viewer``'s site root to this university's index."""
        if self.id == viewer.id:
            return "./index.html"
        if not self.site_path:
            # Target is Pages root; viewer is nested.
            depth = len([p for p in viewer.site_path.split("/") if p])
            return "../" * depth + "index.html"
        if not viewer.site_path:
            return f"./{self.site_path}/index.html"
        # Both nested under Pages root (siblings).
        depth = len([p for p in viewer.site_path.split("/") if p])
        return "../" * depth + f"{self.site_path}/index.html"


UNICA = University(
    id="unica",
    collection="UNIV-COTEDAZUR",
    short_name="UniCA",
    display_name="Université Côte d’Azur",
    site_name="HAL-UniCA",
    tagline=(
        "Open-science monitoring for Université Côte d’Azur on HAL: "
        "linked datasets, repositories, software, and correction queues."
    ),
    org_url="https://univ-cotedazur.fr/",
    site_path="",
    logo=None,  # text chip until a logo file is added under static/universities/
    census_dir=Path("data/census"),
    links_path=Path("data/unica_data_repo_links.jsonl"),
    harvest_path=Path("data/unica_hal_metadata.jsonl"),
    site_dir=Path("docs"),
    stats_fallback=Path("docs/data/stats.json"),
    log_path=Path("logs/census.log"),
    ror_ids=("https://ror.org/019tgvf94",),
    affiliation_names=(
        "Université Côte d'Azur",
        "Universite Cote d'Azur",
        "Univ. Côte d'Azur",
        "Univ Côte d'Azur",
        "University Côte d'Azur",
        "University Cote d'Azur",
    ),
)

UBE = University(
    id="ube",
    collection="UNIV-BOURGOGNE",
    short_name="UBE",
    display_name="Université Bourgogne Europe",
    site_name="HAL-UBE",
    tagline=(
        "Open-science monitoring for Université Bourgogne Europe on HAL: "
        "linked datasets, repositories, software, and correction queues."
    ),
    org_url="https://www.ube.fr/",
    site_path="ube",
    logo="ube.png",
    census_dir=Path("data/ube/census"),
    links_path=Path("data/ube/links.jsonl"),
    harvest_path=Path("data/ube/harvest.jsonl"),
    site_dir=Path("docs/ube"),
    stats_fallback=Path("docs/ube/data/stats.json"),
    log_path=Path("logs/ube-census.log"),
)

UNIVERSITIES: dict[str, University] = {
    UNICA.id: UNICA,
    UBE.id: UBE,
}

DEFAULT_UNIVERSITY = UNICA

_current: ContextVar[University] = ContextVar("hal_university", default=UNICA)


def get_university() -> University:
    return _current.get()


def set_university(uni: University):
    """Bind the active tenant for site rendering. Returns a reset token."""
    return _current.set(uni)


def reset_university(token) -> None:
    _current.reset(token)


def resolve_university(key: str | None) -> University:
    """Resolve ``--university`` / collection code / id to a registered tenant."""
    if not key:
        return DEFAULT_UNIVERSITY
    raw = key.strip()
    lowered = raw.lower()
    if lowered in UNIVERSITIES:
        return UNIVERSITIES[lowered]
    for uni in UNIVERSITIES.values():
        if uni.collection.upper() == raw.upper():
            return uni
        if uni.short_name.lower() == lowered:
            return uni
    known = ", ".join(sorted(UNIVERSITIES))
    raise KeyError(f"Unknown university {key!r}. Known ids: {known}")


def other_universities(viewer: University | None = None) -> list[University]:
    """Universities shown in the logo row (everyone except the viewer)."""
    current = viewer or get_university()
    return [u for u in UNIVERSITIES.values() if u.id != current.id]
