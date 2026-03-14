"""Extraction adapters for CV and portfolio website profile imports."""

from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from app.domain.job_text import normalize_text

_DEFAULT_FETCH_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
}

_BLOCK_BREAK_TAGS: set[str] = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "div",
    "dl",
    "dt",
    "dd",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}

_SUPPRESSED_TAGS: set[str] = {"script", "style", "noscript", "svg"}


class ProfileImportExtractionError(Exception):
    """Raised when source extraction fails."""


@dataclass(frozen=True)
class ExtractedTextResult:
    """Extraction result for one source payload."""

    text: str
    extractor_name: str
    extractor_version: str | None = None


@dataclass(frozen=True)
class WebsitePageResult:
    """Extracted text result for one crawled website page."""

    url: str
    text: str


class CvImportExtractor:
    """CV extractor preferring Docling with fallback-compatible parsing."""

    def extract_from_file(
        self,
        *,
        file_path: Path,
        file_name: str,
        content_type: str | None,
    ) -> ExtractedTextResult:
        """Extract normalized text from a CV file.

        Args:
            file_path: Stored source file path.
            file_name: Original uploaded filename.
            content_type: Uploaded content type.

        Returns:
            Extracted text payload.

        Raises:
            ProfileImportExtractionError: If extraction cannot parse the file.
        """

        docling_result = _extract_with_docling(file_path)
        if docling_result is not None:
            return docling_result

        suffix = file_path.suffix.lower()
        if suffix == ".docx":
            text = _extract_docx_text(file_path)
            return ExtractedTextResult(text=_normalize_multiline_text(text), extractor_name="docx_fallback")

        if suffix == ".pdf":
            text = _extract_pdf_text(file_path)
            return ExtractedTextResult(text=_normalize_multiline_text(text), extractor_name="pdf_fallback")

        if suffix in {".txt", ".md", ".rtf"}:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            return ExtractedTextResult(text=_normalize_multiline_text(text), extractor_name="text_fallback")

        if content_type and "word" in content_type:
            text = _extract_docx_text(file_path)
            return ExtractedTextResult(text=_normalize_multiline_text(text), extractor_name="docx_fallback")

        if content_type and "pdf" in content_type:
            text = _extract_pdf_text(file_path)
            return ExtractedTextResult(text=_normalize_multiline_text(text), extractor_name="pdf_fallback")

        raise ProfileImportExtractionError(
            f"Unsupported CV format for file '{file_name}'. Only PDF and DOCX are supported."
        )


class WebsiteImportExtractor:
    """Website extractor with same-domain crawling and Trafilatura preference."""

    def __init__(
        self,
        *,
        fetch_html: Callable[[str], str] | None = None,
    ) -> None:
        """Initialize website extractor.

        Args:
            fetch_html: Optional custom fetcher used for testing.
        """

        self._fetch_html = fetch_html or _fetch_html_default

    def extract_from_url(self, *, url: str, max_pages: int) -> tuple[str, list[WebsitePageResult]]:
        """Extract useful text from one URL and same-domain linked pages.

        Args:
            url: Root website URL.
            max_pages: Maximum same-domain pages to crawl.

        Returns:
            Tuple of extractor name and extracted page payload list.

        Raises:
            ProfileImportExtractionError: If root page cannot be fetched or parsed.
        """

        normalized_url = _normalize_url(url)
        if not normalized_url:
            raise ProfileImportExtractionError("Invalid website URL.")

        page_limit = max(1, max_pages)
        domain = urlparse(normalized_url).netloc.lower()
        queue: list[str] = [normalized_url]
        visited: set[str] = set()
        pages: list[WebsitePageResult] = []

        while queue and len(pages) < page_limit:
            current_url = queue.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)

            try:
                html = self._fetch_html(current_url)
            except ProfileImportExtractionError:
                if current_url == normalized_url:
                    raise
                continue

            text = _extract_website_text(html=html, url=current_url)
            if text:
                pages.append(WebsitePageResult(url=current_url, text=text))

            for link in _extract_same_domain_links(html=html, base_url=current_url, domain=domain):
                if link in visited or link in queue:
                    continue
                if len(queue) + len(pages) >= page_limit * 3:
                    break
                queue.append(link)

        if not pages:
            raise ProfileImportExtractionError("No readable text could be extracted from the website.")

        extractor_name = "trafilatura" if _is_trafilatura_available() else "html_fallback"
        return extractor_name, pages


def compute_sha256_bytes(content: bytes) -> str:
    """Return SHA256 checksum for input bytes.

    Args:
        content: Raw source bytes.

    Returns:
        SHA256 hex digest.
    """

    digest = hashlib.sha256()
    digest.update(content)
    return digest.hexdigest()


def _extract_with_docling(file_path: Path) -> ExtractedTextResult | None:
    """Try extracting text using Docling when available."""

    try:
        from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]
    except Exception:
        return None

    try:
        converter = DocumentConverter()
        result = converter.convert(str(file_path))

        text = _docling_result_to_text(result)
        normalized = _normalize_multiline_text(text)
        if not normalized:
            return None
        return ExtractedTextResult(
            text=normalized,
            extractor_name="docling",
            extractor_version=None,
        )
    except Exception:
        return None


