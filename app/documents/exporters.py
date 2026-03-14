"""File exporters for HTML, PDF, and DOCX document artifacts."""

from __future__ import annotations

import html
import re
import textwrap
import zipfile
from pathlib import Path


def export_html(html_content: str, output_path: Path) -> None:
    """Write rendered HTML content to disk.

    Args:
        html_content: Rendered HTML string.
        output_path: Output path for HTML artifact.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")


def export_pdf(html_content: str, output_path: Path) -> None:
    """Export HTML content to a lightweight single-page PDF.

    Args:
        html_content: Rendered HTML string.
        output_path: Output path for PDF artifact.
    """

    lines = _html_to_text_lines(html_content)
    pdf_bytes = _build_simple_pdf(lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)


def export_docx(html_content: str, output_path: Path) -> None:
    """Export HTML content to a minimal DOCX package.

    Args:
        html_content: Rendered HTML string.
        output_path: Output path for DOCX artifact.
    """

    lines = _html_to_text_lines(html_content)
    document_xml = _build_document_xml(lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _root_relationships_xml())
        archive.writestr("word/document.xml", document_xml)


def _html_to_text_lines(html_content: str) -> list[str]:
    """Convert HTML into readable plain text lines.

    Args:
        html_content: Source HTML string.

    Returns:
        Text line list used for PDF and DOCX export.
    """

    text = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|h1|h2|h3|h4|h5|h6|li|div|section|article)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)

    raw_lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in raw_lines if line]
    return lines


def _build_simple_pdf(lines: list[str]) -> bytes:
    """Build a minimal valid PDF document from text lines.

    Args:
        lines: Text lines to include in PDF content stream.

    Returns:
        Serialized PDF bytes.
    """

    wrapped_lines: list[str] = []
    for line in lines:
        wrapped_lines.extend(textwrap.wrap(line, width=95) or [""])

    text_commands = ["BT", "/F1 10 Tf", "14 TL", "40 800 Td"]
    for line in wrapped_lines:
        safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        text_commands.append(f"({safe_line}) Tj")
        text_commands.append("T*")
    text_commands.append("ET")

    stream = "\n".join(text_commands).encode("latin-1", errors="replace")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    header = b"%PDF-1.4\n"
    body = bytearray(header)
    offsets: list[int] = []

    for index, object_data in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f"{index} 0 obj\n".encode("ascii"))
        body.extend(object_data)
        body.extend(b"\nendobj\n")

    xref_offset = len(body)
    body.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    body.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        body.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    body.extend(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_offset}\n"
            "%%EOF\n"
        ).encode("ascii")
    )

    return bytes(body)


def _build_document_xml(lines: list[str]) -> str:
    """Build minimal WordprocessingML document XML.

    Args:
        lines: Plain text line sequence.

    Returns:
        XML content for ``word/document.xml``.
    """

    paragraphs: list[str] = []
    for line in lines:
        escaped = html.escape(line)
        paragraphs.append(f"<w:p><w:r><w:t xml:space=\"preserve\">{escaped}</w:t></w:r></w:p>")

    if not paragraphs:
        paragraphs.append("<w:p/>")

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:body>"
        + "".join(paragraphs)
        + (
            "<w:sectPr><w:pgSz w:w=\"11906\" w:h=\"16838\"/>"
            "<w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\" "
            "w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/></w:sectPr>"
        )
        + "</w:body></w:document>"
    )


def _content_types_xml() -> str:
    """Return minimal ``[Content_Types].xml`` payload.

    Returns:
        XML content types document.
    """

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/word/document.xml\" "
        "ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
        "</Types>"
    )


def _root_relationships_xml() -> str:
    """Return minimal package relationships XML.

    Returns:
        Root relationships XML payload.
    """

    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" "
        "Target=\"word/document.xml\"/>"
        "</Relationships>"
    )
