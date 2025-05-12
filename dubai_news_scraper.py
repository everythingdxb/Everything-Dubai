#!/usr/bin/env python3
"""
Everything Dubai – Daily RSS Digest
-----------------------------------
• Finds Dubai-related headlines, grabs thumbnails when present.
• Builds a white-background HTML digest (no placeholder images).
• Saves an HTML file and emails the same layout via iCloud SMTP.

Dependencies:
    pip install feedparser python-dateutil
"""

import feedparser, re, os, ssl, smtplib, html, textwrap
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dateutil import parser as dateparser

# ── SETTINGS ────────────────────────────────────────────────────────────────
RSS_FEEDS = [
    ("Google News",      "https://news.google.com/rss/search?q=Dubai&hl=en"),
    ("Gulf News (UAE)",  "https://gulfnews.com/rss?cat=/uae"),
    ("Khaleej Times",    "https://www.khaleejtimes.com/rss?section=uae"),
    ("Al Jazeera",       "https://www.aljazeera.com/xml/rss/all.xml"),
    ("CNN ME",           "https://rss.cnn.com/rss/edition_meast.rss"),
    ("Reuters World",    "https://feeds.reuters.com/reuters/worldNews"),
    ("BBC ME",           "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("The National UAE", "https://www.thenationalnews.com/rss?outputType=xml"),
]

DUBAI_REGEX = re.compile(r"\bdubai\b", re.IGNORECASE)

# Email credentials (iCloud)
EMAIL_TO      = "scottandann@me.com"
EMAIL_FROM    = "scottandann@me.com"
SMTP_SERVER   = "smtp.mail.me.com"
SMTP_PORT     = 587
SMTP_USER     = "scottandann@me.com"
SMTP_PASSWORD = "yaaa-axbl-eyiv-hahk"    # app-specific password

# ── HELPERS ────────────────────────────────────────────────────────────────
TAG_RE    = re.compile(r"<[^>]+>")
ENTITY_RE = re.compile(r"&[a-zA-Z0-9#]+;")

def clean_html(raw, limit=200):
    if not raw:
        return ""
    text = html.unescape(ENTITY_RE.sub(" ", TAG_RE.sub(" ", raw)))
    text = re.sub(r"\s+", " ", text).strip()
    return textwrap.shorten(text, width=limit, placeholder="…")

def first_image(entry):
    """Return a thumbnail URL if one exists, else None."""
    # media tags
    for key in ("media_thumbnail", "media_content"):
        if key in entry and entry[key]:
            url = entry[key][0].get("url")
            if url: return url
    # enclosures
    for enc in entry.get("enclosures", []):
        if enc.get("type", "").startswith("image/") and enc.get("href"):
            return enc["href"]
    # inline <img> in summary / description
    for field in ("summary", "description"):
        m = re.search(r'<img[^>]+src="([^"]+)"', entry.get(field, ""))
        if m: return m.group(1)
    # nothing found
    return None

# ── CORE ───────────────────────────────────────────────────────────────────
def fetch_articles():
    articles = []
    for source, url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries:
            blob = " ".join(filter(None, [
                e.get("title", ""), e.get("summary", ""), e.get("description", "")
            ]))
            if not DUBAI_REGEX.search(blob):
                continue

            pub_raw = e.get("published") or e.get("updated") or ""
            try:
                pub_dt = dateparser.parse(pub_raw)
                if not pub_dt.tzinfo:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            except Exception:
                pub_dt = datetime.now(timezone.utc)

            articles.append({
                "title":   e.get("title", "(no title)"),
                "link":    e.get("link"),
                "source":  source,
                "published": pub_dt,
                "snippet": clean_html(e.get("summary") or e.get("description")),
                "image":   first_image(e)
            })

    # deduplicate + newest first
    seen, uniq = set(), []
    for a in sorted(articles, key=lambda x: x["published"], reverse=True):
        if a["link"] not in seen:
            uniq.append(a); seen.add(a["link"])
    return uniq

def build_html(arts):
    today = datetime.now().strftime("%Y-%m-%d")
    rows = []
    for a in arts or [{}]:
        img_html = (f'<img src="{a["image"]}" alt="" style="width:100%;'
                    'max-height:200px;object-fit:cover;border-radius:6px;'
                    'margin-bottom:8px;">') if a.get("image") else ""
        rows.append(f"""
        <tr>
          <td style="padding:0 0 24px 0;">
            {img_html}
            <a href="{a.get('link','#')}" style="font:700 17px/1.4 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
               color:#0366d6;text-decoration:none;">{a.get('title','No Dubai articles today.')}</a><br>
            <span style="font-size:13px;color:#555;">{a.get('snippet','')}</span><br>
            <span style="font-size:11px;color:#888;">{a.get('source','')} • {a.get('published','').strftime('%Y-%m-%d %H:%M') if arts else ''}</span>
          </td>
        </tr>""")
    body_rows = "\n".join(rows)

    return f"""\
<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"></head>
<body style="margin:0;padding:0;background:#ffffff;
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <center>
    <table role="presentation" width="100%" style="max-width:640px;margin:0 auto;">
      <!-- Header -->
      <tr>
        <td style="background:#008080;padding:24px 16px;text-align:center;">
          <span style="font-size:32px;font-weight:800;color:#ffffff;">Everything&nbsp;Dubai</span><br>
          <span style="font-size:14px;color:#e2f7f7;">{today}</span>
        </td>
      </tr>
      <!-- Body -->
      <tr>
        <td style="padding:24px;">
          <table role="presentation" width="100%">{body_rows}</table>
          <div style="text-align:center;padding-top:12px;font-size:11px;color:#97a0a6;">
            Generated automatically by dubai_news_scraper.py
          </div>
        </td>
      </tr>
    </table>
  </center>
</body></html>"""

def send_email(html):
    plain = "Switch to HTML view to see today's Dubai headlines with images."
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Everything Dubai"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as s:
        s.ehlo(); s.starttls(context=ctx); s.ehlo()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())

def main():
    arts = fetch_articles()
    html = build_html(arts)
    out  = os.path.join(os.path.dirname(__file__), "dubai_news_digest.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved digest with {len(arts)} articles → {out}")
    send_email(html)

if __name__ == "__main__":
    main()