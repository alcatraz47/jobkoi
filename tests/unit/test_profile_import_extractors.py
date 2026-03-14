"""Unit tests for profile import extraction adapters."""

from __future__ import annotations

from app.services.profile_import_extractors import WebsiteImportExtractor, _extract_same_domain_links


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
