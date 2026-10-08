"""Build the sample knowledge base: data/sources/ -> data/corpus/.

The corpus describes Brindlewave, a fictional company, so the LLM cannot answer from its
training data — any correct answer has to come from retrieval.

- *.pdf.md files are rendered to PDF, with a running header/footer like real company PDFs
  (ingestion has to cope with that repeated noise).
- .md and .txt files are copied as-is.

Usage (from backend/):  python -m scripts.generate_corpus
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path

import markdown
from fpdf import FPDF, TextStyle

from app.config import PROJECT_ROOT

SOURCES = PROJECT_ROOT / "data" / "sources"
CORPUS = PROJECT_ROOT / "data" / "corpus"

# The built-in PDF fonts are Latin-1 only (no "€"), so embed a Unicode TTF. These ship with macOS.
FONT_DIR = Path("/System/Library/Fonts/Supplemental")
FONT_FILES = {"": "Arial.ttf", "B": "Arial Bold.ttf", "I": "Arial Italic.ttf"}

NAVY = (22, 45, 84)
GREY = (120, 120, 120)


class CompanyPDF(FPDF):
    def __init__(self, title: str):
        super().__init__(format="A4")
        self.doc_title = title
        for style, filename in FONT_FILES.items():
            self.add_font("body", style, FONT_DIR / filename)
        self.set_margins(20, 20, 20)
        self.set_auto_page_break(auto=True, margin=20)
        self.set_title(title)
        self.set_author("Brindlewave B.V.")
        # Fixed date so regenerating produces identical files.
        self.set_creation_date(datetime(2026, 9, 15, tzinfo=timezone.utc))

    def header(self):
        self.set_font("body", size=8)
        self.set_text_color(*GREY)
        self.cell(0, 6, "Brindlewave B.V. | Internal")
        self.set_x(self.l_margin)
        self.cell(0, 6, self.doc_title, align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("body", size=8)
        self.set_text_color(*GREY)
        self.cell(0, 10, f"Confidential - for internal use only | Page {self.page_no()} of {{nb}}", align="C")


def render_pdf(source: Path, target: Path) -> int:
    text = source.read_text(encoding="utf-8")
    title = text.splitlines()[0].removeprefix("# ").strip()
    html = markdown.markdown(text, extensions=["tables"])

    pdf = CompanyPDF(title)
    pdf.add_page()
    pdf.set_font("body", size=10)
    pdf.set_text_color(30, 30, 30)
    pdf.write_html(
        html,
        font_family="body",
        table_line_separators=True,
        li_prefix_color=NAVY,
        # Margins are multiples of the font size, not millimetres.
        tag_styles={
            "h1": TextStyle(font_family="body", font_style="B", font_size_pt=18, color=NAVY, t_margin=0, b_margin=0.5),
            "h2": TextStyle(font_family="body", font_style="B", font_size_pt=13, color=NAVY, t_margin=1, b_margin=0.3),
            "h3": TextStyle(font_family="body", font_style="B", font_size_pt=11, color=NAVY, t_margin=0.8, b_margin=0.2),
        },
    )
    pdf.output(str(target))
    return pdf.pages_count


def main() -> None:
    missing = [f for f in FONT_FILES.values() if not (FONT_DIR / f).exists()]
    if missing:
        raise SystemExit(f"Missing fonts in {FONT_DIR}: {missing}. Edit FONT_DIR to point at Unicode TTF fonts.")

    CORPUS.mkdir(parents=True, exist_ok=True)
    for source in sorted(SOURCES.iterdir()):
        if source.name.endswith(".pdf.md"):
            target = CORPUS / source.name.removesuffix(".md")
            pages = render_pdf(source, target)
            print(f"  PDF   {target.name}  ({pages} pages)")
        elif source.suffix in {".md", ".txt"}:
            shutil.copy2(source, CORPUS / source.name)
            print(f"  copy  {source.name}")

    print(f"Corpus written to {CORPUS.relative_to(PROJECT_ROOT)}/")


if __name__ == "__main__":
    main()
