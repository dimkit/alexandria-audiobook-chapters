import os
import posixpath
import re
import zipfile
from html import unescape
from html.parser import HTMLParser
from xml.etree import ElementTree as ET


_WHITESPACE_RE = re.compile(r"\s+")
_PARAGRAPH_BREAK_RE = re.compile(r"\n\s*\n+")
_TOC_TITLE_RE = re.compile(r"^(table\s+of\s+contents|contents|toc)\W*$", re.IGNORECASE)


def _normalize_text(text):
    return _WHITESPACE_RE.sub(" ", (text or "").strip())


def _count_words(text):
    return len(re.findall(r"\b\w+\b", text or "", re.UNICODE))


def split_text_into_paragraphs(text):
    paragraphs = []
    for part in _PARAGRAPH_BREAK_RE.split(text or ""):
        normalized = _normalize_text(part)
        if normalized:
            paragraphs.append(normalized)
    return paragraphs


def _looks_like_toc_title(value):
    return bool(_TOC_TITLE_RE.match(_normalize_text(value)))


def _is_table_of_contents_chapter(parsed, title, chapter_text):
    candidates = []
    if title:
        candidates.append(title)
    candidates.extend(parsed.get("headings") or [])

    first_block = chapter_text.split("\n\n", 1)[0] if chapter_text else ""
    if first_block:
        candidates.append(first_block)

    return any(_looks_like_toc_title(candidate) for candidate in candidates)


class _HtmlTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "body", "caption", "dd", "div",
        "dl", "dt", "figcaption", "figure", "footer", "form", "h1", "h2", "h3",
        "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre",
        "section", "table", "td", "th", "tr", "ul",
    }
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
    SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.headings = []
        self.title_parts = []
        self._text_parts = []
        self._heading_parts = None
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = True
            return
        if tag == "br":
            self._flush_block()
            return
        if tag in self.BLOCK_TAGS:
            self._flush_block()
        if tag in self.HEADING_TAGS:
            self._heading_parts = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = False
            return
        if tag in self.HEADING_TAGS:
            heading = _normalize_text("".join(self._heading_parts or []))
            if heading:
                self.headings.append(heading)
            self._heading_parts = None
            self._flush_block()
            return
        if tag in self.BLOCK_TAGS:
            self._flush_block()

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        self._text_parts.append(data)
        if self._heading_parts is not None:
            self._heading_parts.append(data)

    def _flush_block(self):
        text = _normalize_text(unescape("".join(self._text_parts)))
        self._text_parts = []
        if text and (not self.blocks or self.blocks[-1] != text):
            self.blocks.append(text)

    def finalize(self):
        self._flush_block()
        title = _normalize_text(unescape("".join(self.title_parts)))
        return {
            "text": "\n\n".join(self.blocks).strip(),
            "headings": self.headings,
            "title": title,
        }


def _load_text_document(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return {
        "type": "text",
        "title": os.path.splitext(os.path.basename(path))[0],
        "chapters": [{
            "title": None,
            "text": text,
        }],
    }


def _resolve_zip_path(base_path, relative_path):
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_path), relative_path))


def _parse_opf(zip_file, opf_path):
    package = ET.fromstring(zip_file.read(opf_path))
    manifest = {}
    for item in package.findall(".//{*}manifest/{*}item"):
        item_id = item.attrib.get("id")
        if not item_id:
            continue
        manifest[item_id] = {
            "href": item.attrib.get("href", ""),
            "media_type": item.attrib.get("media-type", ""),
            "properties": item.attrib.get("properties", ""),
        }

    spine = []
    for itemref in package.findall(".//{*}spine/{*}itemref"):
        spine.append({
            "idref": itemref.attrib.get("idref"),
            "linear": itemref.attrib.get("linear", "yes"),
        })

    title = ""
    title_node = package.find(".//{*}metadata/{*}title")
    if title_node is not None and title_node.text:
        title = _normalize_text(title_node.text)

    return title, manifest, spine


def _extract_epub_chapters(path):
    chapters = []
    with zipfile.ZipFile(path) as zip_file:
        container = ET.fromstring(zip_file.read("META-INF/container.xml"))
        rootfile = container.find(".//{*}rootfile")
        if rootfile is None or not rootfile.attrib.get("full-path"):
            raise ValueError("Invalid EPUB: missing package document")
        opf_path = rootfile.attrib["full-path"]

        book_title, manifest, spine = _parse_opf(zip_file, opf_path)

        for index, spine_item in enumerate(spine, start=1):
            if spine_item.get("linear", "yes") == "no":
                continue
            manifest_item = manifest.get(spine_item.get("idref"))
            if not manifest_item:
                continue
            href = manifest_item.get("href") or ""
            media_type = (manifest_item.get("media_type") or "").lower()
            properties = set((manifest_item.get("properties") or "").split())
            if "nav" in properties:
                continue
            if media_type not in {"application/xhtml+xml", "text/html", "application/xml"}:
                continue

            item_path = _resolve_zip_path(opf_path, href)
            try:
                raw = zip_file.read(item_path)
            except KeyError:
                continue
            html_text = raw.decode("utf-8", errors="replace")
            extractor = _HtmlTextExtractor()
            extractor.feed(html_text)
            parsed = extractor.finalize()
            chapter_text = parsed["text"].strip()
            if _count_words(chapter_text) < 3:
                continue

            title = parsed["headings"][0] if parsed["headings"] else parsed["title"]
            if not title:
                title = os.path.splitext(os.path.basename(href))[0].replace("_", " ").replace("-", " ").strip()
            title = title or f"Chapter {index}"

            if _is_table_of_contents_chapter(parsed, title, chapter_text):
                continue

            chapters.append({
                "title": title,
                "text": chapter_text,
            })

    if not chapters:
        raise ValueError("No readable chapter content found in EPUB")

    return {
        "type": "epub",
        "title": os.path.splitext(os.path.basename(path))[0],
        "book_title": book_title,
        "chapters": chapters,
    }


def load_source_document(path):
    extension = os.path.splitext(path)[1].lower()
    if extension == ".epub":
        return _extract_epub_chapters(path)
    return _load_text_document(path)


def iter_document_paragraphs(source_document):
    """Yield source paragraphs in story order."""
    for chapter in source_document.get("chapters", []):
        chapter_title = chapter.get("title")
        for paragraph in split_text_into_paragraphs(chapter.get("text") or ""):
            yield {
                "chapter": chapter_title,
                "text": paragraph,
            }
