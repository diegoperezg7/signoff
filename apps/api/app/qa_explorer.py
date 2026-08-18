"""Safe smoke exploration for the running application.

This is deliberately a bounded verifier, not an unconstrained crawler. It
only visits an explicit host, follows same-origin links and returns facts that
can be attached to a verification run. Playwright is optional; HTTP discovery
keeps MOCK_MODE useful on machines without browser binaries.
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.buttons: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag == "button":
            self.buttons.append(values.get("aria-label", "button"))
        self._in_title = tag == "title"

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()


class QAExplorer:
    def __init__(self, allowed_hosts: set[str] | None = None, timeout_seconds: float = 8.0) -> None:
        self.allowed_hosts = allowed_hosts or {"localhost", "127.0.0.1"}
        self.timeout_seconds = timeout_seconds

    def _validate_url(self, url: str, base_url: str | None = None) -> str:
        absolute = urljoin(base_url or url, url)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in self.allowed_hosts:
            raise ValueError("QA Explorer can only visit explicitly allowed local hosts")
        return absolute

    def discover(self, target_url: str, max_routes: int = 20) -> dict[str, Any]:
        target = self._validate_url(target_url)
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(target)
        parser = _LinkParser()
        parser.feed(response.text[:1_000_000])
        routes: list[str] = [target]
        for link in parser.links:
            try:
                candidate = self._validate_url(link, target)
            except ValueError:
                continue
            parsed = urlparse(candidate)
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"
            if normalized not in routes and len(routes) < max_routes:
                routes.append(normalized)
        # Signoff publishes a route manifest in the frontend build. In local
        # mock mode the generated HTML may not contain navigation links, so
        # these safe, read-only hints make the smoke check useful immediately.
        if urlparse(target).hostname in self.allowed_hosts and urlparse(target).port in {3000, None}:
            for path in ("/", "/dashboard", "/projects", "/milestones", "/releases", "/reports", "/baselines", "/metrics", "/risk", "/templates", "/teams", "/integrations", "/settings", "/review/demo-review-token"):
                candidate = self._validate_url(path, target)
                if candidate not in routes and len(routes) < max_routes:
                    routes.append(candidate)
        return {
            "target_url": target,
            "status_code": response.status_code,
            "title": parser.title,
            "routes": routes,
            "buttons_observed": len(parser.buttons),
            "links_observed": len(parser.links),
            "content_length": len(response.content),
        }

    def smoke_check(self, target_url: str, routes: list[str] | None = None, max_steps: int = 12) -> dict[str, Any]:
        target = self._validate_url(target_url)
        if routes is None:
            routes = self.discover(target, max_routes=max_steps).get("routes", [target])
        observations: list[dict[str, Any]] = []
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for index, route in enumerate(routes[:max_steps], 1):
                safe_route = self._validate_url(route, target)
                try:
                    response = client.get(safe_route)
                    parser = _LinkParser()
                    parser.feed(response.text[:1_000_000])
                    observations.append({"step": index, "url": safe_route, "status_code": response.status_code, "passed": 200 <= response.status_code < 400, "title": parser.title, "links": len(parser.links), "buttons": len(parser.buttons)})
                except httpx.HTTPError as exc:
                    observations.append({"step": index, "url": safe_route, "status_code": None, "passed": False, "error": str(exc)})
        failed = [item for item in observations if not item["passed"]]
        return {
            "target_url": target,
            "routes_checked": len(observations),
            "observations": observations,
            "state": "demonstrated" if observations and not failed else "partially_demonstrated" if observations else "inconclusive",
            "failed_routes": [item["url"] for item in failed],
            "provider": "http-smoke-explorer",
            "browser_engine": "playwright-not-required",
        }
