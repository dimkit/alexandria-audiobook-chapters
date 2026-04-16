import os
import tempfile
import unittest
import zipfile

from source_document import iter_document_paragraphs, load_source_document, split_text_into_paragraphs


def _write_test_epub(path, toc_heading="Table of Contents"):
    with zipfile.ZipFile(path, "w") as epub:
        epub.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        epub.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test Book</dc:title>
  </metadata>
  <manifest>
    <item id="toc" href="toc.xhtml" media-type="application/xhtml+xml"/>
    <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="toc"/>
    <itemref idref="chapter1"/>
  </spine>
</package>""",
        )
        epub.writestr(
            "OEBPS/toc.xhtml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{toc_heading}</title></head>
  <body>
    <h1>{toc_heading}</h1>
    <p>Chapter One</p>
    <p>Chapter Two</p>
    <p>Chapter Three</p>
  </body>
</html>""",
        )
        epub.writestr(
            "OEBPS/chapter1.xhtml",
            """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Chapter One</title></head>
  <body>
    <h1>Chapter One</h1>
    <p>This is the first real chapter with enough words to keep.</p>
  </body>
</html>""",
        )


class SourceDocumentEpubTests(unittest.TestCase):
    def test_drops_table_of_contents_chapter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            epub_path = os.path.join(temp_dir, "book.epub")
            _write_test_epub(epub_path)

            source = load_source_document(epub_path)

            self.assertEqual(source["type"], "epub")
            self.assertEqual(len(source["chapters"]), 1)
            self.assertEqual(source["chapters"][0]["title"], "Chapter One")

    def test_drops_contents_variant_chapter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            epub_path = os.path.join(temp_dir, "book.epub")
            _write_test_epub(epub_path, toc_heading="Contents")

            source = load_source_document(epub_path)

            self.assertEqual(len(source["chapters"]), 1)
            self.assertEqual(source["chapters"][0]["title"], "Chapter One")

    def test_split_text_into_paragraphs_discards_blank_sections(self):
        paragraphs = split_text_into_paragraphs("First block.\n\n  \nSecond block.\n\nThird block.")
        self.assertEqual(paragraphs, ["First block.", "Second block.", "Third block."])

    def test_iter_document_paragraphs_preserves_chapter_order(self):
        document = {
            "chapters": [
                {"title": "One", "text": "Alpha.\n\nBeta."},
                {"title": "Two", "text": "Gamma."},
            ]
        }

        paragraphs = list(iter_document_paragraphs(document))

        self.assertEqual(
            paragraphs,
            [
                {"chapter": "One", "text": "Alpha."},
                {"chapter": "One", "text": "Beta."},
                {"chapter": "Two", "text": "Gamma."},
            ],
        )


@unittest.skipUnless(__import__("importlib").util.find_spec("docx") is not None, "python-docx not installed")
class SourceDocumentDocxTests(unittest.TestCase):
    @staticmethod
    def _write_docx(path, paragraph_specs):
        from docx import Document

        doc = Document()
        for text, style in paragraph_specs:
            p = doc.add_paragraph(text)
            if style:
                p.style = style
        doc.save(path)

    def test_uses_most_frequent_heading_level_for_chapters(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = os.path.join(temp_dir, "book.docx")
            self._write_docx(
                docx_path,
                [
                    ("Book Title", "Heading 1"),
                    ("Preface line", None),
                    ("Scene 1", "Heading 2"),
                    ("Scene one body.", None),
                    ("Scene 2", "Heading 2"),
                    ("Scene two body.", None),
                    ("Subnote", "Heading 3"),
                    ("Trailing body.", None),
                ],
            )

            source = load_source_document(docx_path)

            self.assertEqual(source["type"], "docx")
            self.assertEqual(len(source["chapters"]), 2)
            self.assertEqual(source["chapters"][0]["title"], "Scene 1")
            self.assertIn("Scene one body.", source["chapters"][0]["text"])
            self.assertEqual(source["chapters"][1]["title"], "Scene 2")
            self.assertIn("Scene two body.", source["chapters"][1]["text"])

    def test_heading_tie_prefers_h1(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = os.path.join(temp_dir, "book.docx")
            self._write_docx(
                docx_path,
                [
                    ("Chapter A", "Heading 1"),
                    ("A body.", None),
                    ("Section A.1", "Heading 2"),
                    ("Ignored as chapter break body.", None),
                    ("Chapter B", "Heading 1"),
                    ("B body.", None),
                    ("Section B.1", "Heading 2"),
                    ("More B body.", None),
                ],
            )

            source = load_source_document(docx_path)

            self.assertEqual([c["title"] for c in source["chapters"]], ["Chapter A", "Chapter B"])

    def test_no_headings_falls_back_to_single_chapter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = os.path.join(temp_dir, "book.docx")
            self._write_docx(
                docx_path,
                [
                    ("First paragraph.", None),
                    ("Second paragraph.", None),
                ],
            )

            source = load_source_document(docx_path)

            self.assertEqual(source["type"], "docx")
            self.assertEqual(len(source["chapters"]), 1)
            self.assertIsNone(source["chapters"][0]["title"])
            self.assertIn("First paragraph.", source["chapters"][0]["text"])
            self.assertIn("Second paragraph.", source["chapters"][0]["text"])


if __name__ == "__main__":
    unittest.main()
