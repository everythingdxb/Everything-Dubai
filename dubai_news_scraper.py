#!/usr/bin/env python3
"""
Everything Dubai – Daily Digest (self-subscribe edition)

• Generates index.html for GitHub Pages
• Sends email only when NOT running inside GitHub Actions
"""

import os, feedparser, re, ssl, smtplib, html, textwrap, imaplib, email, email.utils
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dateutil import parser as dateparser

# ----------------------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------------------
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
DUBAI_REGEX   = re.compile(r"\bdubai\b", re.I)
EMAIL_FROM    = "scottandann@me.com"
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "yaaa-axbl-eyiv-hahk")   # env first, fallback literal
SMTP_SERVER   = "smtp.mail.me.com"
SMTP_PORT     = 587
RECIP_FILE    = "recipients.txt"
IMAP_SERVER   = "imap.mail.me.com"

TAG_RE    = re.compile(r"<[^>]+>")
ENTITY_RE = re.compile(r"&[a-zA-Z0-9#]+;")

# ----------------------------------------------------------------------------
def clean_html(raw, limit=200):
    if not raw: return ""
    txt = html.unescape(ENTITY_RE.sub(" ", TAG_RE.sub(" ", raw)))
    txt = re.sub(r"\s+", " ", txt).strip()
    return textwrap.shorten(txt, width=limit, placeholder="…")

def first_image(entry):
    for key in ("media_thumbnail", "media_content"):
        if key in entry and entry[key]:
            u = entry[key][0].get("url");  return u
    for e in entry.get("enclosures", []):
        if e.get("type","").startswith("image/"): return e.get("href")
    for fld in ("summary","description"):
        m = re.search(r'<img[^>]+src="([^"]+)"', entry.get(fld,""))
        if m: return m.group(1)
    return None

# ----------------------------------------------------------------------------
def fetch_articles():
    arts = []
    for src,url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries:
            blob = " ".join(filter(None,[e.get("title",""),e.get("summary",""),e.get("description","")]))
            if not DUBAI_REGEX.search(blob): continue
            try:
                dt = parser.parse(e.get("published") or e.get("updated",""))
                if not dt.tzinfo: dt = dt.replace(tzinfo=timezone.utc)
            except Exception: dt = datetime.now(timezone.utc)
            arts.append(dict(
                title=e.get("title","(no title)"),
                link =e.get("link"),
                source=src,
                published=dt,
                snippet=clean_html(e.get("summary") or e.get("description")),
                image=first_image(e)
            ))
    uniq,seen = [],set()
    for a in sorted(arts,key=lambda x:x["published"],reverse=True):
        if a["link"] not in seen: uniq.append(a); seen.add(a["link"])
    return uniq

# ── recipients helpers (identical to previous version) ----------------------
def load_recipients():
    if not os.path.isfile(RECIP_FILE):
        with open(RECIP_FILE,"w") as f: f.write(EMAIL_FROM+"\n")
    with open(RECIP_FILE) as f:
        return {l.strip().lower() for l in f if l.strip()}

def save_recipients(rs):
    with open(RECIP_FILE,"w") as f:
        for r in sorted(rs): f.write(r+"\n")

def update_recipients_from_inbox(rs):
    try:
        M = imaplib.IMAP4_SSL(IMAP_SERVER)
        M.login(EMAIL_FROM, SMTP_PASSWORD)
        M.select("INBOX")
        typ,data=M.search(None,'(UNSEEN SUBJECT "ADD RECIPIENT")')
        for num in data[0].split():
            typ,msg_data=M.fetch(num,"(RFC822)")
            msg=email.message_from_bytes(msg_data[0][1])
            sender=email.utils.parseaddr(msg.get("From"))[1].lower()
            if sender and sender not in rs:
                print("Added new recipient:",sender); rs.add(sender)
            M.store(num, "+FLAGS", "\\Seen")
        M.logout()
    except Exception as e:
        print("IMAP check failed:",e)
    return rs

