"""Split loaded documents into heading-aware chunks sized for embedding and retrieval."""

import re
from dataclasses import dataclass

from app.loaders import LoadedDocument

# Coarsest boundary first: paragraph, line, sentence, word. Each is (split pattern, joiner).
_SEPARATORS = [
    (re.compile(r"\n\s*\n"), "\n\n"),
    (re.compile(r"\n"), "\n"),
    (re.compile(r"(?<=[.!?])\s+"), " "),
    (re.compile(r"\s+"), " "),
]


@dataclass
class Chunk:
    text: str  # chunk body, with section headings written inline
    headings: list[str]  # sections this chunk covers, in order
    pages: list[int]  # PDF pages this chunk covers (empty for other formats)

    @property
    def metadata(self) -> dict:
        return {"headings": self.headings, "pages": self.pages}


def chunk_document(doc: LoadedDocument, size: int, overlap: int) -> list[Chunk]:
    """Pack consecutive sections into chunks of about `size` characters.

    Small neighbouring sections are merged so chunks aren't too thin to be useful; sections longer
    than `size` are split with split_text(). Every chunk starts with the heading of its first
    section, so it still makes sense when retrieved on its own.
    """
    pieces = [
        (section.heading, section.page, part)
        for section in doc.sections
        for part in split_text(section.text, size, overlap)
    ]

    chunks: list[Chunk] = []
    current: list[tuple[str, int | None, str]] = []
    for piece in pieces:
        if current and len(_render(current + [piece])) > size:
            chunks.append(_make_chunk(current))
            current = []
        current.append(piece)
    if current:
        chunks.append(_make_chunk(current))
    return chunks


def split_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into pieces of at most `size` characters.

    Breaks at the coarsest boundary available (paragraph, line, sentence, word). Each piece starts
    with up to `overlap` characters from the end of the previous one, so a fact that straddles a
    boundary is still intact in at least one piece.
    """
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []

    pattern, joiner = next(((p, j) for p, j in _SEPARATORS if p.search(text)), (None, ""))
    if pattern is None:  # a single enormous "word": hard cut
        step = max(size - overlap, 1)
        return [text[i : i + size] for i in range(0, len(text), step)]

    units: list[str] = []
    for unit in pattern.split(text):
        units.extend(split_text(unit, size, overlap) if len(unit) > size else [unit])

    pieces: list[str] = []
    window: list[str] = []
    for unit in units:
        if window and len(joiner.join(window + [unit])) > size:
            pieces.append(joiner.join(window))
            window = _tail(window, joiner, overlap)
            while window and len(joiner.join(window + [unit])) > size:
                window.pop(0)
        window.append(unit)
    pieces.append(joiner.join(window))
    return [p.strip() for p in pieces if p.strip()]


def _tail(units: list[str], joiner: str, max_chars: int) -> list[str]:
    """The trailing units whose combined length is at most max_chars (the overlap)."""
    tail: list[str] = []
    for unit in reversed(units):
        if len(joiner.join([unit] + tail)) > max_chars:
            break
        tail.insert(0, unit)
    return tail


def _render(pieces: list[tuple[str, int | None, str]]) -> str:
    """Join pieces, writing a section's heading on its own line where that section starts."""
    parts: list[str] = []
    previous_heading = None
    for heading, _, text in pieces:
        if heading and heading != previous_heading:
            parts.append(heading)
        parts.append(text)
        previous_heading = heading
    return "\n\n".join(parts)


def _make_chunk(pieces: list[tuple[str, int | None, str]]) -> Chunk:
    return Chunk(
        text=_render(pieces),
        headings=list(dict.fromkeys(h for h, _, _ in pieces if h)),
        pages=sorted({p for _, p, _ in pieces if p is not None}),
    )
