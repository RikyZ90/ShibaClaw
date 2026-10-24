"""Build the public landing page without application files or dependencies."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://rikyz90.github.io/ShibaClaw/"
ASSETS = ("shibaclaw_64.png", "shibaclaw_256.png", "shibdemo.webp", "shibmobiledemo.webp")
SITE_FILES = ("index.html", "styles.css", "site.js", "desktop-preview.webp", "mobile-preview.webp")


def build_pages(root: Path = ROOT) -> Path:
    root = root.resolve()
    output = root / "dist" / "pages"
    sources = [(root / "site" / name, name) for name in SITE_FILES]
    sources += [(root / "assets" / name, f"assets/{name}") for name in ASSETS]
    for source, _ in sources:
        if not source.is_file():
            raise FileNotFoundError(source)
    # Only replace this build's directory, including stale files from earlier builds.
    if output.resolve() != output:
        raise ValueError("The Pages output must not resolve through a symbolic link")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / "assets").mkdir()
    for source, destination in sources:
        shutil.copyfile(source, output / destination)
    (output / ".nojekyll").touch()
    (output / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{SITE_URL}</loc></url>\n</urlset>\n",
        encoding="utf-8",
    )
    return output


if __name__ == "__main__":
    print(f"Pages built in {build_pages()}")
