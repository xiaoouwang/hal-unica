"""Resolve DOIs via the DataCite REST API for fine-grained repository labels."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import quote, urlparse

import httpx

DATACITE_DOI = "https://api.datacite.org/dois/{doi}"


@dataclass
class DoiResolution:
    doi: str
    publisher: str | None = None
    title: str | None = None
    landing_url: str | None = None
    landing_host: str | None = None
    prefix: str | None = None
    client_id: str | None = None
    repository: str | None = None
    object_kind: str | None = None  # dataset_repo | publication_landing | other | unresolved
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DoiResolution:
        return cls(
            doi=str(data.get("doi") or ""),
            publisher=data.get("publisher"),
            title=data.get("title"),
            landing_url=data.get("landing_url"),
            landing_host=data.get("landing_host"),
            prefix=data.get("prefix"),
            client_id=data.get("client_id"),
            repository=data.get("repository"),
            object_kind=data.get("object_kind"),
            error=data.get("error"),
        )

    def reclassify(self) -> DoiResolution:
        """Re-apply repository / object_kind rules without calling DataCite."""
        repo, kind = classify_repository(
            doi=self.doi,
            publisher=self.publisher,
            landing_url=self.landing_url,
            prefix=self.prefix,
            client_id=self.client_id,
        )
        self.repository = repo
        self.object_kind = kind
        return self



def _host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


def classify_repository(
    *,
    doi: str,
    publisher: str | None,
    landing_url: str | None,
    prefix: str | None,
    client_id: str | None,
) -> tuple[str, str]:
    """
    Return (repository_label, object_kind).

    object_kind:
      - dataset_repo: lands on a data repository
      - publication_landing: DOI resolves to HAL/publisher page (not a data vault)
      - other / unresolved
    """
    host = _host(landing_url) or ""
    pub = (publisher or "").strip()
    pref = (prefix or doi.split("/")[0]).lower()

    # Host-based (most reliable for "where does it live?")
    if host.endswith("nakala.fr") or host == "api.nakala.fr":
        return "NAKALA", "dataset_repo"
    if host in {
        "entrepot.recherche.data.gouv.fr",
        "recherche.data.gouv.fr",
    } or host.endswith("recherche.data.gouv.fr"):
        return "Recherche Data Gouv", "dataset_repo"
    # Data INRAE is a federated node of Recherche Data Gouv
    if host in {"data.inrae.fr", "entrepot.inrae.fr"} or host.endswith("data.inrae.fr"):
        return "Recherche Data Gouv", "dataset_repo"

    known_hosts: list[tuple[tuple[str, ...], str]] = [
        (("zenodo.org",), "Zenodo"),
        (("figshare.com",), "Figshare"),
        (("datadryad.org", "dryad"), "Dryad"),
        (("osf.io",), "OSF"),
        (("pangaea.de",), "PANGAEA"),
        (("seanoe.org",), "SEANOE"),
        (("data.mendeley.com",), "Mendeley Data"),
        (("harvard.dataverse.org", "dataverse.harvard.edu"), "Harvard Dataverse"),
        (("iedadata.org", "www.iedadata.org", "ecl.earthchem.org"), "IEDA"),
        (("doi.pangaea.de",), "PANGAEA"),
        (("softwareheritage.org", "archive.softwareheritage.org"), "Software Heritage"),
        (("huggingface.co",), "Hugging Face"),
        (("fdsn.org",), "FDSN / seismic network"),
        (("seismology.epos-france.fr",), "Epos-France Seismological Data Center"),
        (("networks.seismo.ethz.ch",), "ETH Zurich seismic networks"),
        (("geoscope.ipgp.fr",), "GEOSCOPE"),
        (("vizier.cds.unistra.fr", "cdsarc.cds.unistra.fr", "cds.unistra.fr"), "CDS"),
        (("openneuro.org",), "OpenNeuro"),
        (("dataverse.ird.fr",), "DataSuds"),
        (("data.indores.fr",), "data.InDoRES"),
        (("campagnes.flotteoceanographique.fr",), "Sismer"),
        (("camcatt.sedoo.fr", "mistrals.sedoo.fr", "sedoo.fr"), "SEDOO / Theia"),
        (("resources.marine.copernicus.eu", "marine.copernicus.eu"), "Mercator Ocean / Copernicus Marine"),
        (("data.aeronomie.be",), "BIRA-IASB data"),
        (("data.oreme.org",), "OSU OREME"),
        (("data.progedo.fr",), "Progedo-Adisp"),
        (("data.bris.ac.uk",), "University of Bristol data.bris"),
        (("ncei.noaa.gov",), "NOAA NCEI"),
        (("archive.stsci.edu",), "STScI/MAST"),
        (("pid.geoscience.gov.au",), "Geoscience Australia"),
        (("geosur.osureunion.fr",), "OSU Réunion"),
        (("radar.kit.edu",), "RADAR KIT"),
        (("jamstec.go.jp",), "JAMSTEC"),
    ]
    for suffixes, label in known_hosts:
        if any(host == s or host.endswith("." + s) or s in host for s in suffixes):
            return label, "dataset_repo"

    # Generic data-repo URL patterns (Dataverse nodes, institutional data portals)
    if "dataverse." in host or host.startswith("data.") or ".data." in host:
        return pub or host, "dataset_repo"
    if any(tok in host for tok in ("opendata.", "open-data.", "dataportal.", "repository.")):
        return pub or host, "dataset_repo"

    # Preprints / scholarly networks / publishers — not data repositories
    publication_hosts: list[tuple[tuple[str, ...], str]] = [
        (("arxiv.org",), "arXiv"),
        (("researchgate.net",), "ResearchGate"),
        (("academia.edu",), "Academia.edu"),
        (("ssrn.com",), "SSRN"),
        (("biorxiv.org",), "bioRxiv"),
        (("medrxiv.org",), "medRxiv"),
        (("openalex.org",), "OpenAlex"),
        (("github.com",), "GitHub"),
        (("gitlab.com",), "GitLab"),
        (("archimer.ifremer.fr",), "Archimer (Ifremer publications)"),
        (("publikationen.bibliothek.kit.edu",), "KIT publications"),
        (("drops.dagstuhl.de",), "Dagstuhl"),
        (("canal-u.tv",), "Canal-U"),
        (("ieee.org", "ieeexplore.ieee.org"), "IEEE"),
        (("springer.com", "link.springer.com", "springernature.com"), "Springer"),
        (("sciencedirect.com", "elsevier.com"), "Elsevier"),
        (("nature.com",), "Nature"),
        (("wiley.com", "onlinelibrary.wiley.com"), "Wiley"),
        (("oup.com", "academic.oup.com"), "Oxford University Press"),
        (("acm.org", "dl.acm.org"), "ACM"),
        (("sioe.org",), "SIOE"),
    ]
    for suffixes, label in publication_hosts:
        if any(host == s or host.endswith("." + s) or s in host for s in suffixes):
            return label, "publication_landing"

    if "hal." in host or host.endswith("archives-ouvertes.fr"):
        label = pub or "INRAE/INRA DOI"
        return f"{label} → HAL notice", "publication_landing"

    # Prefix / publisher fallbacks when host is empty or generic (doi.org)
    if pref == "10.34847" or "nakala" in pub.lower():
        return "NAKALA", "dataset_repo"
    if pref == "10.57745" or pub.lower() == "recherche data gouv":
        return "Recherche Data Gouv", "dataset_repo"
    if pref == "10.15454":
        if "data inrae" in pub.lower() or "portail data" in pub.lower():
            return "Recherche Data Gouv", "dataset_repo"
        if pub:
            return f"{pub} (prefix 10.15454)", "other"
        return "Recherche Data Gouv", "other"
    if pref == "10.5281":
        return "Zenodo", "dataset_repo"
    if pref == "10.17882":
        return "SEANOE", "dataset_repo"
    if pref == "10.6084":
        return "Figshare", "dataset_repo"
    if pref == "10.48550" or "arxiv" in pub.lower():
        return "arXiv", "publication_landing"
    if pref == "10.13140" or "researchgate" in pub.lower() or pub.lower() == "unpublished":
        return "ResearchGate", "publication_landing"
    # Common Crossref journal prefixes with no DataCite landing → not datasets
    if pref in {
        "10.1007",
        "10.1109",
        "10.1016",
        "10.1002",
        "10.1038",
        "10.1093",
        "10.1137",
        "10.1145",
        "10.1017",
        "10.4000",
        "10.3917",
        "10.1371",
    }:
        return f"Journal DOI ({pref})", "publication_landing"

    # Unknown host/publisher: never assume a data repository
    if host and pub:
        return pub, "other"
    if pub:
        return pub, "other"
    if host:
        return host, "other"
    if pref:
        return f"DOI prefix {pref}", "unresolved"
    return "Unknown", "unresolved"


class DataCiteClient:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        min_interval: float = 0.15,
        user_agent: str = "hal-unica/0.1 (+datacite-resolve)",
    ) -> None:
        self.min_interval = min_interval
        self._last = 0.0
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/vnd.api+json",
            },
            follow_redirects=True,
        )
        self._cache: dict[str, DoiResolution] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DataCiteClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def resolve(self, doi: str) -> DoiResolution:
        doi = doi.strip()
        if doi in self._cache:
            return self._cache[doi]

        self._throttle()
        self._last = time.monotonic()
        url = DATACITE_DOI.format(doi=quote(doi, safe=""))
        try:
            resp = self._client.get(url)
            if resp.status_code == 404:
                result = DoiResolution(
                    doi=doi,
                    error="not_found",
                    repository="Unknown (DOI not in DataCite)",
                    object_kind="unresolved",
                )
                self._cache[doi] = result
                return result
            resp.raise_for_status()
            payload = resp.json()
            attrs = payload["data"]["attributes"]
            rel = payload["data"].get("relationships") or {}
            client = (rel.get("client") or {}).get("data") or {}
            titles = attrs.get("titles") or []
            title = titles[0].get("title") if titles else None
            landing = attrs.get("url")
            publisher = attrs.get("publisher")
            if isinstance(publisher, dict):
                publisher = publisher.get("name") or publisher.get("publisherName")
            prefix = attrs.get("prefix") or doi.split("/")[0]
            client_id = client.get("id")
            repository, object_kind = classify_repository(
                doi=doi,
                publisher=publisher,
                landing_url=landing,
                prefix=prefix,
                client_id=client_id,
            )
            result = DoiResolution(
                doi=doi,
                publisher=publisher,
                title=title,
                landing_url=landing,
                landing_host=_host(landing),
                prefix=prefix,
                client_id=client_id,
                repository=repository,
                object_kind=object_kind,
            )
        except Exception as exc:  # noqa: BLE001 — surface per-DOI errors in report
            result = DoiResolution(
                doi=doi,
                error=str(exc),
                repository="Unresolved (DataCite error)",
                object_kind="unresolved",
            )

        self._cache[doi] = result
        return result

    def dump_cache(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._cache.values()]


def looks_like_doi(value: str) -> bool:
    v = value.strip()
    return v.startswith("10.") and "/" in v
