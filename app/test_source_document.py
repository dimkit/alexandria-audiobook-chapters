import os
import tempfile
import unittest
import zipfile

from source_document import load_source_document


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


if __name__ == "__main__":
    unittest.main()
