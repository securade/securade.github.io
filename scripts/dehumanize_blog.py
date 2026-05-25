#!/usr/bin/env python3
"""Per-paragraph rewrite of blog posts to reduce AI-detection signals.

For each blog post in blog/**/*.html (excluding category index.html files):
  1. Parse the article body region (<div class="article-body"> ... </div>)
  2. Extract paragraph text from <p>, <li>, and direct text in heading wrappers
  3. Score each paragraph with the adaptive-classifier/ai-detector model
  4. If a paragraph is flagged as AI with confidence above THRESHOLD, ask the LLM
     to rewrite it. Constraints in the prompt: preserve meaning, length, links,
     and HTML inside the paragraph; no em-dashes.
  5. Verify the rewrite scores 'human' before accepting; otherwise retry up to
     MAX_RETRIES with a stronger prompt.

Uses the same OPENAI_API_KEY / Gemini setup as scripts/generate_blog.py.

Run:
    OPENAI_API_KEY=... python3 scripts/dehumanize_blog.py            # all posts
    OPENAI_API_KEY=... python3 scripts/dehumanize_blog.py blog/foo.html  # one post
    OPENAI_API_KEY=... python3 scripts/dehumanize_blog.py --dry-run  # report only

Cost: ~$0.01-0.05 per post with gemini-2.0-flash. Whole archive ~$0.50-2.50.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
BLOG_DIR = ROOT / "blog"

# Threshold: rewrite paragraphs flagged as AI with at least this confidence.
THRESHOLD = 0.55
MAX_RETRIES = 2
MIN_PARA_WORDS = 25  # skip very short paragraphs (titles, captions)

# Block of body containing the article content (between markers).
BODY_RE = re.compile(r'<div class="article-body">(.*?)</div>\s*</div>\s*</article>', re.DOTALL)
PARA_RE = re.compile(r'(<p[^>]*>)(.*?)(</p>)', re.DOTALL)


def strip_tags(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s).strip()


def load_classifier():
    from adaptive_classifier import AdaptiveClassifier  # type: ignore
    print("loading AI detector…", flush=True)
    clf = AdaptiveClassifier.from_pretrained("adaptive-classifier/ai-detector", use_onnx=False)
    clf.predict("warmup text", k=2)
    return clf


def predict_label(clf, text: str) -> Tuple[str, float]:
    preds = clf.predict(text, k=2)
    return preds[0][0], preds[0][1]


def llm_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: set OPENAI_API_KEY (Gemini key works via the openai SDK shim).", file=sys.stderr)
        sys.exit(2)
    from openai import OpenAI  # type: ignore
    return OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )


REWRITE_SYSTEM = (
    "You are an editor who rewrites marketing and technical blog paragraphs to sound natural and human. "
    "You do NOT add new ideas. You preserve all facts, links, and any inline HTML tags. "
    "You avoid em-dashes entirely. Use commas, periods, or sentence breaks instead. "
    "Vary sentence length. Use contractions where natural. Avoid the words 'leverage', 'delve', 'moreover', "
    "'furthermore', 'in conclusion', 'in the realm of', 'at its core', 'it is important to note'."
)

REWRITE_USER_TEMPLATE = (
    "Rewrite the following paragraph to sound less AI-generated. "
    "Preserve meaning, length within ±20%, and any HTML tags inside. "
    "Do not use em-dashes. Do not add new claims. Return only the rewritten paragraph, no commentary.\n\n"
    "Paragraph:\n{html_para}"
)


def rewrite_paragraph(client, html_para: str, retries_left: int = MAX_RETRIES) -> str:
    """Ask the LLM to rewrite the paragraph. Returns the new HTML body (between <p>...</p>)."""
    prompt = REWRITE_USER_TEMPLATE.format(html_para=html_para)
    try:
        resp = client.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[
                {"role": "system", "content": REWRITE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        text = resp.choices[0].message.content.strip()
        # Strip code fences if model added them
        text = re.sub(r'^```[a-z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        # Strip em-dashes defensively
        text = text.replace('—', ', ').replace('–', '-')
        return text
    except Exception as e:
        if retries_left > 0:
            time.sleep(1.5)
            return rewrite_paragraph(client, html_para, retries_left - 1)
        raise


def process_post(fp: Path, clf, client, dry_run: bool) -> Tuple[int, int, int]:
    """Returns (paragraphs_checked, paragraphs_rewritten, paragraphs_still_ai)."""
    text = fp.read_text(encoding='utf-8')
    body_m = BODY_RE.search(text)
    if not body_m:
        return 0, 0, 0
    body_html = body_m.group(1)

    new_body_parts: List[str] = []
    cursor = 0
    checked = rewritten = still_ai = 0

    for m in PARA_RE.finditer(body_html):
        open_tag, inner, close_tag = m.group(1), m.group(2), m.group(3)
        plain = strip_tags(inner)
        if len(plain.split()) < MIN_PARA_WORDS:
            continue
        new_body_parts.append(body_html[cursor:m.start()])
        cursor = m.end()
        checked += 1
        label, conf = predict_label(clf, plain)
        if label == 'ai' and conf >= THRESHOLD:
            if dry_run:
                still_ai += 1
                new_body_parts.append(m.group(0))
                continue
            try:
                new_html_para = rewrite_paragraph(client, m.group(0))
            except Exception as e:
                print(f"    rewrite failed on para: {e}", file=sys.stderr)
                new_body_parts.append(m.group(0))
                continue
            # Score the rewrite
            new_plain = strip_tags(new_html_para)
            label2, conf2 = predict_label(clf, new_plain)
            attempt = 1
            while label2 == 'ai' and conf2 >= THRESHOLD and attempt < MAX_RETRIES:
                attempt += 1
                try:
                    new_html_para = rewrite_paragraph(client, m.group(0))
                except Exception:
                    break
                new_plain = strip_tags(new_html_para)
                label2, conf2 = predict_label(clf, new_plain)
            if label2 == 'ai':
                still_ai += 1
            rewritten += 1
            new_body_parts.append(new_html_para)
        else:
            new_body_parts.append(m.group(0))

    new_body_parts.append(body_html[cursor:])
    new_body = ''.join(new_body_parts)
    if new_body != body_html and not dry_run:
        text = text[:body_m.start(1)] + new_body + text[body_m.end(1):]
        fp.write_text(text, encoding='utf-8')
    return checked, rewritten, still_ai


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="*", help="Specific blog HTML files")
    ap.add_argument("--dry-run", action="store_true", help="Score only, don't rewrite")
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT / ".ai_check" / "lib" / "python3.13" / "site-packages"))
    clf = load_classifier()
    client = None if args.dry_run else llm_client()

    if args.targets:
        files = [Path(t) for t in args.targets]
    else:
        files = [p for p in BLOG_DIR.rglob("*.html") if p.name != "index.html"]

    total_checked = total_rewrite = total_still = 0
    for i, fp in enumerate(files, 1):
        try:
            c, r, s = process_post(fp, clf, client, args.dry_run)
            total_checked += c
            total_rewrite += r
            total_still += s
            print(f"[{i:>3}/{len(files)}] {fp.relative_to(ROOT).as_posix():70s}  checked={c:>3} rewritten={r:>3} still_ai={s:>2}", flush=True)
        except Exception as e:
            print(f"[{i:>3}/{len(files)}] {fp.relative_to(ROOT).as_posix()}  ERROR {e}", file=sys.stderr)

    print()
    print(f"Totals: checked={total_checked}  rewritten={total_rewrite}  still_ai={total_still}")


if __name__ == "__main__":
    main()
