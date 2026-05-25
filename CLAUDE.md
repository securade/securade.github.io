# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This is the **securade.ai** marketing/content website, served as a static site by GitHub Pages (`CNAME` → `securade.ai`). There is no build step, no bundler, no test suite — every `.html` file in the repo is the file that ships. Edits to HTML are deployed by merging to `main`.

The Python under `scripts/` is **not** part of the site; it is automation that generates content into this repo (run via GitHub Actions or manually).

## Layout that matters

- Root-level pages (`index.html`, `safety-copilot.html`, `resources.html`, `page2.html`, `page3.html`, `privacy.html`, `tos.html`, `billing.html`, `subscribe.html`, `404.html`) — the main site.
- `blog/` — blog posts organized into category subdirectories (`technology/`, `workplace-safety/`, `industry-solutions/`, `best-practices/`). Each category has its own `index.html` listing its posts.
- `assets/` — CSS, JS, images. CSS is Bootstrap 5.0.0-beta2 + custom `main.css`. Blog images live under `assets/images/blog/<category>/`.
- `templates/blog_template.html` — Jinja2 template consumed only by `scripts/generate_blog.py`. Do not link to it from the site (it is excluded from the sitemap).
- `sitemap.xml` — auto-generated, do not hand-edit (see workflow below).

## HTML conventions

Blog posts and pages use Bootstrap 5 utility classes. When editing or generating blog content, match the existing style — these classes are load-bearing for layout, not decorative:
- Paragraphs: `<p class="fs-5 mb-4">`
- Section headings: `<h2 class="fw-bolder mb-4 mt-5">`, subsections `<h3 class="fw-bolder mb-4 mt-5">`
- Images: `<figure class="mb-4"><img class="img-fluid rounded" ...></figure>`
- CTA links: `<a href="..." class="text-body-emphasis fw-bold">`

Blog pages reference assets via `../../assets/...` (two levels up from `blog/<category>/post.html`). Root-level pages use `assets/...`.

## Automation

### Blog generation (`scripts/generate_blog.py`)
Triggered by `.github/workflows/generate-blog-post.yml` when a GitHub issue is opened with a title starting `Create a new blog on `. The script:
1. Parses the issue title (topic) and body (description + markdown image links).
2. Calls Gemini (via the OpenAI SDK pointed at `generativelanguage.googleapis.com/v1beta/openai/`, model `gemini-2.0-flash`) to pick a category, generate SEO meta + HTML body, name images, and produce an SEO-optimized filename.
3. Downloads issue images, re-encodes to JPEG, names them `securadeai<CamelCase>.jpeg`.
4. Renders via `templates/blog_template.html`, writes to `blog/<category>/<slug>.html` and images to `assets/images/blog/<category>/`.
5. Updates the category `index.html` via `category_utils.update_category_indexes` and opens a PR on branch `blog-<title-slug>`.

Required env: `GITHUB_TOKEN`, `OPENAI_API_KEY` (used as the Gemini key), `ISSUE_NUMBER`, `REPO`. When changing the LLM call, update both `generate_blog_content` (writes the post) and `generate_seo_title_and_filename` (chooses the filename) — the filename comes from a separate LLM call after content is generated, not from the issue title.

### Sitemap (`.github/workflows/sitemap-generation.yml`)
Runs on every push to `main` that touches `**.html` or `**.pdf`. Uses `cicirello/generate-sitemap` and opens a PR from branch `create-pull-request/sitemap`. Excluded paths are hardcoded in the workflow: `/templates /scripts /404.html /tos.html /privacy.html /billing.html /subscribe.html`. If you add a page that should be excluded (or stop excluding one), edit the workflow's `exclude-paths`.

### `scripts/process.py`
Manual SEO tooling, not wired to any workflow. Two modes:
- `python scripts/process.py -s sitemap.xml` — scrapes URLs from the sitemap and prints internal-linking opportunities (uses spaCy `en_core_web_lg` + TF-IDF cosine similarity).
- `python scripts/process.py -f <folder> [--add-header] [--add-footer] [-o out.html]` — bulk-injects the standard header/footer HTML defined inline in `process.py` into all HTML files in a folder.

## Local setup for the Python scripts

```
python -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt
bash scripts/post_install.sh   # downloads spaCy en_core_web_lg model (only needed for process.py)
```

`.venv` and `scripts/__pycache__/` are gitignored. There is no test suite, no linter config, and no build command.

## Things to be careful about

- **Do not edit `sitemap.xml` by hand** — the workflow will overwrite it and open a competing PR.
- **Category names are slugs** chosen by the LLM at blog-creation time. Existing slugs are discovered by listing subdirs of `blog/`, so the set grows organically. If you rename a category directory, also update any in-page links in the category's `index.html` and any cross-links from other posts.
- **The `OPENAI_API_KEY` secret actually holds a Gemini key** — the OpenAI SDK is pointed at Google's OpenAI-compatible endpoint. Don't "fix" this back to OpenAI without changing the `base_url` and `MODEL` in `generate_blog.py`.
- **Hero image is `processed_images[0]`** and is intentionally not placeholder-substituted in the body — only images 1..N are inlined via `{{image_N}}` placeholders. Off-by-one changes here will break image rendering in generated posts.
