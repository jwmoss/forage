"""Intercept only browser network requests for isolated CLI process tests."""

from __future__ import annotations

import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from playwright.sync_api import Browser, Route

_fixture_origin = os.environ.get("FORAGE_E2E_ORIGIN")
_original_context = Browser.new_context


def _route(route: Route) -> None:
    endpoint = urlparse(route.request.url)
    if endpoint.scheme != "https" or endpoint.hostname != "www.facebook.com":
        route.abort("blockedbyclient")
        return
    request = Request(
        f"{_fixture_origin}{endpoint.path}?{endpoint.query}",
        headers={"X-Fixture-Cookie": route.request.all_headers().get("cookie", "")},
    )
    with urlopen(request, timeout=5) as response:
        if response.headers.get("X-Fixture-Abort"):
            route.abort("connectionrefused")
            return
        route.fulfill(
            status=response.status,
            content_type=response.headers.get("Content-Type", "text/html"),
            body=response.read(),
        )


def _new_context(self: Browser, *args, **kwargs):
    context = _original_context(self, *args, **kwargs)
    context.route("**/*", _route)
    return context


if _fixture_origin:
    Browser.new_context = _new_context
