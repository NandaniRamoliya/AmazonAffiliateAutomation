# Amazon Affiliate Content Pipeline ($0 Budget)

A 100% free, Amazon Associates-compliant GitHub Actions pipeline that turns your Amazon affiliate links or ASINs into:
- **1080x1080 social media deal cards** (`docs/cards/*.png`) with `#ad` disclosures
- **Ready-to-post social captions** (`docs/posts.json`)
- **A live GitHub Pages storefront** (`docs/index.html`) with category filters and search
- **Optional Telegram channel auto-posting** via Telegram Bot API

## Why This Stays Compliant
- **No scraping:** Uses your own titles/notes + official ASIN/affiliate URLs.
- **No price tracking or cloaked links:** Links go directly to Amazon (`rel="nofollow sponsored"`).
- **Built-in disclosures:** Includes `#ad` and `"As an Amazon Associate I earn from qualifying purchases."` on every card, caption, and page.

## 5-Minute GitHub Setup
1. Create a new GitHub repository and push all files from this folder to the `main` branch.
2. Go to **Settings -> Pages**, set **Source** to `Deploy from a branch`, choose `main` and `/docs`, and save.
3. Go to **Settings -> Secrets and variables -> Actions**:
   - Under **Secrets**, add `AMAZON_PARTNER_TAG` (e.g., `yourtag-21`).
   - *(Optional)* Under **Variables**, add `AMAZON_MARKETPLACE` (defaults to `amazon.in`; set `amazon.com`, `amazon.co.uk`, etc. if needed).
   - *(Optional for Telegram auto-posting)* Under **Secrets**, add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
4. Edit `data/products.json` with your real Amazon ASINs or `amzn.to` affiliate links, commit, and push—GitHub Actions will automatically build your cards, update your live site, and post new items to Telegram.
