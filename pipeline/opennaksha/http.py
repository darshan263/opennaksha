"""A polite HTTP client for government sites (PLAN.md §2 and §6).

- Clear User-Agent with a contact address taken from ``OPENNAKSHA_CONTACT``.
- robots.txt is fetched once per host and respected.
- At most one request per second per host.
- Timeouts, and retries with exponential backoff on network errors and 5xx/429.
- Optional on-disk cache of GET responses for development (``OPENNAKSHA_HTTP_CACHE=1``).
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from opennaksha import __version__

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=15.0)
RETRY_STATUSES = {429, 500, 502, 503, 504}


class RobotsDisallowed(Exception):
    pass


def user_agent() -> str:
    contact = os.environ.get("OPENNAKSHA_CONTACT", "").strip()
    suffix = f"; contact: {contact}" if contact else ""
    return f"OpenNaksha/{__version__} (open-source TP map catalog; non-commercial{suffix})"


@dataclass
class HeadInfo:
    status_code: int
    etag: str | None
    last_modified: str | None
    content_length: int | None

    @property
    def has_validators(self) -> bool:
        return any(v is not None for v in (self.etag, self.last_modified, self.content_length))


@dataclass
class Download:
    sha256: str
    size_bytes: int
    path: Path | None


class PoliteClient:
    def __init__(
        self,
        *,
        min_interval: float = 1.0,
        retries: int = 3,
        backoff: float = 2.0,
        cache_dir: Path | None = None,
        insecure_hosts: frozenset[str] = frozenset(),
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        respect_robots: bool = True,
    ) -> None:
        self.min_interval = min_interval
        self.retries = retries
        self.backoff = backoff
        self.cache_dir = cache_dir
        if cache_dir is None and os.environ.get("OPENNAKSHA_HTTP_CACHE") == "1":
            self.cache_dir = Path(".http_cache")
        self.respect_robots = respect_robots
        self._sleep = sleep
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._lock = threading.Lock()
        headers = {"User-Agent": user_agent(), "Accept-Language": "en,gu;q=0.8"}
        common = dict(headers=headers, timeout=DEFAULT_TIMEOUT, follow_redirects=True)
        self._client = httpx.Client(transport=transport, **common)
        # Some government sites serve broken TLS chains. Hosts listed by a scraper (and
        # documented in docs/sources.md) skip verification; everything else is verified.
        self._insecure_hosts = insecure_hosts
        self._insecure_client = (
            httpx.Client(transport=transport, verify=False, **common) if insecure_hosts else None
        )

    # ------------------------------------------------------------------ plumbing

    def close(self) -> None:
        self._client.close()
        if self._insecure_client:
            self._insecure_client.close()

    def __enter__(self) -> PoliteClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _client_for(self, host: str) -> httpx.Client:
        if self._insecure_client and host in self._insecure_hosts:
            return self._insecure_client
        return self._client

    def _throttle(self, host: str) -> None:
        # Reserve the next free slot for this host under the lock, then sleep outside it so
        # threads working on other hosts are never blocked.
        with self._lock:
            now = time.monotonic()
            last = self._last_request.get(host)
            slot = now if last is None else max(now, last + self.min_interval)
            self._last_request[host] = slot
        if slot > now:
            self._sleep(slot - now)

    def _allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlsplit(url)
        host = parts.netloc
        if host not in self._robots:
            robots_url = f"{parts.scheme}://{host}/robots.txt"
            parser: RobotFileParser | None = RobotFileParser(robots_url)
            try:
                resp = self._send("GET", robots_url, check_robots=False, retries=1)
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                else:
                    parser = None  # no robots.txt → everything allowed
            except httpx.HTTPError as e:
                log.warning("robots.txt unavailable for %s (%s); treating as allowed", host, e)
                parser = None
            self._robots[host] = parser
        parser = self._robots[host]
        return parser is None or parser.can_fetch(user_agent(), url)

    def _send(
        self,
        method: str,
        url: str,
        *,
        check_robots: bool = True,
        retries: int | None = None,
        **kwargs: object,
    ) -> httpx.Response:
        if check_robots and not self._allowed(url):
            raise RobotsDisallowed(url)
        host = urlsplit(url).netloc
        attempts = (retries if retries is not None else self.retries) + 1
        for attempt in range(attempts):
            self._throttle(host)
            try:
                resp = self._client_for(host).request(method, url, **kwargs)  # type: ignore[arg-type]
                if resp.status_code not in RETRY_STATUSES or attempt == attempts - 1:
                    return resp
                log.info("%s %s → %s, retrying", method, url, resp.status_code)
            except httpx.TransportError:
                if attempt == attempts - 1:
                    raise
                log.info("%s %s failed, retrying", method, url, exc_info=True)
            self._sleep(self.backoff * (2**attempt))
        raise AssertionError("unreachable")

    # ------------------------------------------------------------------ public API

    def get_text(self, url: str) -> str:
        """GET a page and return its text. Raises on HTTP errors."""
        cache_file = None
        if self.cache_dir:
            cache_file = self.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".html")
            if cache_file.exists():
                return cache_file.read_text(encoding="utf-8")
        resp = self._send("GET", url)
        resp.raise_for_status()
        text = resp.text
        if cache_file:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(text, encoding="utf-8")
        return text

    def get_json(self, url: str, **kwargs: object) -> object:
        resp = self._send("GET", url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def post_text(self, url: str, data: dict[str, str]) -> str:
        resp = self._send("POST", url, data=data)
        resp.raise_for_status()
        return resp.text

    def head(self, url: str) -> HeadInfo | None:
        """HEAD a file. Returns None if the server doesn't support HEAD or it fails."""
        try:
            resp = self._send("HEAD", url, retries=1)
        except (httpx.HTTPError, RobotsDisallowed) as e:
            log.info("HEAD %s failed: %s", url, e)
            return None
        if resp.status_code >= 400:
            return None
        length = resp.headers.get("content-length")
        return HeadInfo(
            status_code=resp.status_code,
            etag=resp.headers.get("etag"),
            last_modified=resp.headers.get("last-modified"),
            content_length=int(length) if length and length.isdigit() else None,
        )

    def download(self, url: str, dest: Path | None = None) -> Download:
        """Stream a file, hashing as it arrives. Saves it to ``dest`` if given."""
        if not self._allowed(url):
            raise RobotsDisallowed(url)
        host = urlsplit(url).netloc
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self._throttle(host)
            digest = hashlib.sha256()
            size = 0
            try:
                with self._client_for(host).stream("GET", url) as resp:
                    resp.raise_for_status()
                    out = dest.open("wb") if dest else None
                    try:
                        for chunk in resp.iter_bytes(1 << 16):
                            digest.update(chunk)
                            size += len(chunk)
                            if out:
                                out.write(chunk)
                    finally:
                        if out:
                            out.close()
                return Download(sha256=digest.hexdigest(), size_bytes=size, path=dest)
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in RETRY_STATUSES:
                    raise
                last_error = e
            except httpx.TransportError as e:
                last_error = e
            self._sleep(self.backoff * (2**attempt))
        assert last_error is not None
        raise last_error
