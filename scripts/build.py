#!/usr/bin/env python3
"""Securade.ai site build script.

Processes every .html file in the repo and replaces partial markers with rendered
content from _partials/. Each page can declare metadata in an @page block.

Usage:
    python scripts/build.py           # build all pages
    python scripts/build.py --check   # exit 1 if build would change anything
    python scripts/build.py path/...  # build only specified files

Markers:
    <!-- @page
    title: ...
    description: ...
    @endpage -->

    <!-- @partial:NAME -->
        ...rendered content (managed by build)...
    <!-- @endpartial:NAME -->

    {{token}} substitution happens inside partials, using @page metadata.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARTIALS_DIR = ROOT / "_partials"
SITE_URL = "https://securade.ai"

DEFAULT_OG_IMAGE = "/assets/images/og-default.png"
DEFAULT_OG_TYPE = "website"

# Files / directories that are NOT pages to template.
EXCLUDE_DIRS = {".git", "node_modules", "scripts", "_partials", "templates", ".github", "assets", "images"}
EXCLUDE_FILES: set[str] = set()  # add bare names if needed

# Marker regexes
PAGE_BLOCK_RE = re.compile(r"<!--\s*@page\s*(.*?)\s*@endpage\s*-->", re.DOTALL)
PARTIAL_RE = re.compile(
    r"<!--\s*@partial:([a-zA-Z0-9_\-]+)\s*-->"
    r"(.*?)"
    r"<!--\s*@endpartial:\1\s*-->",
    re.DOTALL,
)
PARTIAL_START_RE = re.compile(r"<!--\s*@partial:([a-zA-Z0-9_\-]+)\s*-->")
CARDS_RE = re.compile(
    r"<!--\s*@cards:([a-zA-Z0-9_\-]+)\s*-->"
    r"(.*?)"
    r"<!--\s*@endcards:\1\s*-->",
    re.DOTALL,
)
CARDS_START_RE = re.compile(r"<!--\s*@cards:([a-zA-Z0-9_\-]+)\s*-->")
TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_\.]+)\s*\}\}")


def collect_blog_posts() -> list[dict]:
    """Walk blog/ and return a list of post metadata dicts, sorted by date desc."""
    posts: list[dict] = []
    blog_dir = ROOT / "blog"
    if not blog_dir.exists():
        return posts
    for fp in blog_dir.rglob("*.html"):
        if fp.name == "index.html":
            continue
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception:
            continue
        if "@partial:" not in text:
            continue
        meta = parse_page_block(text)
        if not meta:
            continue
        rel = fp.relative_to(ROOT).as_posix()
        url = "/" + rel
        # Extract date from extra_schema JSON if available, else from filesystem
        date_iso = ""
        m = re.search(r'"datePublished"\s*:\s*"([0-9\-]+)"', meta.get("extra_schema", ""))
        if m:
            date_iso = m.group(1)
        if not date_iso:
            date_iso = datetime.fromtimestamp(fp.stat().st_mtime).strftime("%Y-%m-%d")
        parts = rel.split("/")
        # @page `category` metadata overrides path-based detection (for posts at /blog/foo.html
        # that should appear under a category in the filter but keep their URL).
        category_slug = meta.get("category", "").strip()
        if not category_slug:
            category_slug = parts[1] if len(parts) >= 3 and parts[0] == "blog" else ""
        category_label = category_slug.replace("-", " ").title() if category_slug else "Misc"
        title = re.sub(r"\s*[-—|]\s*Securade\.ai\s*$", "", meta.get("title", "")).strip()
        posts.append({
            "url": url,
            "title": title,
            "description": meta.get("og_description") or meta.get("description", ""),
            "image": meta.get("og_image", "/assets/images/logo/logo.png"),
            "date_iso": date_iso,
            "category_slug": category_slug,
            "category_label": category_label,
        })
    posts.sort(key=lambda p: p["date_iso"], reverse=True)
    return posts


def render_card(post: dict) -> str:
    return (
        f'<a href="{post["url"]}" class="post-card" data-category="{post["category_slug"] or "uncategorized"}">'
        f'<div class="post-card-media"><img src="{post["image"]}" alt="" loading="lazy" width="640" height="360" /></div>'
        f'<div class="post-card-body">'
        f'<span class="post-card-chip">{post["category_label"]}</span>'
        f'<h2 class="post-card-title">{post["title"]}</h2>'
        f'<div class="post-card-meta"><time datetime="{post["date_iso"]}">{post["date_iso"]}</time></div>'
        f'</div></a>'
    )


def render_cards_block(kind: str) -> str:
    posts = collect_blog_posts()
    if kind == "all_posts":
        items = posts
    elif kind == "recent_3":
        items = posts[:3]
    elif kind == "recent_6":
        items = posts[:6]
    elif kind.startswith("category_"):
        slug = kind[len("category_"):].replace("_", "-")
        items = [p for p in posts if p["category_slug"] == slug]
    else:
        return ""
    cards_html = "\n      ".join(render_card(p) for p in items)
    return f'<div class="card-grid" data-post-grid>\n      {cards_html}\n    </div>'


def render_filter_chips() -> str:
    """Generate filter chips for resources page based on actual category counts."""
    posts = collect_blog_posts()
    counts: dict[str, int] = {"all": len(posts)}
    labels: dict[str, str] = {}
    for p in posts:
        slug = p["category_slug"] or "uncategorized"
        counts[slug] = counts.get(slug, 0) + 1
        labels[slug] = p["category_label"] if p["category_slug"] else "Other"
    chips = [f'<button class="filter-chip is-active" data-category="all">All <span class="filter-chip-count">{counts["all"]}</span></button>']
    # Stable ordering
    order = ["technology", "workplace-safety", "industry-solutions", "best-practices", "uncategorized", "misc"]
    for slug in order:
        if slug in counts and slug != "all":
            label = labels.get(slug, slug.replace("-", " ").title())
            if slug in ("uncategorized", "misc"): label = "Misc"
            chips.append(f'<button class="filter-chip" data-category="{slug}">{label} <span class="filter-chip-count">{counts[slug]}</span></button>')
    return '<div class="filter-chips" data-filter-chips>\n      ' + "\n      ".join(chips) + "\n    </div>"


def parse_page_block(text: str) -> dict[str, str]:
    """Parse the @page YAML-lite block into a dict."""
    m = PAGE_BLOCK_RE.search(text)
    if not m:
        # Warn loudly if a page has an opener but no closer — common foot-gun.
        if re.search(r"<!--\s*@page\b", text) and "@endpage" not in text:
            print("  ! WARNING: @page opener found but no @endpage closer; metadata ignored", file=sys.stderr)
        return {}
    body = m.group(1)
    meta: dict[str, str] = {}
    current_key: str | None = None
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        # continuation lines (start with whitespace and we have a current key)
        if line.startswith((" ", "\t")) and current_key is not None:
            meta[current_key] = (meta[current_key] + " " + line.strip()).strip()
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        meta[key] = value
        current_key = key
    return meta


def file_to_canonical_path(file_path: Path) -> str:
    """Map a repo file path to its canonical URL path."""
    rel = file_path.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return "/"
    return "/" + rel


def load_partial(name: str) -> str:
    p = PARTIALS_DIR / f"{name}.html"
    if not p.exists():
        raise FileNotFoundError(f"Partial not found: {p}")
    return p.read_text(encoding="utf-8").rstrip() + "\n"


def render_tokens(template: str, ctx: dict[str, str]) -> str:
    def replace(m: re.Match[str]) -> str:
        key = m.group(1)
        return str(ctx.get(key, ""))
    return TOKEN_RE.sub(replace, template)


def build_context(page_meta: dict[str, str], file_path: Path) -> dict[str, str]:
    canonical_path = page_meta.get("canonical_path") or file_to_canonical_path(file_path)
    canonical_url = SITE_URL + canonical_path

    title = page_meta.get("title", "Securade.ai")
    description = page_meta.get(
        "description",
        "Securade.ai is a generative AI video analytics platform that turns existing CCTV cameras into safety copilots, predicting and preventing workplace accidents.",
    )
    og_title = page_meta.get("og_title", title)
    og_description = page_meta.get("og_description", description)
    og_type = page_meta.get("og_type", DEFAULT_OG_TYPE)
    og_image = page_meta.get("og_image", DEFAULT_OG_IMAGE)
    if og_image.startswith("/"):
        og_image_abs = SITE_URL + og_image
    elif og_image.startswith("http"):
        og_image_abs = og_image
    else:
        og_image_abs = SITE_URL + "/" + og_image.lstrip("./")

    nav_active = page_meta.get("nav_active", "")
    extra_head = page_meta.get("extra_head", "")
    extra_schema = page_meta.get("extra_schema", "")
    robots = page_meta.get("robots", "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1")

    ctx = {
        "title": title,
        "description": description,
        "og_title": og_title,
        "og_description": og_description,
        "og_type": og_type,
        "og_image": og_image,
        "og_image_abs": og_image_abs,
        "canonical_path": canonical_path,
        "canonical_url": canonical_url,
        "year": str(datetime.now().year),
        "today_iso": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "extra_head": extra_head,
        "extra_schema": extra_schema,
        "robots": robots,
        "active_home": "active" if nav_active == "home" else "",
        "active_hub": "active" if nav_active == "hub" else "",
        "active_tower": "active" if nav_active == "tower" else "",
        "active_sentinel": "active" if nav_active == "sentinel" else "",
        "active_resources": "active" if nav_active in ("resources", "blog") else "",
    }
    # Allow @page metadata to override any context key explicitly.
    for k, v in page_meta.items():
        if k not in ctx:
            ctx[k] = v
    return ctx


def replace_partial_blocks(html: str, ctx: dict[str, str]) -> tuple[str, bool]:
    """Replace contents inside each @partial:NAME ... @endpartial:NAME block.

    If a @partial:NAME marker exists without an @endpartial closer, inject the
    rendered partial + a closing marker right after the opener.
    """
    changed = False

    # First, expand bare markers (no closing tag yet) by inserting an
    # @endpartial right after them so the regex below catches them.
    def ensure_close(match: re.Match[str]) -> str:
        name = match.group(1)
        nonlocal changed
        # Check if this opener has a matching closer further down. If yes, leave alone.
        rest = html[match.end():]
        if re.search(rf"<!--\s*@endpartial:{re.escape(name)}\s*-->", rest):
            return match.group(0)
        changed = True
        return f"{match.group(0)}\n<!-- @endpartial:{name} -->"

    html2 = PARTIAL_START_RE.sub(ensure_close, html)

    def render(match: re.Match[str]) -> str:
        nonlocal changed
        name = match.group(1)
        try:
            partial_src = load_partial(name)
        except FileNotFoundError:
            print(f"  ! unknown partial: {name}", file=sys.stderr)
            return match.group(0)
        rendered = render_tokens(partial_src, ctx).rstrip() + "\n"
        # Wrap in original markers with line breaks for readability.
        new_block = f"<!-- @partial:{name} -->\n{rendered}<!-- @endpartial:{name} -->"
        old_block = match.group(0)
        if new_block != old_block:
            changed = True
        return new_block

    out = PARTIAL_RE.sub(render, html2)

    # Now handle @cards:NAME blocks
    def ensure_close_cards(match: re.Match[str]) -> str:
        nonlocal changed
        name = match.group(1)
        rest = out[match.end():]
        if re.search(rf"<!--\s*@endcards:{re.escape(name)}\s*-->", rest):
            return match.group(0)
        changed = True
        return f"{match.group(0)}\n<!-- @endcards:{name} -->"

    out2 = CARDS_START_RE.sub(ensure_close_cards, out)

    def render_cards_match(match: re.Match[str]) -> str:
        nonlocal changed
        name = match.group(1)
        if name == "filter_chips":
            rendered = render_filter_chips()
        else:
            rendered = render_cards_block(name)
        new_block = f"<!-- @cards:{name} -->\n{rendered}\n<!-- @endcards:{name} -->"
        if new_block != match.group(0):
            changed = True
        return new_block

    out2 = CARDS_RE.sub(render_cards_match, out2)
    return out2, changed


def iter_html_files(targets: list[Path] | None = None):
    if targets:
        for t in targets:
            tp = (ROOT / t).resolve() if not t.is_absolute() else t
            if tp.is_file() and tp.suffix == ".html":
                yield tp
            elif tp.is_dir():
                yield from iter_html_files_recursive(tp)
        return
    yield from iter_html_files_recursive(ROOT)


def iter_html_files_recursive(start: Path):
    for dirpath, dirnames, filenames in os.walk(start):
        # Filter excluded directories in-place
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fname in filenames:
            if not fname.endswith(".html"):
                continue
            if fname in EXCLUDE_FILES:
                continue
            yield Path(dirpath) / fname


def process_file(file_path: Path, check: bool = False) -> bool:
    text = file_path.read_text(encoding="utf-8")
    if "@partial:" not in text:
        return False  # not a templated page yet
    page_meta = parse_page_block(text)
    ctx = build_context(page_meta, file_path)
    new_text, changed = replace_partial_blocks(text, ctx)
    if new_text != text:
        if check:
            print(f"  would change: {file_path.relative_to(ROOT)}")
            return True
        file_path.write_text(new_text, encoding="utf-8")
        print(f"  built: {file_path.relative_to(ROOT)}")
        return True
    return False


# Paths that should never appear in sitemap.xml. Matches the previous
# cicirello/generate-sitemap workflow exclusions so search-console state is preserved.
SITEMAP_EXCLUDE_PATHS = {
    "/404.html",
    "/tos.html",
    "/privacy.html",
    "/billing.html",
    "/subscribe.html",
    "/safety-copilot.html",
    "/page2.html",
    "/page3.html",
}
SITEMAP_EXCLUDE_DIRS = {"templates", "scripts", "_partials"}


def build_minified_css(check: bool = False) -> bool:
    """Generate assets/css/theme.min.css from theme.css. Returns True if changed."""
    src_path = ROOT / "assets/css/theme.css"
    dst_path = ROOT / "assets/css/theme.min.css"
    if not src_path.exists():
        return False
    src = src_path.read_text(encoding="utf-8")
    s = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*([{}:;,>])\s*", r"\1", s)
    s = re.sub(r";}", "}", s)
    new_text = s.strip()
    old_text = dst_path.read_text(encoding="utf-8") if dst_path.exists() else ""
    if new_text == old_text:
        return False
    if check:
        print("  would change: assets/css/theme.min.css")
        return True
    dst_path.write_text(new_text, encoding="utf-8")
    print(f"  built: assets/css/theme.min.css ({len(new_text)} bytes)")
    return True


def url_for_html(file_path: Path) -> str:
    rel = file_path.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel


def build_sitemap(check: bool = False) -> bool:
    """Generate sitemap.xml from the current set of HTML pages. Returns True if file changed."""
    urls: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDE_DIRS
            and d not in SITEMAP_EXCLUDE_DIRS
            and not d.startswith(".")
        ]
        for fname in filenames:
            if not fname.endswith(".html"):
                continue
            fp = Path(dirpath) / fname
            url = url_for_html(fp)
            if url in SITEMAP_EXCLUDE_PATHS:
                continue
            mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc)
            lastmod = mtime.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            urls.append((url, lastmod))

    urls.sort(key=lambda u: u[0])
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, lastmod in urls:
        lines.append("<url>")
        lines.append(f"<loc>{SITE_URL}{url}</loc>")
        lines.append(f"<lastmod>{lastmod}</lastmod>")
        lines.append("</url>")
    lines.append("</urlset>")
    new_text = "\n".join(lines) + "\n"

    sitemap_path = ROOT / "sitemap.xml"
    old_text = sitemap_path.read_text(encoding="utf-8") if sitemap_path.exists() else ""
    if new_text == old_text:
        return False
    if check:
        print(f"  would change: sitemap.xml ({len(urls)} urls)")
        return True
    sitemap_path.write_text(new_text, encoding="utf-8")
    print(f"  built: sitemap.xml ({len(urls)} urls)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Build Securade.ai static site")
    parser.add_argument("targets", nargs="*", help="Specific files/dirs to build (defaults to all)")
    parser.add_argument("--check", action="store_true", help="Exit 1 if any file would change")
    parser.add_argument("--no-sitemap", action="store_true", help="Skip sitemap.xml generation")
    args = parser.parse_args()

    targets = [Path(t) for t in args.targets] if args.targets else None
    any_changed = False
    count = 0
    for fp in iter_html_files(targets):
        count += 1
        if process_file(fp, check=args.check):
            any_changed = True

    # CSS minification and sitemap regenerate from the full repo regardless of which
    # files were built; both are derived from many sources.
    if not args.targets:
        if build_minified_css(check=args.check):
            any_changed = True
    if not args.no_sitemap and not args.targets:
        if build_sitemap(check=args.check):
            any_changed = True

    print(f"\nProcessed {count} HTML file(s).")
    if args.check and any_changed:
        print("Build is out of date. Re-run `python scripts/build.py`.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
