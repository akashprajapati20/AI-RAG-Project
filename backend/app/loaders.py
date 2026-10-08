"""Turn PDF, Markdown and plain-text files into a title plus a list of clean sections."""

import math
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PageObject, PdfReader


@dataclass
class Section:
    heading: str  # e.g. "4. SLA credits" or "Endpoints > GET /sites"; "" before the first heading
    text: str
    page: int | None = None  # 1-based page number (PDFs only)


@dataclass
class LoadedDocument:
    title: str
    sections: list[Section]
    metadata: dict = field(default_factory=dict)


def load_document(path: Path) -> LoadedDocument:
    loader = LOADERS.get(path.suffix.lower())
    if loader is None:
        raise ValueError(f"Unsupported file type: {path.name}")
    return loader(path)


# ---------------------------------------------------------------- Markdown

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def load_markdown(path: Path) -> LoadedDocument:
    """Split on headings. Each section's heading is its full path, e.g. "Endpoints > GET /sites"."""
    title = None
    sections: list[Section] = []
    headings: dict[int, str] = {}  # heading level -> text, for the current position in the file
    buffer: list[str] = []
    in_code_block = False

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            sections.append(Section(heading=" > ".join(headings[lvl] for lvl in sorted(headings)), text=text))
        buffer.clear()

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_code_block = not in_code_block
        match = None if in_code_block else _MD_HEADING.match(line)
        if not match:
            buffer.append(line)
            continue

        flush()
        level, text = len(match.group(1)), match.group(2).replace("`", "").strip()
        if level == 1 and title is None:
            title = text  # the first H1 is the document title, not a section
            continue
        headings = {lvl: h for lvl, h in headings.items() if lvl < level}
        headings[level] = text
    flush()

    return LoadedDocument(title=title or _title_from_filename(path), sections=sections, metadata={"format": "markdown"})


# ---------------------------------------------------------------- Plain text


def load_text(path: Path) -> LoadedDocument:
    """One section; a short first line (common in notes) becomes the title."""
    text = path.read_text(encoding="utf-8").strip()
    first_line, _, rest = text.partition("\n")
    if len(first_line) <= 100 and rest.strip():
        title, body = first_line.strip(), rest.strip()
    else:
        title, body = _title_from_filename(path), text
    return LoadedDocument(title=title, sections=[Section(heading="", text=body)], metadata={"format": "text"})


# ---------------------------------------------------------------- PDF
#
# pypdf gives us plain text lines, plus (via a visitor callback) each text run with its font size.
# Font size lets us tell structure apart without guessing from wording:
#   - headings are set in a noticeably larger font than body text,
#   - running headers/footers are set in a smaller font, sit at the page edges, and repeat.
# Printed lines are then rejoined into paragraphs (see _join_wrapped_lines), so each line of a
# section's text is a whole paragraph, list item or table row, never a fragment of a sentence.

EDGE_LINES = 2  # how many lines at the top and bottom of a page can be header/footer
_PAGE_NUMBER = re.compile(r"^(page\s*)?\d+(\s*(of|/)\s*\d+)?$", re.IGNORECASE)
_LIST_ITEM = re.compile(r"^([•▪◦*\-–]|\d+[.)]|[a-z][.)])\s")  # "• x", "- x", "3. x", "2) x", "a) x"