# ----------------------------------------------------------------------------
def build_html(arts):
    today=datetime.now().strftime("%Y-%m-%d")
    rows=[]
    for a in arts or [{}]:
        img_html=(f'<img src="{a["image"]}" alt="" style="width:100%;max-height:200px;object-fit:cover;border-radius:6px;margin-bottom:8px;">' 
                  if a.get("image") else "")
        rows.append(f"""
        <tr><td style="padding:0 0 24px 0;">{img_html}
          <a href="{a.get('link','#')}" ≈target="_blank" rel="noopener noreferrer" style="font:700 17px/1.4 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
             color:#0366d6;text-decoration:none;">{a.get('title','No Dubai articles today.')}</a><br>
          <span style="font-size:13px;color:#555;">{a.get('snippet','')}</span><br>
          <span style="font-size:11px;color:#888;">{a.get('source','')} • {a.get('published','').strftime('%Y-%m-%d %H:%M') if arts else ''}</span>
        </td></tr>""")
    body="\n".join(rows)
    mailto=("mailto:"+EMAIL_FROM+"?subject=ADD%20RECIPIENT&body=Please%20add%20me%20to%20Everything%20Dubai")
    return f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<meta name=color-scheme content="light dark"></head>
<body style="margin:0;padding:0;background:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<center><table role=presentation width=100% style="max-width:640px;margin:0 auto">
<tr>
  <td style="padding:0;">
    <img src="assets/dubai-skyline.png"
         alt="Dubai skyline"
         style="width:100%;max-height:220px;object-fit:cover;display:block;">
    <div style="position:relative;top:-160px;text-align:center;color:#fff;">
      <h1 style="margin:0;font-size:32px;font-weight:800;
                 text-shadow:0 2px 4px rgba(0,0,0,.6);">
        Everything&nbsp;Dubai
      </h1>
      <p style="margin:0;font-size:14px;
                text-shadow:0 2px 4px rgba(0,0,0,.6);">
        {today}
      </p>
    </div>
  </td>
</tr>
<tr><td style="padding:24px"><table role=presentation width=100%>{body}</table>
  <div style="text-align:center;padding:18px 0">
    <a href="{mailto}" style="background:#0366d6;color:#fff;font-weight:600;text-decoration:none;
       padding:10px 18px;border-radius:6px;display:inline-block">Add&nbsp;New&nbsp;Recipient</a>
  </div>
  <div style="text-align:center;font-size:11px;color:#97a0a6">Generated automatically by dubai_news_scraper.py</div>
</td></tr></table></center></body></html>"""

# ----------------------------------------------------------------------------
def send_email(html, recips):
    plain="Switch to HTML view to see today's Dubai headlines."
    msg=MIMEMultipart("alternative")
    msg["Subject"]="Everything Dubai"
    msg["From"]=EMAIL_FROM
    msg["To"]=", ".join(recips)
    msg.attach(MIMEText(plain,"plain","utf-8"))
    msg.attach(MIMEText(html,"html","utf-8"))
    ctx=ssl.create_default_context()
    with smtplib.SMTP(SMTP_SERVER,SMTP_PORT,timeout=30) as s:
        s.ehlo(); s.starttls(context=ctx); s.ehlo()
        s.login(EMAIL_FROM, SMTP_PASSWORD)
        s.sendmail(EMAIL_FROM,list(recips), msg.as_string())

# ----------------------------------------------------------------------------
def main():
    recips=load_recipients()
    recips=update_recipients_from_inbox(recips)
    save_recipients(recips)

    arts=fetch_articles()
    html=build_html(arts)

    out="index.html"   # 👉 output for GitHub Pages
    with open(out,"w",encoding="utf-8") as f: f.write(html)
    print("Saved digest with",len(arts),"articles →",out)

    if os.getenv("GITHUB_ACTIONS")!="true":   # skip emailing inside Actions
        send_email(html, recips)

if __name__=="__main__":
    main()
