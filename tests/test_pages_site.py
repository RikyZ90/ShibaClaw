"""Dependency-free checks for the public GitHub Pages artifact."""

from html.parser import HTMLParser
from html import unescape
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

from scripts.build_pages import ASSETS, ROOT, SITE_URL, build_pages


class PageParser(HTMLParser):
    def __init__(self, source: str):
        super().__init__()
        self.tags: list[tuple[str, dict]] = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class PagesSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "site", self.root / "site")
        (self.root / "assets").mkdir()
        for name in ASSETS:
            shutil.copyfile(ROOT / "assets" / name, self.root / "assets" / name)
        self.output = build_pages(self.root)
        self.page = PageParser((self.output / "index.html").read_text(encoding="utf-8"))

    def test_build_allowlist_and_stale_file_cleanup(self):
        sibling = self.output.parent / "keep.txt"
        sibling.write_text("another build", encoding="utf-8")
        for directory in (self.root, self.root / "site", self.root / "assets", self.output):
            (directory / "private.env").write_text("must not be published", encoding="utf-8")
        build_pages(self.root)
        actual = {p.relative_to(self.output).as_posix() for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(actual, {
            "index.html", "styles.css", "site.js", "desktop-preview.webp", "mobile-preview.webp",
            ".nojekyll", "sitemap.xml",
            "assets/shibaclaw_64.png", "assets/shibaclaw_256.png",
            "assets/shibdemo.webp", "assets/shibmobiledemo.webp",
        })
        self.assertEqual(sibling.read_text(encoding="utf-8"), "another build")
        for name in ASSETS:
            self.assertEqual((self.output / "assets" / name).read_bytes(),
                             (self.root / "assets" / name).read_bytes())

    def test_missing_input_preserves_previous_build(self):
        (self.root / "assets" / "shibdemo.webp").unlink()
        before = (self.output / "index.html").read_bytes()
        with self.assertRaises(FileNotFoundError):
            build_pages(self.root)
        self.assertEqual((self.output / "index.html").read_bytes(), before)

    def test_links_images_and_project_path(self):
        ids = [attrs["id"] for _, attrs in self.page.tags if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate HTML ids")
        urls = [attrs[key] for _, attrs in self.page.tags
                for key in ("href", "src", "data-demo", "data-preview") if key in attrs]
        css = (self.output / "styles.css").read_text(encoding="utf-8")
        urls += [match.strip(" \"'") for match in re.findall(r"url\(([^)]+)\)", css)]
        for url in urls:
            with self.subTest(url=url):
                parsed = urlsplit(urljoin(SITE_URL, url))
                self.assertIn(parsed.scheme, ("https", "mailto"))
                if parsed.netloc != urlsplit(SITE_URL).netloc:
                    continue
                self.assertTrue(parsed.path.startswith("/ShibaClaw/"), "Link escapes project prefix")
                relative = unquote(parsed.path.removeprefix("/ShibaClaw/")) or "index.html"
                self.assertTrue((self.output / relative).is_file(), f"Missing local target: {relative}")
                if parsed.fragment and relative == "index.html":
                    self.assertIn(unquote(parsed.fragment), ids)
        for tag, attrs in self.page.tags:
            if tag == "img":
                self.assertIn("alt", attrs)
                self.assertTrue(attrs.get("width"))
                self.assertTrue(attrs.get("height"))
                self.assertNotIn(attrs.get("src"), ("assets/shibdemo.webp", "assets/shibmobiledemo.webp"))
            if attrs.get("target") == "_blank":
                self.assertIn("noopener", attrs.get("rel", "").split())
        self.assertFalse(any(tag == "base" for tag, _ in self.page.tags))
        self.assertTrue(any(tag == "script" and attrs.get("src") == "site.js"
                            and "defer" in attrs for tag, attrs in self.page.tags))
        self.assertEqual({attrs["data-demo"] for _, attrs in self.page.tags if "data-demo" in attrs},
                         {"assets/shibdemo.webp", "assets/shibmobiledemo.webp"})

    def test_search_metadata(self):
        tags = self.page.tags
        self.assertTrue(any(tag == "html" and attrs.get("lang") for tag, attrs in tags))
        self.assertRegex((self.output / "index.html").read_text(encoding="utf-8"),
                         r"<title>[^<]+</title>")
        metadata = {attrs.get("name", attrs.get("property")): attrs.get("content")
                    for tag, attrs in tags if tag == "meta"}
        for name in ("description", "viewport", "og:title", "og:description", "og:image"):
            self.assertTrue(metadata.get(name), f"Missing metadata: {name}")
        self.assertEqual(metadata.get("og:url"), SITE_URL)
        self.assertEqual([attrs.get("href") for tag, attrs in tags
                          if tag == "link" and attrs.get("rel") == "canonical"], [SITE_URL])
        image = urlsplit(metadata["og:image"])
        self.assertEqual(image.scheme, "https")
        self.assertTrue(image.path.startswith("/ShibaClaw/assets/"))
        self.assertTrue((self.output / image.path.removeprefix("/ShibaClaw/")).is_file())
        sitemap = ET.parse(self.output / "sitemap.xml")
        self.assertEqual(sitemap.findtext(".//{*}loc"), SITE_URL)

    def test_install_commands_are_complete_and_match_readme(self):
        source = (self.output / "index.html").read_text(encoding="utf-8")
        commands = dict(re.findall(r'<code id="([^"]+)">(.*?)</code>', source, re.S))
        buttons = {attrs["data-copy"] for _, attrs in self.page.tags if "data-copy" in attrs}
        self.assertEqual(buttons, {"install-windows", "install-unix", "install-docker", "install-pip"})
        self.assertTrue(buttons.issubset(commands))
        readme_lines = {line.split(" #", 1)[0].rstrip()
                        for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines()}
        for target in buttons:
            for line in unescape(commands[target]).splitlines():
                self.assertIn(line, readme_lines, f"Command differs from the README: {target}")
        self.assertEqual(len(commands["install-docker"].splitlines()), 2)
        self.assertEqual(len(commands["install-pip"].splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
