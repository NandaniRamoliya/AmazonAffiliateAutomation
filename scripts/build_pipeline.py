import html
import json
import os
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "products.json"
POSTED_FILE = ROOT_DIR / "data" / "posted_ids.json"
DOCS_DIR = ROOT_DIR / "docs"
CARDS_DIR = DOCS_DIR / "cards"

PARTNER_TAG = os.getenv("AMAZON_PARTNER_TAG", "yourtag-21").strip() or "yourtag-21"
MARKETPLACE = os.getenv("AMAZON_MARKETPLACE", "amazon.in").strip() or "amazon.in"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

DISCLOSURE_TEXT = "As an Amazon Associate I earn from qualifying purchases."


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        ]
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def build_affiliate_url(item: dict) -> str:
    """
    Build a compliant Amazon affiliate URL without link cloaking or scraping.
    - If affiliate_url is provided (e.g., amzn.to or amazon.in/...), preserve it
      and ensure ?tag= is set on full Amazon domain URLs.
    - Otherwise construct https://www.<marketplace>/dp/<ASIN>?tag=<partner_tag>.
    """
    raw_url = (item.get("affiliate_url") or "").strip()
    asin = (item.get("asin") or "").strip().upper()

    if raw_url:
        parsed = urlparse(raw_url)
        if "amazon." in parsed.netloc.lower():
            query = parse_qs(parsed.query)
            if "tag" not in query and PARTNER_TAG:
                query["tag"] = [PARTNER_TAG]
            new_query = urlencode(query, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
        return raw_url

    if not asin:
        raise ValueError(f"Product '{item.get('id')}' must have either 'asin' or 'affiliate_url'.")

    return f"https://www.{MARKETPLACE}/dp/{asin}?tag={PARTNER_TAG}"


def slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", text).strip("-").lower() or "item"


def generate_deal_card(item: dict, url: str, out_path: Path) -> None:
    """Render a clean 1080x1080 social media graphic with mandatory #ad disclosure."""
    width, height = 1080, 1080
    img = Image.new("RGB", (width, height), "#0F172A")
    draw = ImageDraw.Draw(img)

    # Outer card container
    draw.rounded_rectangle(
        [(56, 56), (width - 56, height - 56)],
        radius=36,
        fill="#1E293B",
        outline="#334155",
        width=3,
    )

    # Top accent bar
    draw.rounded_rectangle(
        [(56, 56), (width - 56, 76)],
        radius=12,
        fill="#F59E0B",
    )

    font_badge = load_font(28, bold=True)
    font_cat = load_font(26, bold=False)
    font_title = load_font(54, bold=True)
    font_body = load_font(34, bold=False)
    font_cta = load_font(32, bold=True)
    font_disc = load_font(22, bold=False)

    # Category & Badge pills
    category = (item.get("category") or "Featured Pick").upper()
    badge = (item.get("badge") or "Recommended").upper()

    draw.rounded_rectangle([(104, 128), (104 + 280, 184)], radius=24, fill="#F59E0B")
    draw.text((128, 140), badge[:18], font=font_badge, fill="#0F172A")
    draw.text((410, 142), category[:28], font=font_cat, fill="#94A3B8")

    # Title (wrapped)
    title_lines = textwrap.wrap(item.get("title", "Amazon Find"), width=24)[:3]
    y = 240
    for line in title_lines:
        draw.text((104, y), line, font=font_title, fill="#F8FAFC")
        y += 72

    # Divider
    y = max(y + 24, 490)
    draw.line([(104, y), (width - 104, y)], fill="#334155", width=2)
    y += 40

    # Highlight / user commentary
    highlight_lines = textwrap.wrap(item.get("highlight", ""), width=38)[:5]
    for line in highlight_lines:
        draw.text((104, y), line, font=font_body, fill="#CBD5E1")
        y += 48

    # CTA Button
    cta_text = item.get("cta") or "Shop on Amazon"
    draw.rounded_rectangle([(104, 800), (width - 104, 886)], radius=20, fill="#F59E0B")
    draw.text((140, 825), f"{cta_text[:34]}  ->", font=font_cta, fill="#0F172A")

    # Mandatory Amazon Associates Disclosure Footer
    draw.text(
        (104, 932),
        f"#ad  |  {DISCLOSURE_TEXT}",
        font=font_disc,
        fill="#94A3B8",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG", optimize=True)


def build_caption(item: dict, url: str) -> str:
    title = item.get("title", "Amazon Find")
    highlight = item.get("highlight", "").strip()
    category = item.get("category", "Finds")
    tag_slug = re.sub(r"[^a-zA-Z0-9]", "", category) or "AmazonFinds"
    lines = [
        f"{title}",
        "",
        highlight,
        "",
        f"Check it out on Amazon: {url}",
        "",
        f"#ad #{tag_slug} | {DISCLOSURE_TEXT}",
    ]
    return "\n".join(line for line in lines if line is not None)


def generate_html_page(enriched_items: list[dict]) -> None:
    categories = sorted({item["category"] for item in enriched_items})
    cat_buttons = "\n".join(
        f'<button class="filter-btn" data-category="{html.escape(c)}">{html.escape(c)}</button>'
        for c in categories
    )

    cards_html = []
    for item in enriched_items:
        cards_html.append(
            f"""
            <article class="card" data-category="{html.escape(item['category'])}" data-search="{html.escape((item['title'] + ' ' + item['highlight']).lower())}">
              <div class="card-img-wrap">
                <img src="cards/{html.escape(item['card_filename'])}" alt="{html.escape(item['title'])}" loading="lazy" />
              </div>
              <div class="card-body">
                <div class="meta">
                  <span class="badge">{html.escape(item['badge'])}</span>
                  <span class="cat">{html.escape(item['category'])}</span>
                </div>
                <h2>{html.escape(item['title'])}</h2>
                <p>{html.escape(item['highlight'])}</p>
                <a class="cta" href="{html.escape(item['url'])}" target="_blank" rel="nofollow sponsored noopener noreferrer">
                  {html.escape(item['cta'])} &rarr;
                </a>
                <p class="card-disc">#ad &middot; Amazon link</p>
              </div>
            </article>
            """
        )

    updated_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Curated Amazon Finds</title>
  <style>
    :root {{
      --bg: #0f172a;
      --surface: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #f59e0b;
      --accent-dark: #d97706;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    .disclosure-bar {{
      background: #172033;
      border-bottom: 1px solid var(--border);
      text-align: center;
      padding: 10px 16px;
      font-size: 0.85rem;
      color: var(--muted);
    }}
    header {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 40px 20px 24px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 2rem; }}
    .subtitle {{ color: var(--muted); margin: 0 0 20px; }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
    }}
    .filters {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .filter-btn {{
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 8px 14px;
      border-radius: 999px;
      cursor: pointer;
      font-size: 0.9rem;
    }}
    .filter-btn.active {{
      background: var(--accent);
      color: #0f172a;
      border-color: var(--accent);
      font-weight: 600;
    }}
    #search {{
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 10px 14px;
      border-radius: 10px;
      min-width: 240px;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 12px 20px 60px;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 24px;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    .card-img-wrap img {{
      width: 100%;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      display: block;
    }}
    .card-body {{
      padding: 18px;
      display: flex;
      flex-direction: column;
      flex: 1;
    }}
    .meta {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      font-size: 0.8rem;
    }}
    .badge {{
      background: var(--accent);
      color: #0f172a;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 999px;
    }}
    .cat {{ color: var(--muted); }}
    h2 {{ margin: 0 0 8px; font-size: 1.15rem; }}
    .card-body p {{ color: #cbd5e1; font-size: 0.95rem; margin: 0 0 16px; flex: 1; }}
    .cta {{
      display: block;
      text-align: center;
      background: var(--accent);
      color: #0f172a;
      font-weight: 700;
      text-decoration: none;
      padding: 12px 16px;
      border-radius: 10px;
    }}
    .cta:hover {{ background: var(--accent-dark); }}
    .card-disc {{
      font-size: 0.75rem !important;
      color: var(--muted) !important;
      margin: 8px 0 0 !important;
      flex: 0 !important;
      text-align: center;
    }}
    footer {{
      border-top: 1px solid var(--border);
      text-align: center;
      padding: 24px 16px;
      color: var(--muted);
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>
  <div class="disclosure-bar">
    <strong>Affiliate Disclosure:</strong> {html.escape(DISCLOSURE_TEXT)}
  </div>
  <header>
    <h1>Curated Amazon Finds</h1>
    <p class="subtitle">Hand-picked gear, deals, and essentials. Updated {updated_str}.</p>
    <div class="controls">
      <div class="filters">
        <button class="filter-btn active" data-category="all">All</button>
        {cat_buttons}
      </div>
      <input id="search" type="search" placeholder="Search products..." aria-label="Search products" />
    </div>
  </header>
  <main id="grid">
    {''.join(cards_html)}
  </main>
  <footer>
    {html.escape(DISCLOSURE_TEXT)} All links go directly to Amazon.
  </footer>
  <script>
    const buttons = document.querySelectorAll('.filter-btn');
    const searchInput = document.getElementById('search');
    const cards = document.querySelectorAll('.card');
    let activeCat = 'all';

    function filterCards() {{
      const q = searchInput.value.trim().toLowerCase();
      cards.forEach(card => {{
        const matchCat = activeCat === 'all' || card.dataset.category === activeCat;
        const matchText = !q || card.dataset.search.includes(q);
        card.style.display = (matchCat && matchText) ? 'flex' : 'none';
      }});
    }}

    buttons.forEach(btn => {{
      btn.addEventListener('click', () => {{
        buttons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeCat = btn.dataset.category;
        filterCards();
      }});
    }});
    searchInput.addEventListener('input', filterCards);
  </script>
</body>
</html>
"""
    (DOCS_DIR / "index.html").write_text(page_html, encoding="utf-8")


def post_new_to_telegram(enriched_items: list[dict]) -> None:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("Telegram secrets not configured; skipping Telegram auto-post.")
        return

    posted_ids = set()
    if POSTED_FILE.exists():
        posted_ids = set(json.loads(POSTED_FILE.read_text(encoding="utf-8")))

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    for item in enriched_items:
        if item["id"] in posted_ids:
            continue
        card_path = CARDS_DIR / item["card_filename"]
        with card_path.open("rb") as photo:
            resp = requests.post(
                api_url,
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": item["caption"][:1024]},
                files={"photo": photo},
                timeout=30,
            )
        if resp.ok:
            print(f"Posted '{item['id']}' to Telegram.")
            posted_ids.add(item["id"])
        else:
            print(f"Telegram post failed for '{item['id']}': {resp.text}")

    POSTED_FILE.write_text(json.dumps(sorted(posted_ids), indent=2) + "\n", encoding="utf-8")


def main() -> None:
    products = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    enriched = []
    for raw in products:
        pid = slugify(raw.get("id") or raw.get("asin") or raw.get("title", "item"))
        url = build_affiliate_url(raw)
        card_filename = f"{pid}.png"
        generate_deal_card(raw, url, CARDS_DIR / card_filename)
        caption = build_caption(raw, url)

        enriched.append(
            {
                "id": pid,
                "title": raw.get("title", "Amazon Find"),
                "category": raw.get("category", "Featured"),
                "highlight": raw.get("highlight", ""),
                "badge": raw.get("badge", "Pick"),
                "cta": raw.get("cta", "View on Amazon"),
                "url": url,
                "card_filename": card_filename,
                "caption": caption,
            }
        )

    generate_html_page(enriched)
    (DOCS_DIR / "posts.json").write_text(
        json.dumps(
            [{"id": x["id"], "url": x["url"], "card": f"cards/{x['card_filename']}", "caption": x["caption"]} for x in enriched],
            indent=2,
        ),
        encoding="utf-8",
    )
    post_new_to_telegram(enriched)
    print(f"Built {len(enriched)} deal cards, docs/index.html, and docs/posts.json.")


if __name__ == "__main__":
    main()
