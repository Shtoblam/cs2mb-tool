"""Static contract tests for the local app interface."""

from __future__ import annotations

import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_HTML = ROOT / "app" / "index.html"


class DocumentContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.tags: dict[str, list[dict[str, str | None]]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        element_id = values.get("id")
        if element_id:
            self.ids.append(element_id)
        self.tags.setdefault(tag, []).append(values)


class AppUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = APP_HTML.read_text(encoding="utf-8")
        cls.parser = DocumentContractParser()
        cls.parser.feed(cls.source)

    def test_document_ids_are_unique(self) -> None:
        counts = Counter(self.parser.ids)
        duplicates = sorted(element_id for element_id, count in counts.items() if count > 1)
        self.assertEqual(duplicates, [])

    def test_brand_logo_and_favicon_use_the_local_png_asset(self) -> None:
        favicons = [
            attrs for attrs in self.parser.tags.get("link", [])
            if "icon" in (attrs.get("rel") or "").split()
        ]
        self.assertEqual(len(favicons), 1)
        self.assertEqual(favicons[0].get("href"), "/logo.png")
        logos = [
            attrs for attrs in self.parser.tags.get("img", [])
            if attrs.get("src") == "/logo.png"
        ]
        self.assertEqual(len(logos), 1)
        self.assertEqual(logos[0].get("width"), "34")
        self.assertEqual(logos[0].get("height"), "34")

    def test_viewer_is_available_separately_and_preview_is_opt_in(self) -> None:
        anchors = [
            attrs for attrs in self.parser.tags.get("a", [])
            if attrs.get("id") == "viewer-link"
        ]
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0].get("target"), "_blank")
        self.assertIn("noopener", (anchors[0].get("rel") or "").split())

        viewer_wrappers = [
            attrs for attrs in self.parser.tags.get("div", [])
            if attrs.get("id") == "viewer-wrap"
        ]
        self.assertEqual(len(viewer_wrappers), 1)
        self.assertIn("hidden", viewer_wrappers[0])


if __name__ == "__main__":
    unittest.main()