def _docling_result_to_text(result: object) -> str:
    """Best-effort conversion of Docling conversion result to text."""

    if result is None:
        return ""

    document = getattr(result, "document", None)
    if document is None:
        return str(result)

    for method_name in (
        "export_to_markdown",
        "export_to_text",
        "to_markdown",
        "to_text",
    ):
        method = getattr(document, method_name, None)
        if callable(method):
            try:
                value = method()
                if isinstance(value, str) and value.strip():
                    return value
            except Exception:
                continue

    return str(document)


def _extract_docx_text(file_path: Path) -> str:
    """Extract plain text from DOCX file bytes."""

    try:
        with zipfile.ZipFile(file_path, "r") as archive:
            xml_bytes = archive.read("word/document.xml")
    except Exception as exc:
        raise ProfileImportExtractionError("Failed to parse DOCX file.") from exc

    xml_text = xml_bytes.decode("utf-8", errors="ignore")

    # Preserve paragraph/table boundaries before XML tag stripping.
    xml_text = re.sub(r"</w:p>", "\n", xml_text)
    xml_text = re.sub(r"</w:tr>", "\n", xml_text)
    xml_text = re.sub(r"<w:br\s*/>", "\n", xml_text)
    xml_text = re.sub(r"<w:tab\s*/>", " ", xml_text)
    xml_text = re.sub(r"<w:cr\s*/>", "\n", xml_text)

    text = _strip_xml_tags(xml_text)
    return _normalize_multiline_text(text)


def _extract_pdf_text(file_path: Path) -> str:
    """Extract readable text from PDF bytes using fallback heuristics."""

    pypdf_text = _extract_pdf_text_with_pypdf(file_path)
    if pypdf_text:
        return pypdf_text

    data = file_path.read_bytes()
    chunks = re.findall(rb"\(([^\)]{1,500})\)\s*Tj", data)

    if chunks:
        text_parts = [chunk.decode("latin-1", errors="ignore") for chunk in chunks]
        return _normalize_multiline_text("\n".join(text_parts))

    printable = re.findall(rb"[A-Za-z0-9@._+\-/]{3,}", data)
    text = " ".join(part.decode("latin-1", errors="ignore") for part in printable)
    if not text.strip():
        raise ProfileImportExtractionError("Failed to parse PDF file.")
    return _normalize_multiline_text(text)


def _extract_pdf_text_with_pypdf(file_path: Path) -> str:
    """Extract text from PDF using pypdf when available.

    Args:
        file_path: PDF file path.

    Returns:
        Extracted PDF text, or empty string when unavailable.
    """

    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except Exception:
        return ""

    try:
        reader = PdfReader(str(file_path))
    except Exception:
        return ""

    parts: list[str] = []
    for page in reader.pages:
        raw_text = ""
        try:
            raw_text = page.extract_text(extraction_mode="layout") or ""
        except TypeError:
            raw_text = page.extract_text() or ""
        except Exception:
            continue

        cleaned = _normalize_multiline_text(raw_text)
        if cleaned:
            parts.append(cleaned)

    return "\n\n".join(parts)


def _strip_xml_tags(xml_text: str) -> str:
    """Strip XML tags from text and compact whitespace."""

    text = re.sub(r"<[^>]+>", " ", xml_text)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    return text


def _fetch_html_default(url: str) -> str:
    """Fetch one HTML page via HTTP.

    Uses TLS verification by default and retries once without certificate
    verification when the failure is specifically a certificate validation issue.
    Falls back to ``http://`` when the provided ``https://`` endpoint cannot be
    reached.

    Args:
        url: URL to fetch.

    Returns:
        Response HTML body.

    Raises:
        ProfileImportExtractionError: If the page cannot be fetched.
    """

    try:
        return _fetch_html_with_verify(url=url, verify=True)
    except ProfileImportExtractionError as primary_error:
        if _is_tls_verification_error(primary_error):
            try:
                return _fetch_html_with_verify(url=url, verify=False)
            except ProfileImportExtractionError:
                pass

        parsed = urlparse(url)
        if parsed.scheme == "https":
            http_url = urlunparse(parsed._replace(scheme="http"))
            return _fetch_html_with_verify(url=http_url, verify=True)

        raise primary_error


def _fetch_html_with_verify(*, url: str, verify: bool) -> str:
    """Fetch HTML with explicit TLS verification behavior.

    Args:
        url: URL to fetch.
        verify: TLS verification toggle.

    Returns:
        Response HTML body.

    Raises:
        ProfileImportExtractionError: If HTTP request fails.
    """

    try:
        with httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            headers=_DEFAULT_FETCH_HEADERS,
            verify=verify,
        ) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        raise ProfileImportExtractionError(f"Failed to fetch URL: {url} ({exc})") from exc

    if response.status_code >= 400:
        raise ProfileImportExtractionError(f"URL returned HTTP {response.status_code}: {url}")

    return response.text