def load_pdf(path: Path) -> LoadedDocument:
    reader = PdfReader(path)
    pages = [_read_pdf_page(page) for page in reader.pages]

    # Body font size = the size that covers the most characters.
    chars_per_size: Counter[float] = Counter()
    for _, runs in pages:
        for text, size in runs:
            chars_per_size[size] += len(text)
    body_size = chars_per_size.most_common(1)[0][0] if chars_per_size else 0.0
    repeated = _repeated_edge_lines(pages)

    # Full line width in characters ~ the 90th-percentile line length. A printed line at least
    # 85% that long most likely ran into the right margin and continues on the next line.
    lengths = sorted(len(line) for lines, _ in pages for line in lines)
    wrap_width = 0.85 * lengths[int(0.9 * (len(lengths) - 1))] if lengths else math.inf

    title = (reader.metadata.title if reader.metadata else None) or _title_from_filename(path)
    sections: list[Section] = []
    heading = ""

    for page_no, (lines, runs) in enumerate(pages, start=1):
        small = [text for text, size in runs if size < body_size - 0.5]
        large = [text for text, size in runs if size > body_size * 1.15]
        buffer: list[str] = []
        previous_was_heading = False

        for i, line in enumerate(lines):
            at_edge = i < EDGE_LINES or i >= len(lines) - EDGE_LINES
            if at_edge and (_normalize(line) in repeated or _PAGE_NUMBER.match(line) or _made_of(line, small)):
                continue  # running header / footer / page number
            if _made_of(line, large):
                if previous_was_heading:
                    heading = f"{heading} {line}"  # a long heading wrapped onto the next line
                else:
                    _add_section(sections, heading, _join_wrapped_lines(buffer, wrap_width), page_no, title)
                    buffer = []
                    heading = line
                previous_was_heading = True
                continue
            previous_was_heading = False
            buffer.append(line)

        # Close the section at the page break; if it continues, the next page starts a new
        # Section with the same heading, which the chunker stitches back together.
        _add_section(sections, heading, _join_wrapped_lines(buffer, wrap_width), page_no, title)

    return LoadedDocument(title=title, sections=sections, metadata={"format": "pdf", "pages": len(pages)})


def _read_pdf_page(page: PageObject) -> tuple[list[str], list[tuple[str, float]]]:
    """Return the page's text lines, and every text run with its rendered font size."""
    runs: list[tuple[str, float]] = []

    def visit(text, cm, tm, font_dict, font_size):
        if text.strip():
            # Rendered size = nominal size scaled by the text matrix (tm) and page transform (cm).
            scale = math.hypot(tm[2], tm[3]) * math.hypot(cm[2], cm[3])
            runs.append((_squash(text), round(font_size * scale, 1)))

    text = page.extract_text(visitor_text=visit)
    lines = [squashed for line in text.splitlines() if (squashed := _squash(line))]
    return lines, runs


def _repeated_edge_lines(pages: list[tuple[list[str], list]]) -> set[str]:
    """Normalised lines found at the top/bottom of at least half the pages (and at least 2)."""
    counts: Counter[str] = Counter()
    for lines, _ in pages:
        counts.update({_normalize(line) for line in lines[:EDGE_LINES] + lines[-EDGE_LINES:]})
    threshold = max(2, len(pages) / 2)
    return {line for line, n in counts.items() if n >= threshold}


def _made_of(line: str, runs: list[str]) -> bool:
    """True if the line consists only of text from these runs (e.g. only large-font text)."""
    rest = line
    for run in sorted(runs, key=len, reverse=True):
        rest = rest.replace(run, " ")
    return bool(line) and not rest.strip()


def _join_wrapped_lines(lines: list[str], wrap_width: float) -> list[str]:
    """Rejoin printed lines that only broke because the text reached the right margin.

    A line that (nearly) fills the width was wrapped mid-paragraph, so the next line continues
    it; a shorter line ends a paragraph, list item or table row. Bullets and numbered items
    always start a new line. Without this, the chunker would split PDF text at printed line
    ends, i.e. in the middle of sentences.
    """
    joined: list[str] = []
    previous = ""
    for line in lines:
        if joined and len(previous) >= wrap_width and not _LIST_ITEM.match(line):
            joined[-1] += ("" if joined[-1].endswith("-") else " ") + line
        else:
            joined.append(line)
        previous = line
    return joined


def _add_section(sections: list[Section], heading: str, lines: list[str], page: int, title: str) -> None:
    text = "\n".join(lines).strip()
    if text:
        # Text under the document title itself (the intro) has no section heading.
        sections.append(Section(heading="" if heading == title else heading, text=text, page=page))


def _normalize(line: str) -> str:
    """Lower-case with digits masked, so "Page 1 of 3" and "Page 2 of 3" compare equal."""
    return re.sub(r"\d+", "#", line.lower())


# ---------------------------------------------------------------- helpers


def _squash(text: str) -> str:
    return " ".join(text.split())


def _title_from_filename(path: Path) -> str:
    return path.stem.replace("_", " ").strip().capitalize()


LOADERS: dict[str, Callable[[Path], LoadedDocument]] = {
    ".pdf": load_pdf,
    ".md": load_markdown,
    ".markdown": load_markdown,
    ".txt": load_text,
}
