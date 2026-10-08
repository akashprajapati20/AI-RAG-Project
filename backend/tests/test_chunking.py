from app.chunking import chunk_document, split_text
from app.loaders import LoadedDocument, Section


def test_short_text_is_a_single_piece():
    assert split_text("Hello world.", size=100, overlap=10) == ["Hello world."]


def test_pieces_fit_size_and_keep_every_word():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 40 for i in range(20))
    pieces = split_text(text, size=300, overlap=50)
    assert len(pieces) > 1
    assert all(len(p) <= 300 for p in pieces)
    assert set(" ".join(pieces).split()) == set(text.split())


def test_long_paragraph_splits_between_sentences_with_overlap():
    text = " ".join(f"Sentence number {i} is here." for i in range(40))
    pieces = split_text(text, size=200, overlap=60)
    assert all(p.endswith(".") for p in pieces)  # never cut mid-sentence
    for previous, current in zip(pieces, pieces[1:]):
        first_sentence = current.split(". ")[0]
        assert first_sentence in previous  # each piece starts with the tail of the previous one


def test_small_sections_are_merged_with_headings_inline():
    doc = LoadedDocument("Doc", [Section("A", "alpha text", page=1), Section("B", "beta text", page=2)])
    [chunk] = chunk_document(doc, size=500, overlap=50)
    assert chunk.text == "A\n\nalpha text\n\nB\n\nbeta text"
    assert chunk.headings == ["A", "B"]
    assert chunk.pages == [1, 2]


def test_section_continuing_on_next_page_is_stitched_without_repeating_heading():
    doc = LoadedDocument("Doc", [Section("A", "first half", page=1), Section("A", "second half", page=2)])
    [chunk] = chunk_document(doc, size=500, overlap=50)
    assert chunk.text == "A\n\nfirst half\n\nsecond half"


def test_every_chunk_of_a_long_section_starts_with_its_heading():
    doc = LoadedDocument("Doc", [Section("Policy", "\n\n".join(["x " * 100] * 5))])
    chunks = chunk_document(doc, size=300, overlap=0)
    assert len(chunks) > 1
    assert all(c.text.startswith("Policy\n\n") for c in chunks)
