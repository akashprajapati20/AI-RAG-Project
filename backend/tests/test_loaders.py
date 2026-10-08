"""Loader tests against the generated sample corpus (python -m scripts.generate_corpus)."""

from app.chunking import split_text
from app.config import PROJECT_ROOT
from app.loaders import load_document

CORPUS = PROJECT_ROOT / "data" / "corpus"


def full_text(doc) -> str:
    return "\n".join(s.text for s in doc.sections)


def test_pdf_strips_repeated_header_and_footer():
    text = full_text(load_document(CORPUS / "employee_handbook.pdf"))
    assert "Brindlewave B.V. | Internal" not in text
    assert "Confidential" not in text


def test_single_page_pdf_strips_header_by_font_size():
    # Only one page, so the header can't be detected by repetition.
    text = full_text(load_document(CORPUS / "hr_policy_update_2026.pdf"))
    assert "Brindlewave B.V. | Internal" not in text
    assert "Confidential" not in text


def test_pdf_headings_and_pages():
    doc = load_document(CORPUS / "pricing_and_plans_2026.pdf")
    assert doc.title == "Tally Pricing and Plans 2026"
    assert doc.metadata == {"format": "pdf", "pages": 2}
    headings = [s.heading for s in doc.sections]
    assert headings[:3] == ["", "1. Plans", "2. Billing and discounts"]
    free_trial = next(s for s in doc.sections if s.heading == "5. Free trial")
    assert free_trial.page == 2
    assert "30 days" in free_trial.text


def test_pdf_section_split_by_page_break_keeps_its_heading():
    doc = load_document(CORPUS / "employee_handbook.pdf")
    expenses = [s for s in doc.sections if s.heading == "7. Expenses and travel"]
    assert [s.page for s in expenses] == [1, 2]


def test_pdf_title_wrapped_over_two_lines_is_one_heading():
    doc = load_document(CORPUS / "postmortem_INC-2026-031.pdf")
    headings = [s.heading for s in doc.sections]
    assert headings[:3] == ["", "1. Summary", "2. Root cause"]
    assert "EU Region" not in headings


def section(doc, heading):
    return next(s for s in doc.sections if s.heading == heading)


def test_pdf_rejoins_lines_wrapped_at_the_margin():
    sick_leave = section(load_document(CORPUS / "employee_handbook.pdf"), "3. Sick leave")
    assert "\n" not in sick_leave.text  # 4 printed lines -> 1 paragraph
    assert "on the first day of absence" in sick_leave.text  # this phrase spanned a line break


def test_pdf_keeps_bullets_and_table_rows_on_their_own_lines():
    parental = section(load_document(CORPUS / "employee_handbook.pdf"), "4. Parental leave").text.splitlines()
    assert parental[1].startswith("• Primary caregivers")
    assert parental[2].startswith("• Secondary caregivers")
    plans = section(load_document(CORPUS / "pricing_and_plans_2026.pdf"), "1. Plans").text.splitlines()
    assert "Uptime SLA 99.5% 99.9% 99.95%" in plans


def test_long_pdf_paragraph_is_split_between_sentences():
    # Before paragraphs were rejoined, split_text fell back to printed lines and cut mid-sentence.
    sick_leave = section(load_document(CORPUS / "employee_handbook.pdf"), "3. Sick leave")
    pieces = split_text(sick_leave.text, size=200, overlap=50)
    assert len(pieces) > 1
    assert all(p.endswith(".") for p in pieces)


def test_markdown_title_and_heading_paths():
    doc = load_document(CORPUS / "api_reference.md")
    assert doc.title == "Tally Cloud REST API Reference (v2)"
    headings = [s.heading for s in doc.sections]
    assert "Endpoints > GET /forecasts/{tag_id}" in headings
    assert "Webhooks" in headings


def test_markdown_ignores_hash_lines_inside_code_blocks(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# Title\n\n## Real\n\n```\n# not a heading\n```\n")
    doc = load_document(path)
    assert [s.heading for s in doc.sections] == ["Real"]
    assert "# not a heading" in doc.sections[0].text


def test_text_file_uses_first_line_as_title():
    doc = load_document(CORPUS / "product_meeting_notes_2026-09-10.txt")
    assert doc.title == "PRODUCT & ROADMAP SYNC — meeting notes"
    assert full_text(doc).startswith("Date: Thursday 10 September 2026")
