#!/usr/bin/env python3
"""Genera un sitio estático: una página por cada tema en tendencia de Google Trends.

Uso:
  python3 generate.py --geo AR --site https://tudominio.com --out ./public
Cron (cada 30 min):
  */30 * * * * python3 /ruta/generate.py --geo AR --site https://tudominio.com --out /var/www/html

Texto propio opcional: creá extras/<slug>.txt con un párrafo tuyo (contexto, horarios,
datos verificados). Esas páginas aportan valor real y es lo que Google premia.
"""
import argparse, json, re, unicodedata, urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

FEED = "https://trends.google.com/trending/rss?geo={geo}"

CSS = ("body{font:17px/1.6 Georgia,serif;max-width:720px;margin:0 auto;padding:24px 16px;color:#1c1b19;background:#faf8f4}"
       "a{color:#c2410c}h1{line-height:1.15}.m{color:#6b675f;font:14px system-ui,sans-serif}"
       "li{margin:8px 0}@media(prefers-color-scheme:dark){body{background:#161513;color:#f1eee8}a{color:#fb923c}}")


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:80] or "tema"


def fetch(geo, feed_file=None):
    if feed_file:
        data = Path(feed_file).read_bytes()
    else:
        req = urllib.request.Request(FEED.format(geo=geo), headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=20).read()
    out = []
    root = ET.fromstring(data)
    for el in root.iter():  # ignora namespaces (ht:), por si Google los cambia
        el.tag = el.tag.split("}")[-1]
    for it in root.iter("item"):
        news = [{"title": (n.findtext("news_item_title") or "").strip(),
                 "url": (n.findtext("news_item_url") or "").strip(),
                 "source": (n.findtext("news_item_source") or "").strip()}
                for n in it.findall("news_item")]
        out.append({"term": (it.findtext("title") or "").strip(),
                    "traffic": (it.findtext("approx_traffic") or "").strip(),
                    "news": [n for n in news if n["url"].startswith("http")]})
    return [t for t in out if t["term"]]


def page(title, desc, url, body, ld=None):
    ldtag = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>' if ld else ""
    return (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(title)}</title><meta name="description" content="{escape(desc)}">'
            f'<link rel="canonical" href="{escape(url)}"><meta property="og:title" content="{escape(title)}">'
            f'<meta property="og:description" content="{escape(desc)}"><style>{CSS}</style>{ldtag}</head>'
            f'<body>{body}</body></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geo", default="AR")
    ap.add_argument("--site", required=True, help="URL base, sin barra final")
    ap.add_argument("--out", default="public")
    ap.add_argument("--feed-file", help="XML local, para pruebas")
    ap.add_argument("--extras", default="extras")
    a = ap.parse_args()

    out = Path(a.out); (out / "tema").mkdir(parents=True, exist_ok=True)
    db_path = out / "trends.json"
    db = json.loads(db_path.read_text("utf-8")) if db_path.exists() else {}
    now = datetime.now(timezone.utc)

    for t in fetch(a.geo, a.feed_file):
        slug = slugify(t["term"])
        old = db.get(slug, {})
        db[slug] = {"term": t["term"], "traffic": t["traffic"], "news": t["news"] or old.get("news", []),
                    "first": old.get("first", now.isoformat()), "seen": now.isoformat()}

    for slug, t in db.items():
        url = f"{a.site}/tema/{slug}.html"
        extra = Path(a.extras, slug + ".txt")
        own = "".join(f"<p>{escape(p)}</p>" for p in extra.read_text("utf-8").split("\n\n")) if extra.exists() else ""
        links = "".join(f'<li><a href="{escape(n["url"])}" rel="nofollow noopener">{escape(n["title"] or n["url"])}</a>'
                        f' <span class="m">{escape(n["source"])}</span></li>' for n in t["news"])
        traffic = f" Más de {escape(t['traffic'])} búsquedas." if t["traffic"] else ""
        body = (f'<p class="m"><a href="{a.site}/">← Lo más buscado hoy</a></p><h1>{escape(t["term"])}: por qué es tendencia hoy</h1>'
                f'<p class="m">Visto por última vez: {t["seen"][:16].replace("T", " ")} UTC.{traffic}</p>{own}'
                f'<h2>Qué dicen los medios</h2><ul>{links or "<li>Sin notas asociadas por ahora.</li>"}</ul>')
        ld = {"@context": "https://schema.org", "@type": "WebPage", "name": t["term"], "url": url, "dateModified": t["seen"]}
        (out / "tema" / f"{slug}.html").write_text(
            page(f'{t["term"]}: por qué es tendencia hoy', f'Qué se sabe de {t["term"]} y por qué es lo más buscado hoy.', url, body, ld), "utf-8")

    recent = sorted(db.items(), key=lambda kv: kv[1]["seen"], reverse=True)
    items = "".join(f'<li><a href="{a.site}/tema/{s}.html">{escape(t["term"])}</a> <span class="m">{escape(t["traffic"])}</span></li>' for s, t in recent[:60])
    (out / "index.html").write_text(page("Lo más buscado hoy", "Los temas del momento en Google, actualizados cada 30 minutos.",
                                         a.site + "/", f"<h1>Lo más buscado hoy</h1><ol>{items}</ol>"), "utf-8")
    urls = [a.site + "/"] + [f"{a.site}/tema/{s}.html" for s in db]
    (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                     + "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls) + "</urlset>", "utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {a.site}/sitemap.xml\n", "utf-8")
    db_path.write_text(json.dumps(db, ensure_ascii=False, indent=1), "utf-8")
    print(f"OK: {len(db)} temas, {len(urls)} URLs en {out}")


if __name__ == "__main__":
    main()