def _is_tls_verification_error(error: BaseException) -> bool:
    """Return whether an exception likely indicates TLS verification failure.

    Args:
        error: Exception instance.

    Returns:
        True when error text matches certificate verification failures.
    """

    lowered = str(error).lower()
    patterns = (
        "certificate verify failed",
        "self signed certificate",
        "unable to get local issuer certificate",
        "tlsv",
    )
    return any(pattern in lowered for pattern in patterns)


def _is_trafilatura_available() -> bool:
    """Return whether Trafilatura import is available."""

    try:
        import trafilatura  # type: ignore[import-not-found] # noqa: F401
    except Exception:
        return False
    return True


def _extract_website_text(*, html: str, url: str) -> str:
    """Extract clean page text with Trafilatura fallback."""

    try:
        import trafilatura  # type: ignore[import-not-found]

        extracted = trafilatura.extract(
            html,
            url=url,
            include_links=False,
            include_comments=False,
            output_format="txt",
        )
        if isinstance(extracted, str) and extracted.strip():
            return _normalize_multiline_text(extracted)
    except Exception:
        pass

    parser = _HtmlTextParser()
    parser.feed(html)
    parser.close()
    fallback_text = "\n".join(parser.parts)
    return _normalize_multiline_text(fallback_text)


def _extract_same_domain_links(*, html: str, base_url: str, domain: str) -> list[str]:
    """Extract unique same-domain links from HTML page."""

    parser = _HtmlLinkParser()
    parser.feed(html)
    parser.close()

    links: list[str] = []
    seen: set[str] = set()
    normalized_domain = domain.lower()
    for href in parser.links:
        absolute = _normalize_url(urljoin(base_url, href))
        if not absolute:
            continue
        parsed = urlparse(absolute)
        if parsed.netloc.lower() != normalized_domain:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
    return links


def _normalize_url(url: str) -> str:
    """Normalize and validate URL for crawling.

    Supports bare domains by defaulting to ``https://``.

    Args:
        url: Raw URL input.

    Returns:
        Normalized absolute URL or empty string when invalid.
    """

    candidate = url.strip()
    if not candidate:
        return ""

    parsed = urlparse(candidate)
    if not parsed.scheme:
        parsed = urlparse(f"https://{candidate}")

    if parsed.scheme not in {"http", "https"}:
        return ""
    if not parsed.netloc:
        return ""
    if any(char.isspace() for char in parsed.netloc):
        return ""

    normalized = parsed._replace(fragment="", query="")
    return urlunparse(normalized)


def _normalize_multiline_text(text: str) -> str:
    """Normalize multi-line extracted text while preserving structure.

    Args:
        text: Raw extracted text.

    Returns:
        Cleaned newline-separated text.
    """

    lines = [normalize_text(line) for line in text.splitlines()]
    compact_lines: list[str] = []
    for line in lines:
        if not line:
            continue
        if _is_noise_line(line):
            continue
        if compact_lines and compact_lines[-1] == line:
            continue
        compact_lines.append(line)
    return "\n".join(compact_lines)


def _is_noise_line(line: str) -> bool:
    """Return whether extracted line is likely navigation or boilerplate noise.

    Args:
        line: Normalized line text.

    Returns:
        True when line should be skipped from extracted content.
    """

    lowered = line.lower()
    if any(
        marker in lowered
        for marker in (
            "skip to",
            "toggle menu",
            "powered by",
            "document.documentelement",
            "no-js",
            "primary navigation",
            "footer",
        )
    ):
        return True

    return False


class _HtmlTextParser(HTMLParser):
    """Simple HTML-to-text parser fallback."""

    def __init__(self) -> None:
        """Initialize parser state."""

        super().__init__()
        self.parts: list[str] = []
        self._suppressed_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track block and suppressed tags for text extraction."""

        lowered = tag.lower()
        if lowered in _SUPPRESSED_TAGS:
            self._suppressed_depth += 1
            return

        if lowered in _BLOCK_BREAK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """Close block and suppressed tags for text extraction."""

        lowered = tag.lower()
        if lowered in _SUPPRESSED_TAGS:
            if self._suppressed_depth > 0:
                self._suppressed_depth -= 1
            return

        if lowered in _BLOCK_BREAK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        """Append non-empty text segments."""

        if self._suppressed_depth > 0:
            return

        cleaned = normalize_text(data)
        if cleaned:
            self.parts.append(cleaned)


class _HtmlLinkParser(HTMLParser):
    """Simple anchor-link parser for same-domain crawling."""

    def __init__(self) -> None:
        """Initialize parser state."""

        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Capture link href values from anchor tags."""

        if tag.lower() != "a":
            return

        href = ""
        for key, value in attrs:
            if key.lower() == "href" and value:
                href = value
                break

        if not href:
            return
        if href.startswith("javascript:") or href.startswith("mailto:"):
            return
        self.links.append(href)
