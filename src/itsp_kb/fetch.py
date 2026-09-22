"""Fetchers for the NIST OSCAL baseline and the Cyber Centre ITSP publications
(spec S3.2, S3.3, S3.4). Every fetch writes a dated raw snapshot with hashes
and provenance; nothing here parses the content it downloads.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from itsp_kb.config import DEFAULT_DATA_ROOT, FamilyEntry, SourceEntry, SourceRegistry
from itsp_kb.provenance import (
    latest_raw_snapshot_dir,
    write_snapshot,
)

logger = logging.getLogger(__name__)

USER_AGENT = "itsp-kb/0.1.0 (+unofficial ITSP.10.033 knowledge-base extractor; deterministic research tool)"
REQUEST_TIMEOUT = 30.0
INTER_REQUEST_DELAY_SECONDS = 0.5


class FetchError(RuntimeError):
    def __init__(self, message: str, *, publication: str, url: str):
        super().__init__(message)
        self.publication = publication
        self.url = url


class SourceChangedError(RuntimeError):
    """Raised when a source's discovered layout no longer matches the registry
    (spec S2.8: a source-layout change MUST fail validation in strict mode)."""

    def __init__(self, message: str, *, publication: str):
        super().__init__(message)
        self.publication = publication


@dataclass
class FetchResult:
    source_id: str
    snapshot_dir: Path
    resolved_commit: str | None = None


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    )


def _previous_conditional_headers(source_id: str, data_root: Path, subdir: str | None = None) -> dict[str, str]:
    prev_dir = latest_raw_snapshot_dir(source_id, data_root=data_root)
    if prev_dir is None:
        return {}
    if subdir:
        prev_dir = prev_dir / subdir
    headers_file = prev_dir / "headers.json"
    if not headers_file.exists():
        return {}
    import json

    prev_headers = json.loads(headers_file.read_text(encoding="utf-8"))
    cond: dict[str, str] = {}
    if etag := prev_headers.get("etag"):
        cond["If-None-Match"] = etag
    if last_mod := prev_headers.get("last-modified"):
        cond["If-Modified-Since"] = last_mod
    return cond


def resolve_github_commit(client: httpx.Client, *, repo: str, ref: str, path: str) -> str:
    """Resolve a branch/tag ref to a concrete commit SHA via the GitHub commits API
    (spec S3.3: a reproducible build must record the resolved commit, not `main`)."""
    owner_repo = repo.removeprefix("https://github.com/").rstrip("/")
    api_url = f"https://api.github.com/repos/{owner_repo}/commits"
    resp = client.get(api_url, params={"sha": ref, "path": path, "per_page": 1})
    if resp.status_code != 200 or not resp.json():
        raise FetchError(
            f"Could not resolve ref '{ref}' to a commit for {owner_repo}:{path} (HTTP {resp.status_code})",
            publication="NIST SP 800-53 Rev. 5",
            url=api_url,
        )
    return resp.json()[0]["sha"]


def fetch_nist_oscal(
    registry: SourceRegistry,
    *,
    nist_ref: str | None = None,
    force: bool = False,
    data_root: Path = DEFAULT_DATA_ROOT,
) -> FetchResult:
    source = registry["nist_sp800_53_rev5_oscal"]
    ref = nist_ref or source.source_ref or "main"
    assert source.repository and source.path and source.raw_url

    with _client() as client:
        resolved_commit = resolve_github_commit(client, repo=source.repository, ref=ref, path=source.path)
        raw_url = source.raw_url.format(ref=resolved_commit)

        cond_headers = {} if force else _previous_conditional_headers("nist_sp800_53_rev5_oscal", data_root)
        resp = client.get(raw_url, headers=cond_headers)
        if resp.status_code == 304:
            prev_dir = latest_raw_snapshot_dir("nist_sp800_53_rev5_oscal", data_root=data_root)
            assert prev_dir is not None
            content = (prev_dir / "catalog.json").read_bytes()
            http_status = 304
        elif resp.status_code == 200:
            content = resp.content
            http_status = 200
        else:
            raise FetchError(
                f"Failed to fetch NIST OSCAL catalog (HTTP {resp.status_code})",
                publication="NIST SP 800-53 Rev. 5",
                url=raw_url,
            )

        snapshot_dir = write_snapshot(
            source_id="nist_sp800_53_rev5_oscal",
            publication=source.publication,
            url=raw_url,
            content=content,
            content_filename="catalog.json",
            configured_ref=ref,
            resolved_commit=resolved_commit,
            http_status=http_status,
            content_type="application/json",
            headers=dict(resp.headers) if resp.status_code == 200 else None,
            data_root=data_root,
        )
    return FetchResult(source_id="nist_sp800_53_rev5_oscal", snapshot_dir=snapshot_dir, resolved_commit=resolved_commit)


def _fetch_page(
    client: httpx.Client,
    *,
    source_id: str,
    publication: str,
    url: str,
    filename: str,
    force: bool,
    data_root: Path,
    extra_fetch_fields: dict | None = None,
    subdir: str | None = None,
) -> tuple[bytes, Path]:
    cond_headers = {} if force else _previous_conditional_headers(source_id, data_root, subdir=subdir)
    resp = client.get(url, headers=cond_headers)
    if resp.status_code == 304:
        prev_dir = latest_raw_snapshot_dir(source_id, data_root=data_root)
        assert prev_dir is not None
        if subdir:
            prev_dir = prev_dir / subdir
        content = (prev_dir / filename).read_bytes()
        http_status = 304
        headers_to_store = None
    elif resp.status_code == 200:
        content = resp.content
        http_status = 200
        headers_to_store = dict(resp.headers)
    else:
        raise FetchError(f"HTTP {resp.status_code} fetching {url}", publication=publication, url=url)

    snapshot_dir = write_snapshot(
        source_id=source_id,
        publication=publication,
        url=url,
        content=content,
        content_filename=filename,
        http_status=http_status,
        content_type="text/html",
        headers=headers_to_store,
        extra_fetch_fields=extra_fetch_fields,
        data_root=data_root,
        subdir=subdir,
    )
    time.sleep(INTER_REQUEST_DELAY_SECONDS)
    return content, snapshot_dir


def discover_itsp_10_033_families(client: httpx.Client, toc_url: str) -> list[tuple[str, str]]:
    """Discover (name, slug) pairs from the live table-of-contents page, for
    validation against `config/sources.yaml`'s configured family list (spec
    S7.2 step 2 / S2.8 -- a TOC layout change must be a visible diff)."""
    from bs4 import BeautifulSoup

    resp = client.get(toc_url)
    if resp.status_code != 200:
        raise FetchError(f"HTTP {resp.status_code} fetching TOC {toc_url}", publication="ITSP.10.033", url=toc_url)
    soup = BeautifulSoup(resp.text, "lxml")
    main = soup.find("main") or soup
    # The page-navigation "Previous"/"Next" links and the TOC/concepts pages point into
    # `/itsp10033/...` too but are not family pages; exclude them explicitly rather than
    # relying on link text alone (the family list is otherwise identified by its href).
    non_family_slugs = {
        "concepts-structure",
        "foreword-overview-introduction",
        "controls-assurance-activities-families",
    }
    seen: dict[str, str] = {}
    for a in main.find_all("a", href=True):
        href = str(a["href"])
        name = a.get_text(strip=True)
        if "/itsp10033/" not in href or "#" in href:
            continue
        if name in {"Previous", "Next", "Table of Contents", ""}:
            continue
        slug = href.rstrip("/").rsplit("/", 1)[-1]
        if slug in non_family_slugs or href.rstrip("/").endswith("itsp10033"):
            continue
        if slug not in seen:
            seen[slug] = name
    return [(name, slug) for slug, name in seen.items()]


def fetch_itsp_10_033(
    registry: SourceRegistry,
    *,
    force: bool = False,
    data_root: Path = DEFAULT_DATA_ROOT,
    strict: bool = False,
) -> list[FetchResult]:
    source = registry["itsp_10_033"]
    assert source.toc_url and source.root_url
    results: list[FetchResult] = []

    with _client() as client:
        discovered = discover_itsp_10_033_families(client, source.toc_url)
        discovered_slugs = {slug for _, slug in discovered}
        configured_slugs = {f.slug for f in source.families}
        missing = configured_slugs - discovered_slugs
        extra = discovered_slugs - configured_slugs
        if missing or extra:
            msg = f"ITSP.10.033 family TOC has changed: missing={sorted(missing)} extra={sorted(extra)}"
            if strict:
                raise SourceChangedError(msg, publication="ITSP.10.033")
            logger.warning(msg)

        for family in source.families:
            url = f"{source.root_url.rsplit('/itsp10033', 1)[0]}/itsp10033/{family.slug}"
            _, snapshot_dir = _fetch_page(
                client,
                source_id="itsp_10_033",
                publication=source.publication,
                url=url,
                filename="source.html",
                force=force,
                data_root=data_root,
                extra_fetch_fields={"family_id": family.id, "family_slug": family.slug},
                subdir=family.slug,
            )
            results.append(FetchResult(source_id="itsp_10_033", snapshot_dir=snapshot_dir))

    return results


def fetch_itsp_10_033_01(
    registry: SourceRegistry,
    *,
    force: bool = False,
    data_root: Path = DEFAULT_DATA_ROOT,
) -> FetchResult:
    source = registry["itsp_10_033_01"]
    assert source.root_url
    with _client() as client:
        _, snapshot_dir = _fetch_page(
            client,
            source_id="itsp_10_033_01",
            publication=source.publication,
            url=source.root_url,
            filename="profile.html",
            force=force,
            data_root=data_root,
        )
    return FetchResult(source_id="itsp_10_033_01", snapshot_dir=snapshot_dir)


def fetch_all(
    registry: SourceRegistry,
    *,
    offline: bool = False,
    force: bool = False,
    nist_ref: str | None = None,
    publication: str | None = None,
    data_root: Path = DEFAULT_DATA_ROOT,
    strict: bool = False,
) -> dict[str, list[FetchResult]]:
    if offline:
        logger.info("offline mode: skipping network fetch, relying on existing raw snapshots")
        return {}

    results: dict[str, list[FetchResult]] = {}
    if publication is None or publication == "NIST SP 800-53 Rev. 5":
        results["nist_sp800_53_rev5_oscal"] = [
            fetch_nist_oscal(registry, nist_ref=nist_ref, force=force, data_root=data_root)
        ]
    if publication is None or publication == "ITSP.10.033":
        results["itsp_10_033"] = fetch_itsp_10_033(registry, force=force, data_root=data_root, strict=strict)
    if publication is None or publication == "ITSP.10.033-01":
        results["itsp_10_033_01"] = [fetch_itsp_10_033_01(registry, force=force, data_root=data_root)]
    return results


__all__ = [
    "FamilyEntry",
    "FetchError",
    "FetchResult",
    "SourceChangedError",
    "SourceEntry",
    "discover_itsp_10_033_families",
    "fetch_all",
    "fetch_itsp_10_033",
    "fetch_itsp_10_033_01",
    "fetch_nist_oscal",
    "resolve_github_commit",
]
