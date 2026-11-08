"""Shared test helpers. No test touches the live network."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from opennaksha.http import PoliteClient
from opennaksha.models import DiscoveredFile, DiscoveredScheme

T0 = datetime(2026, 11, 1, 2, 0, tzinfo=UTC)
T1 = datetime(2026, 11, 8, 2, 0, tzinfo=UTC)
T2 = datetime(2026, 11, 15, 2, 0, tzinfo=UTC)


def scheme(
    no: str = "57",
    *,
    city: str = "surat",
    authority: str = "SMC",
    status: str = "preliminary",
    name_en: str | None = "Example",
    files: list[tuple[str, str]] | None = None,
) -> DiscoveredScheme:
    files = files if files is not None else [("map", f"https://example.test/tp{no}.pdf")]
    return DiscoveredScheme(
        city_id=city,
        authority=authority,
        scheme_type="TP",
        scheme_no=no,
        name_en=name_en,
        status=status,  # type: ignore[arg-type]
        source_page_url="https://example.test/tp",
        files=[DiscoveredFile(kind=k, title=f"{k} {no}", url=u) for k, u in files],  # type: ignore[arg-type]
    )


def mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> PoliteClient:
    """A PoliteClient backed by an in-memory transport, with no throttling or robots fetch."""
    return PoliteClient(
        transport=httpx.MockTransport(handler),
        min_interval=0,
        sleep=lambda _s: None,
        respect_robots=False,
    )


class FakeFiles:
    """Serves file bytes by URL; HEAD returns ETag/Content-Length derived from the content."""

    def __init__(self, files: dict[str, bytes], *, validators: bool = True) -> None:
        self.files = files
        self.validators = validators
        self.gets: list[str] = []
        self.heads: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        body = self.files.get(url)
        if body is None:
            return httpx.Response(404)
        headers = {}
        if self.validators:
            headers = {"ETag": f'"{hash(body) & 0xFFFFFFFF:x}"', "Content-Length": str(len(body))}
        if request.method == "HEAD":
            self.heads.append(url)
            return httpx.Response(200, headers=headers)
        self.gets.append(url)
        return httpx.Response(200, headers=headers, content=body)
