#!/usr/bin/env python3
"""One-shot migration: convert old-template blog HTML files to new partials-based structure.

Reads each blog/**/*.html, extracts metadata + article body from the legacy template,
and rewrites the file with @page metadata, partial markers, and new article markup.

Idempotent: skips files that already contain @partial: markers.

Usage:
    python scripts/migrate_blog.py            # migrate all
    python scripts/migrate_blog.py blog/foo.html  # migrate specific file
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG_DIR = ROOT / "blog"

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL | re.IGNORECASE)
META_RE = re.compile(
    r'<meta\s+(?:name|property)\s*=\s*"([^"]+)"\s+content\s*=\s*"([^"]*)"\s*/?>',
    re.IGNORECASE,
)
H1_RE = re.compile(r'<h1[^>]*>(.*?)</h1>', re.DOTALL | re.IGNORECASE)
DATE_AUTHOR_RE = re.compile(
    r'<div[^>]*text-muted[^>]*>\s*Posted on\s+(.*?)\s+by\s+(.*?)\s*</div>',
    re.DOTALL | re.IGNORECASE,
)
FIGURE_RE = re.compile(
    r'<figure[^>]*>\s*<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"[^>]*/?>\s*</figure>',
    re.DOTALL | re.IGNORECASE,
)
ARTICLE_SECTION_RE = re.compile(
    r'<section\s+class="mb-5"\s*>(.*?)</section>',
    re.DOTALL | re.IGNORECASE,
)
# Fallback: grab everything inside the article tag if section isn't found
ARTICLE_FALLBACK_RE = re.compile(r'<article[^>]*>(.*?)</article>', re.DOTALL | re.IGNORECASE)

MONTHS = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12',
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
    'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09',
    'oct': '10', 'nov': '11', 'dec': '12',
}


def parse_date_iso(date_str: str) -> str | None:
    """Parse 'December 29, 2023' or 'Dec 29, 2023' → '2023-12-29'."""
    s = date_str.strip().lower()
    m = re.match(r'([a-z]+)\s+(\d{1,2}),?\s+(\d{4})', s)
    if not m:
        return None
    month = MONTHS.get(m.group(1).lower())
    if not month:
        return None
    return f"{m.group(3)}-{month}-{int(m.group(2)):02d}"


def normalize_image_path(src: str) -> str:
    """Convert relative ../../assets/... or ../assets/... → root-relative /assets/..."""
    src = src.strip()
    if src.startswith("http://") or src.startswith("https://") or src.startswith("//"):
        return src
    # Strip leading ../ segments
    while src.startswith("../"):
        src = src[3:]
    if src.startswith("./"):
        src = src[2:]
    if not src.startswith("/"):
        src = "/" + src
    return src


def rewrite_body_paths(body: str) -> str:
    """Rewrite img src and href paths inside the body to root-relative where reasonable."""
    def fix_src(m: re.Match[str]) -> str:
        return f'src="{normalize_image_path(m.group(1))}"'

    body = re.sub(r'src="((?:\.\./)+assets/[^"]+)"', fix_src, body)
    # Also fix bare leading-slash that the LLM-generated posts use (already root-rel, leave alone)
    return body


def category_label(category_slug: str | None) -> str:
    if not category_slug:
        return "Blog"
    return category_slug.replace("-", " ").title()


def extract_metadata(html: str) -> dict:
    meta: dict = {}
    tm = TITLE_RE.search(html)
    if tm:
        # Title format is usually "X - Securade.ai" or "X | Securade.ai"
        raw_title = unescape(tm.group(1)).strip()
        # Strip " - Securade.ai" suffix if present
        title = re.sub(r'\s*[-|]\s*Securade\.ai\s*$', '', raw_title).strip()
        meta['title'] = title
        meta['raw_title'] = raw_title

    for m in META_RE.finditer(html):
        name = m.group(1).lower()
        content = unescape(m.group(2)).strip()
        if name == 'description':
            meta['description'] = content
        elif name == 'og:title':
            meta['og_title'] = content
        elif name == 'og:description':
            meta['og_description'] = content
        elif name == 'og:image':
            # Drop https://securade.ai prefix to make root-relative
            img = content
            if img.startswith('https://securade.ai'):
                img = img[len('https://securade.ai'):]
            if not img:
                img = '/assets/images/logo/logo.png'
            meta['og_image'] = img
        elif name == 'keywords':
            meta['keywords'] = content
    return meta


def extract_article(html: str, meta: dict) -> dict:
    article: dict = {'body': '', 'hero_img': None, 'hero_alt': '', 'date': '', 'author': 'Arjun Krishnamurthy'}

    h1m = H1_RE.search(html)
    if h1m:
        article['h1'] = re.sub(r'<[^>]+>', '', h1m.group(1)).strip()
    else:
        article['h1'] = meta.get('title', '')

    dam = DATE_AUTHOR_RE.search(html)
    if dam:
        article['date_raw'] = dam.group(1).strip()
        article['date_iso'] = parse_date_iso(dam.group(1)) or ''
        article['author'] = re.sub(r'<[^>]+>', '', dam.group(2)).strip()

    fm = FIGURE_RE.search(html)
    if fm:
        article['hero_img'] = normalize_image_path(fm.group(1))
        article['hero_alt'] = unescape(fm.group(2)).strip()

    sm = ARTICLE_SECTION_RE.search(html)
    if sm:
        body = sm.group(1)
    else:
        am = ARTICLE_FALLBACK_RE.search(html)
        body = am.group(1) if am else ''
        # Strip header/figure if they slipped into the fallback
        body = re.sub(r'<header[^>]*>.*?</header>', '', body, flags=re.DOTALL | re.IGNORECASE)
        body = FIGURE_RE.sub('', body)
    article['body'] = rewrite_body_paths(body).strip()
    return article


def make_new_html(file_path: Path, meta: dict, article: dict) -> str:
    rel = file_path.relative_to(ROOT).as_posix()
    canonical_path = "/" + rel
    # Determine category from path: blog/category/foo.html → category
    parts = rel.split("/")
    category_slug = parts[1] if len(parts) >= 3 and parts[0] == "blog" else None
    category_label_str = category_label(category_slug)

    title = meta.get('title') or article.get('h1') or 'Securade.ai blog post'
    description = meta.get('description') or (article.get('body', '')[:160].replace('\n', ' ').strip() + '…')
    og_title = meta.get('og_title') or title
    og_description = meta.get('og_description') or description
    og_image = meta.get('og_image') or article.get('hero_img') or '/assets/images/logo/logo.png'
    hero_img = article.get('hero_img') or og_image
    hero_alt = article.get('hero_alt') or title
    date_iso = article.get('date_iso') or datetime.now().strftime('%Y-%m-%d')
    date_display = article.get('date_raw') or date_iso
    author = article.get('author') or 'Arjun Krishnamurthy'

    # Breadcrumb
    crumb_parts = [('/', 'Home'), ('/resources.html', 'Resources')]
    if category_slug:
        crumb_parts.append((f"/blog/{category_slug}/", category_label_str))
    breadcrumb_html_parts = []
    crumb_schema_items = []
    for i, (url, label) in enumerate(crumb_parts, start=1):
        breadcrumb_html_parts.append(f'<li><a href="{url}">{label}</a></li>')
        crumb_schema_items.append({
            'position': i, 'name': label, 'item': f'https://securade.ai{url}',
        })
    # Current page in breadcrumb (not linked)
    breadcrumb_html_parts.append(f'<li class="current">{title}</li>')

    # Build Article + BreadcrumbList JSON-LD as extra_schema
    import json
    article_schema = {
        '@type': 'Article',
        '@id': f'https://securade.ai{canonical_path}#article',
        'headline': title,
        'description': description,
        'image': f'https://securade.ai{hero_img}' if hero_img.startswith('/') else hero_img,
        'datePublished': date_iso,
        'dateModified': date_iso,
        'author': {'@type': 'Person', 'name': author},
        'publisher': {'@id': 'https://securade.ai/#organization'},
        'mainEntityOfPage': {'@type': 'WebPage', '@id': f'https://securade.ai{canonical_path}'},
        'inLanguage': 'en',
        'articleSection': category_label_str,
        'keywords': meta.get('keywords', ''),
    }
    breadcrumb_schema = {
        '@type': 'BreadcrumbList',
        '@id': f'https://securade.ai{canonical_path}#breadcrumb',
        'itemListElement': [
            {'@type': 'ListItem', **item} for item in crumb_schema_items
        ],
    }
    extra_schema_json = ',\n    ' + json.dumps(article_schema, ensure_ascii=False) + ',\n    ' + json.dumps(breadcrumb_schema, ensure_ascii=False)

    # Discontinued banner for the safety-copilot post only
    extra_banner = ''
    if file_path.name == 'how-securade-ai-safety-copilot-transforms-worker-safety.html':
        extra_banner = '\n      <div class="banner-discontinued" role="note"><strong>Heads up:</strong> Safety Copilot was an experimental Hugging Face Space demo and is no longer available. Securade.ai HUB, Tower, and Sentinel remain in active development — see <a href="/#platform">the platform</a> or <a href="https://github.com/securade/hub">HUB on GitHub</a>.</div>\n'

    body_indented = '\n'.join('      ' + ln if ln.strip() else '' for ln in article['body'].splitlines())

    new_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<!-- @page
title: {title} — Securade.ai
description: {description}
canonical_path: {canonical_path}
og_title: {og_title}
og_description: {og_description}
og_image: {og_image}
og_type: article
nav_active: resources
extra_schema: {extra_schema_json}
@endpage -->
<!-- @partial:head -->
<!-- @partial:schema-org -->
</head>
<body>
<!-- @partial:header -->

<main id="main">
  <article class="article">
    <div class="container">
      <div class="article-header">
        <ol class="breadcrumbs" aria-label="Breadcrumb">
          {''.join(breadcrumb_html_parts)}
        </ol>
        <span class="article-eyebrow">{category_label_str}</span>
        <h1>{title}</h1>
        <p class="article-meta">
          <span>By {author}</span>
          <span class="dot">·</span>
          <time datetime="{date_iso}">{date_display}</time>
        </p>
      </div>
{extra_banner}      <figure class="article-hero">
        <img src="{hero_img}" alt="{hero_alt}" />
      </figure>

      <div class="article-body">
{body_indented}
      </div>
    </div>
  </article>
</main>

<!-- @partial:footer -->
<!-- @partial:scripts -->
</body>
</html>
'''
    return new_html


def already_migrated(html: str) -> bool:
    return '@partial:head' in html and '@page' in html


def migrate_file(file_path: Path, force: bool = False) -> bool:
    html = file_path.read_text(encoding='utf-8')
    if already_migrated(html) and not force:
        return False
    meta = extract_metadata(html)
    article = extract_article(html, meta)
    if not article['body']:
        print(f"  ! no body found: {file_path.relative_to(ROOT)}", file=sys.stderr)
        return False
    new_html = make_new_html(file_path, meta, article)
    file_path.write_text(new_html, encoding='utf-8')
    print(f"  migrated: {file_path.relative_to(ROOT)}")
    return True


def main():
    args = sys.argv[1:]
    force = False
    if '--force' in args:
        force = True
        args.remove('--force')

    if args:
        targets = [ROOT / a for a in args]
    else:
        targets = list(BLOG_DIR.rglob('*.html'))
        # Skip category index.html — those are listings, not posts
        targets = [t for t in targets if t.name != 'index.html']

    count = 0
    for t in targets:
        if migrate_file(t, force=force):
            count += 1
    print(f"\nMigrated {count}/{len(targets)} file(s).")


if __name__ == '__main__':
    main()
