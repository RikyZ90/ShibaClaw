# ShibaClaw landing page

This is a static public landing page. It does not run the ShibaClaw application.

From the repository root, use Python 3.12 or newer; no packages are needed:

```sh
python -m unittest discover -s tests -p test_pages_site.py -v
python scripts/build_pages.py
python -m http.server 8000 --directory dist
```

Contributors changing demo or command-copy controls also need Node.js 24, without npm packages:

```sh
node --test site/site.test.mjs
```

The static build itself needs only Python. Test files are excluded from its artifact.

Open <http://localhost:8000/pages/> to preview the generated site under a path prefix.
The build replaces only `dist/pages/`, which is already ignored by Git.

The builder copies only `site/index.html`, `site/styles.css`, `site/site.js`,
`site/desktop-preview.webp`, `site/mobile-preview.webp` and these existing assets:

- `assets/shibaclaw_64.png`
- `assets/shibaclaw_256.png`
- `assets/shibdemo.webp`
- `assets/shibmobiledemo.webp`

It also generates `.nojekyll` and `sitemap.xml`. Repository source,
configuration, local data and this README are not included in the published artifact.
Keep asset links relative so deployment works at `/ShibaClaw/`.
The two still previews come from the existing demo images. Original animations
load only when a visitor selects a demo's play button.
Installation commands match the main README. Copy buttons use the browser clipboard
when available; if access is unavailable or denied, they select the command for manual copying.

## GitHub Pages

The intended public URL is <https://rikyz90.github.io/ShibaClaw/>. Canonical and
social metadata in `index.html` and `SITE_URL` in `scripts/build_pages.py` must
agree if the host or repository path changes.

When ready to publish, select **Settings → Pages → Build and deployment → Source →
GitHub Actions** in the repository. This setup step is manual; the workflow does
not enable Pages or change repository settings.

The `GitHub Pages` workflow checks and builds site changes on pull requests and
pushes to `main`. Only a matching push to `main`, or a manual run on `main`, uploads
and deploys the artifact. Pull requests receive no deployment permissions.
Once Pages is configured, use **Actions → GitHub Pages → Run workflow** on `main`
for the first deployment or to rebuild without a source change.

See [GitHub's custom Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
