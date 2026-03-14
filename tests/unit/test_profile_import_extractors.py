"""Unit tests for profile import extraction adapters."""

from __future__ import annotations

import app.services.profile_import_extractors as extractors_module
from app.services.profile_import_extractors import (
    ProfileImportExtractionError,
    WebsiteImportExtractor,
    _extract_same_domain_links,
    _extract_website_text,
    _fetch_html_default,
    _normalize_url,
)


def test_extract_same_domain_links_filters_external_urls() -> None:
    """Link extraction should keep only same-domain URLs."""

    html = """
    <a href="/about">About</a>
    <a href="https://portfolio.example.dev/projects">Projects</a>
    <a href="https://other.example.dev/ignore">External</a>
    """

    links = _extract_same_domain_links(
        html=html,
        base_url="https://portfolio.example.dev",
        domain="portfolio.example.dev",
    )

    assert "https://portfolio.example.dev/about" in links
    assert "https://portfolio.example.dev/projects" in links
    assert all("other.example.dev" not in link for link in links)


def test_website_extractor_crawls_same_domain_pages_only() -> None:
    """Website extractor should crawl root plus same-domain pages up to max_pages."""

    pages = {
        "https://portfolio.example.dev": (
            "<a href='/about'>About</a><a href='https://outside.dev/x'>Outside</a>"
            "<main>Python Engineer</main>"
        ),
        "https://portfolio.example.dev/about": "<main>Built APIs and data products.</main>",
    }

    visited: list[str] = []

    def fake_fetch(url: str) -> str:
        visited.append(url)
        return pages[url]

    extractor = WebsiteImportExtractor(fetch_html=fake_fetch)
    name, results = extractor.extract_from_url(url="https://portfolio.example.dev", max_pages=2)

    assert name in {"trafilatura", "html_fallback"}
    assert len(results) == 2
    assert all(item.url.startswith("https://portfolio.example.dev") for item in results)
    assert all("outside.dev" not in url for url in visited)


def test_website_extractor_skips_failing_non_root_pages() -> None:
    """Website extractor should continue when non-root linked pages fail."""

    pages = {
        "https://portfolio.example.dev": "<a href='/good'>Good</a><a href='/bad'>Bad</a><main>Home</main>",
        "https://portfolio.example.dev/good": "<main>Project portfolio details.</main>",
    }

    def fake_fetch(url: str) -> str:
        if url.endswith("/bad"):
            raise ProfileImportExtractionError("blocked")
        return pages[url]

    extractor = WebsiteImportExtractor(fetch_html=fake_fetch)
    _, results = extractor.extract_from_url(url="https://portfolio.example.dev", max_pages=3)

    urls = [item.url for item in results]
    assert "https://portfolio.example.dev" in urls
    assert "https://portfolio.example.dev/good" in urls


def test_normalize_url_accepts_bare_domain_input() -> None:
    """URL normalization should support inputs without explicit scheme."""

    assert _normalize_url("example.com") == "https://example.com"
    assert _normalize_url("example.com/path") == "https://example.com/path"


def test_fetch_html_default_handles_tls_verification_fallback(monkeypatch) -> None:
    """Default fetch should retry with verify=False after TLS verification errors."""

    calls: list[tuple[str, bool]] = []

    def fake_fetch(*, url: str, verify: bool) -> str:
        calls.append((url, verify))
        if verify:
            raise ProfileImportExtractionError("certificate verify failed")
        return "<html>ok</html>"

    monkeypatch.setattr(extractors_module, "_fetch_html_with_verify", fake_fetch)

    html = _fetch_html_default("https://example.com")

    assert html == "<html>ok</html>"
    assert calls == [
        ("https://example.com", True),
        ("https://example.com", False),
    ]


def test_extract_website_text_fallback_removes_scripts_and_keeps_structure() -> None:
    """Fallback website text extractor should remove script content and preserve line breaks."""

    html = """
    <html>
      <body>
        <h1>Arfan Example</h1>
        <script>window.secret = 'ignore me';</script>
        <p>AI Engineer and Data Scientist</p>
        <h2>Skills</h2>
        <p>Python • NLP • Computer Vision</p>
      </body>
    </html>
    """

    text = _extract_website_text(html=html, url="https://portfolio.example.dev")

    assert "Arfan Example" in text
    assert "AI Engineer and Data Scientist" in text
    assert "ignore me" not in text
    assert "\n" in text
