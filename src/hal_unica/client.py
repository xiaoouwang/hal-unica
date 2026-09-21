from __future__ import annotations

import time
from typing import Any, Iterator
from urllib.parse import urljoin

import httpx

DEFAULT_BASE = "https://api.archives-ouvertes.fr"
DEFAULT_COLLECTION = "UNIV-COTEDAZUR"


class HalClient:
    """Thin HAL Search API client with polite retries."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE,
        collection: str = DEFAULT_COLLECTION,
        timeout: float = 60.0,
        min_interval: float = 0.25,
        user_agent: str = "hal-unica/0.1 (+metadata-harvest; contact=local)",
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.collection = collection
        self.min_interval = min_interval
        self._last_request = 0.0
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HalClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = urljoin(self.base_url, path.lstrip("/"))
        delays = (1.0, 2.0, 5.0, 10.0)
        last_exc: Exception | None = None
        for attempt, delay in enumerate([0.0, *delays]):
            if delay:
                time.sleep(delay)
            self._throttle()
            try:
                self._last_request = time.monotonic()
                resp = self._client.get(url, params=params)
                if resp.status_code in {429, 500, 502, 503, 504}:
                    last_exc = httpx.HTTPStatusError(
                        f"retryable {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                continue
        assert last_exc is not None
        raise last_exc

    def count(self, *, q: str = "*:*", fq: list[str] | None = None) -> int:
        data = self.search(q=q, fq=fq, rows=0, cursor_mark=None)
        return int(data["response"]["numFound"])

    def search(
        self,
        *,
        q: str = "*:*",
        fq: list[str] | None = None,
        fl: list[str] | None = None,
        rows: int = 1000,
        sort: str | None = "docid asc",
        cursor_mark: str | None = "*",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "q": q,
            "wt": "json",
            "rows": rows,
        }
        if fl:
            params["fl"] = ",".join(fl)
        if sort:
            params["sort"] = sort
        if cursor_mark is not None:
            params["cursorMark"] = cursor_mark
        if fq:
            # httpx encodes repeated keys correctly for Solr fq
            params["fq"] = fq
        path = f"search/{self.collection}/"
        return self._get(path, params)

    def iter_docs(
        self,
        *,
        q: str = "*:*",
        fq: list[str] | None = None,
        fl: list[str] | None = None,
        rows: int = 1000,
        max_docs: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield documents via Solr cursor pagination (latest versions in index)."""
        cursor = "*"
        yielded = 0
        while True:
            data = self.search(q=q, fq=fq, fl=fl, rows=rows, cursor_mark=cursor)
            docs = data["response"].get("docs", [])
            for doc in docs:
                yield doc
                yielded += 1
                if max_docs is not None and yielded >= max_docs:
                    return
            next_cursor = data.get("nextCursorMark")
            if not docs or next_cursor is None or next_cursor == cursor:
                return
            cursor = next_cursor
