#!/usr/bin/env python3
"""Generador de sitio de tendencias de Google (v2).

  python3 generate.py --geo AR,MX,CL --site https://tudominio.com --out ./public

Variables de entorno opcionales:
  GEO, SITE_NAME, CONTACT_EMAIL, PLAUSIBLE_DOMAIN, ANTHROPIC_API_KEY, AI_MODEL
Texto propio por tema: extras/<slug>.txt (párrafos separados por línea en blanco).
"""
import argparse, json, os, re, unicodedata, urllib.request
from datetime import datetime, timezone, timedelta
from html import escape as E
from pathlib import Path
import xml.etree.ElementTree as ET

FEED = "https://trends.google.com/trending/rss?geo={geo}"
COUNTRIES = {"AR": "Argentina", "MX": "México", "CL": "Chile", "ES": "España", "CO": "Colombia",
             "UY": "Uruguay", "PE": "Perú", "US": "Estados Unidos", "BR": "Brasil"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
SENSIBLE = re.compile(r"muri|muer|falleci|accident|tragedi|atentad|asesin|violaci|suicid|c[aá]ncer|"
                      r"medicament|retiro|recall|incendio|tiroteo|femicid|desaparec|abuso", re.I)

CSS = """:root{--bg:#faf8f4;--fg:#1c1b19;--mu:#6b675f;--card:#fff;--ln:#e4dfd5;--ac:#c2410c;--chip:#efe9dd}
@media(prefers-color-scheme:dark){:root{--bg:#161513;--fg:#f1eee8;--mu:#a09a8e;--card:#201f1c;--ln:#34312b;--ac:#fb923c;--chip:#2a2823}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.6 Georgia,serif}
[hidden]{display:none!important}a{color:var(--ac)}
header,main,footer{max-width:900px;margin:0 auto;padding:16px}
header{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:baseline;border-bottom:1px solid var(--ln)}
.logo{font:700 20px system-ui,sans-serif;color:var(--fg);text-decoration:none}
nav{display:flex;flex-wrap:wrap;gap:6px 14px;font:14px system-ui,sans-serif}
h1{font-size:2rem;line-height:1.15;margin:.3em 0}h2{font-size:1.15rem;margin:1.4em 0 .4em}
.m{color:var(--mu);font:13px/1.4 system-ui,sans-serif;margin:0}
.bar{display:flex;gap:8px;margin:14px 0;font-family:system-ui,sans-serif}
.bar input{flex:1;min-width:0;padding:9px 12px;border:1px solid var(--ln);border-radius:10px;background:var(--card);color:var(--fg);font-size:15px}
.bar button{border:1px solid var(--ac);background:none;color:var(--ac);border-radius:10px;padding:9px 14px;cursor:pointer;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.card{display:block;background:var(--card);border:1px solid var(--ln);border-radius:12px;padding:14px;text-decoration:none;color:var(--fg)}
.card:hover{border-color:var(--ac)}.card h3{margin:0 0 6px;font-size:1.1rem;line-height:1.25;text-transform:capitalize}
.box{background:var(--card);border:1px solid var(--ln);border-radius:12px;padding:14px;margin:16px 0}
li{margin:8px 0}footer{border-top:1px solid var(--ln);margin-top:32px;font:13px/1.6 system-ui,sans-serif;color:var(--mu)}"""

JS = """var q=document.getElementById('q');
if(q)q.addEventListener('input',function(){var v=q.value.toLowerCase();document.querySelectorAll('.card').forEach(function(c){c.hidden=c.dataset.t.indexOf(v)<0})});
var u=document.getElementById('upd');
if(u){var m=Math.round((Date.now()-new Date(u.getAttribute('datetime')))/60000);u.textContent=m<1?'ahora':m<60?'hace '+m+' min':m<1440?'hace '+Math.round(m/60)+' h':'hace '+Math.round(m/1440)+' d'}
var s=document.getElementById('share');
if(s)s.addEventListener('click',function(){var d={title:document.title,url:location.href};if(navigator.share){navigator.share(d).catch(function(){})}else if(navigator.clipboard){navigator.clipboard.writeText(d.url).then(function(){s.textContent='¡Enlace copiado!'})}});"""


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:80] or "tema"


def bad_term(t):
    """Descarta términos cortados por Google, como 'argentina vs' o 'méxico -'."""
    return len(t) < 3 or bool(re.search(r"(\bvs\.?|-|–|—)\s*$", t.strip(), re.I))


def volume(s):
    m = re.match(r"\s*([\d.,]+)\s*([KkMmLl]?)", s or "")
    if not m:
        return 0
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return 0
    return int(n * {"": 1, "K": 1e3, "M": 1e6, "L": 1e5}[m.group(2).upper()])


def human(n):
    if n >= 2_000_000: return f"más de {n // 1_000_000} millones de búsquedas"
    if n >= 1_000_000: return "más de 1 millón de búsquedas"
    if n >= 1000: return f"más de {n // 1000} mil búsquedas"
    return f"más de {n} búsquedas" if n else ""


def fdate(iso):
    d = datetime.fromisoformat(iso[:10])
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def fetch(geo, feed_file=None):
    if feed_file:
        data = Path(feed_file).read_bytes()
    else:
        req = urllib.request.Request(FEED.format(geo=geo), headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=20).read()
    root = ET.fromstring(data)
    for el in root.iter():  # ignora namespaces (ht:)
        el.tag = el.tag.split("}")[-1]
    out = []
    for it in root.iter("item"):
        news = [{"title": (n.findtext("news_item_title") or "").strip(),
                 "url": (n.findtext("news_item_url") or "").strip(),
                 "source": (n.findtext("news_item_source") or "").strip()} for n in it.findall("news_item")]
        out.append({"term": (it.findtext("title") or "").strip(),
                    "traffic": (it.findtext("approx_traffic") or "").strip(),
                    "news": [n for n in news if n["url"].startswith("http")]})
    return [t for t in out if t["term"] and not bad_term(t["term"])]


def ai_text(term, news):
    """Resumen opcional (requiere ANTHROPIC_API_KEY). Solo con los titulares; evita temas sensibles."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    heads = [n["title"] for n in news if n["title"]][:5]
    if not key or len(heads) < 2 or SENSIBLE.search(term + " " + " ".join(heads)):
        return ""
    prompt = (f"Tema en tendencia: {term}\nTitulares:\n" + "\n".join("- " + h for h in heads) +
              "\n\nEscribí 2 o 3 oraciones en español rioplatense neutro que expliquen de qué trata, usando SOLO la "
              "información de esos titulares. No inventes datos, cifras ni fechas. Si los titulares no alcanzan "
              "para explicarlo, respondé solo: NADA")
    body = json.dumps({"model": os.environ.get("AI_MODEL", "claude-haiku-4-5-20251001"), "max_tokens": 250,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        text = json.load(urllib.request.urlopen(req, timeout=40))["content"][0]["text"].strip()
    except Exception as e:  # sin reintento inmediato; se vuelve a intentar en la próxima corrida
        print("IA falló:", e)
        return None
    return "" if text.upper().startswith("NADA") else text


def layout(c, title, desc, path, body, ld=None):
    url = c["site"] + path
    nav = f'<a href="{c["site"]}/">Inicio</a>' + "".join(
        f'<a href="{c["site"]}/{g.lower()}/">{COUNTRIES.get(g, g)}</a>' for g in c["geos"]) + \
        f'<a href="{c["site"]}/historial/">Historial</a>'
    foot = (f'<a href="{c["site"]}/quienes-somos.html">Quiénes somos</a> · '
            f'<a href="{c["site"]}/privacidad.html">Privacidad</a>' +
            (f' · <a href="{c["site"]}/contacto.html">Contacto</a>' if c["email"] else ""))
    ana = (f'<script defer data-domain="{E(c["plausible"])}" src="https://plausible.io/js/script.js"></script>'
           if c["plausible"] else "")
    ldt = (f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("<", chr(92) + "u003c")}</script>'
           if ld else "")
    return (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{E(title)}</title><meta name="description" content="{E(desc)}">'
            f'<link rel="canonical" href="{E(url)}"><meta property="og:title" content="{E(title)}">'
            f'<meta property="og:description" content="{E(desc)}"><meta property="og:type" content="website">'
            f'<style>{CSS}</style>{ldt}{ana}</head><body>'
            f'<header><a class="logo" href="{c["site"]}/">{E(c["name"])}</a><nav>{nav}</nav></header>'
            f'<main>{body}</main><footer>{E(c["name"])} · Datos de Google Trends. Los enlaces llevan a notas de '
            f'otros medios.<br>{foot}</footer><script>{JS}</script></body></html>')


def cards(c, items):
    if not items:
        return '<p class="m">Todavía no hay temas.</p>'
    out = []
    for slug, t in items:
        v = human(volume(t["traffic"]))
        out.append(f'<a class="card" data-t="{E(t["term"].lower())}" href="{c["site"]}/tema/{slug}.html">'
                   f'<h3>{E(t["term"])}</h3><p class="m">{E(v)}</p><p class="m">{len(t["news"])} notas</p></a>')
    return '<div class="grid">' + "".join(out) + "</div>"


def write(out, rel, text):
    p = out / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, "utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geo", default=os.environ.get("GEO") or "AR", help="Países separados por coma")
    ap.add_argument("--site", required=True)
    ap.add_argument("--out", default="public")
    ap.add_argument("--feed-file")
    ap.add_argument("--extras", default="extras")
    a = ap.parse_args()
    geos = [g.strip().upper() for g in a.geo.split(",") if g.strip()]
    c = {"site": a.site.rstrip("/"), "geos": geos, "name": os.environ.get("SITE_NAME") or "Lo Más Buscado",
         "email": os.environ.get("CONTACT_EMAIL", ""), "plausible": os.environ.get("PLAUSIBLE_DOMAIN", "")}
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    db_path = out / "trends.json"
    db = json.loads(db_path.read_text("utf-8")) if db_path.exists() else {}
    for s in list(db):  # migración de versiones viejas y limpieza
        t = db[s]
        if bad_term(t["term"]):
            del db[s]
            continue
        t.setdefault("geos", {"AR": t.get("seen", now_iso)})

    for g in geos:
        try:
            trends = fetch(g, a.feed_file)
        except Exception as e:
            print(f"No se pudo leer {g}: {e}")
            continue
        for t in trends:
            slug = slugify(t["term"])
            old = db.get(slug, {})
            geo_map = dict(old.get("geos", {}))
            geo_map[g] = now_iso
            db[slug] = {"term": t["term"], "traffic": t["traffic"] or old.get("traffic", ""),
                        "news": t["news"] or old.get("news", []), "first": old.get("first", now_iso),
                        "seen": now_iso, "geos": geo_map, **({"ai": old["ai"]} if "ai" in old else {})}

    done = 0
    for s, t in db.items():  # resúmenes con IA: máx. 12 por corrida, uno por tema
        if "ai" not in t and done < 12 and os.environ.get("ANTHROPIC_API_KEY"):
            r = ai_text(t["term"], t["news"])
            done += 1
            if r is not None:
                t["ai"] = r

    def recent(geo=None):
        lim = (now - timedelta(hours=24)).isoformat()
        it = [(s, t) for s, t in db.items() if any((geo is None or g == geo) and ts >= lim for g, ts in t["geos"].items())]
        return sorted(it, key=lambda kv: volume(kv[1]["traffic"]), reverse=True)[:60]

    tools = ('<div class="bar"><input id="q" type="search" placeholder="Buscar un tema…" aria-label="Buscar">'
             '<button id="share" type="button">Compartir</button></div>')
    upd = f'<p class="m">Actualizado <time id="upd" datetime="{now_iso}">{now_iso[:16]}</time></p>'
    days = sorted({t["first"][:10] for t in db.values()}, reverse=True)

    def index(geo, path):
        name = COUNTRIES.get(geo, geo) if geo else "el mundo hispano"
        items = recent(geo)
        body = (f'<h1>Lo más buscado hoy en {E(name)}</h1><p class="m">Los temas que más crecieron en Google en las '
                f'últimas 24 horas.</p>{upd}{tools}{cards(c, items)}')
        if len(days) > 1:
            body += f'<p><a href="{c["site"]}/dia/{days[1]}.html">Ver lo que se buscó ayer →</a></p>'
        return layout(c, f"Lo más buscado hoy en {name}: tendencias de Google",
                      f"Qué está buscando la gente hoy en {name}: los temas en tendencia de Google, actualizados cada 30 minutos.",
                      path, body)

    write(out, "index.html", index(geos[0], "/"))
    for g in geos:
        write(out, f"{g.lower()}/index.html", index(g, f"/{g.lower()}/"))

    for slug, t in db.items():
        extra = Path(a.extras, slug + ".txt")
        own = "".join(f"<p>{E(p)}</p>" for p in extra.read_text("utf-8").split("\n\n")) if extra.exists() else ""
        ai = (f'<div class="box"><p>{E(t["ai"])}</p><p class="m">Resumen generado automáticamente a partir de '
              f'los titulares de abajo.</p></div>') if t.get("ai") else ""
        links = "".join(f'<li><a href="{E(n["url"])}" rel="nofollow noopener">{E(n["title"] or n["url"])}</a> '
                        f'<span class="m">{E(n["source"])}</span></li>' for n in t["news"])
        rel = [(s, x) for s, x in recent() if s != slug][:6]
        paises = ", ".join(COUNTRIES.get(g, g) for g in t["geos"])
        meta = " · ".join(x for x in [human(volume(t["traffic"])), paises, f'Desde el {fdate(t["first"])}'] if x)
        body = (f'<p class="m"><a href="{c["site"]}/">← Lo más buscado hoy</a></p>'
                f'<h1>{E(t["term"])}: por qué es tendencia hoy</h1><p class="m">{E(meta)}</p>{ai}{own}'
                f'<h2>Qué dicen los medios</h2><ul>{links or "<li>Sin notas asociadas por ahora.</li>"}</ul>'
                f'<h2>Otros temas del momento</h2>{cards(c, rel)}')
        url = f'/tema/{slug}.html'
        ld = {"@context": "https://schema.org", "@type": "WebPage", "name": t["term"], "url": c["site"] + url,
              "dateModified": t["seen"], "datePublished": t["first"]}
        write(out, url[1:], layout(c, f'{t["term"]}: por qué es tendencia hoy',
                                   f'Qué se sabe de {t["term"]} y por qué es lo más buscado hoy.', url, body, ld))

    for d in days:
        it = sorted([(s, t) for s, t in db.items() if t["first"][:10] == d],
                    key=lambda kv: volume(kv[1]["traffic"]), reverse=True)
        write(out, f"dia/{d}.html", layout(
            c, f"Lo más buscado el {fdate(d)}", f"Los temas que fueron tendencia en Google el {fdate(d)}.",
            f"/dia/{d}.html", f'<h1>Lo más buscado el {fdate(d)}</h1>{cards(c, it)}'))
    lst = "".join(f'<li><a href="{c["site"]}/dia/{d}.html">{fdate(d)}</a></li>' for d in days)
    write(out, "historial/index.html", layout(c, "Historial de tendencias", "Los temas más buscados de días anteriores.",
                                              "/historial/", f"<h1>Historial</h1><ul>{lst}</ul>"))

    name = E(c["name"])
    static = {
        "quienes-somos.html": ("Quiénes somos", f"<h1>Quiénes somos</h1><p>{name} muestra qué está buscando la gente en "
            "Google en cada momento. Los temas salen de Google Trends y cada página reúne enlaces a notas de otros "
            "medios. Algunos resúmenes se generan automáticamente a partir de esos titulares y están señalados como "
            "tales. Ante cualquier duda, la fuente original es la nota enlazada.</p>"),
        "privacidad.html": ("Política de privacidad", f"<h1>Política de privacidad</h1><p>{name} no pide registro ni "
            "recolecta datos personales propios."
            + (" Usamos Plausible Analytics, que mide visitas sin cookies ni datos personales." if c["plausible"] else "")
            + " Los enlaces salen a sitios de terceros, que tienen sus propias políticas. Esta página es un modelo "
            "general y conviene revisarla si agregás publicidad u otras herramientas.</p>"),
    }
    if c["email"]:
        static["contacto.html"] = ("Contacto", f'<h1>Contacto</h1><p>Escribinos a <a href="mailto:{E(c["email"])}">'
                                   f'{E(c["email"])}</a>.</p>')
    for f, (ttl, b) in static.items():
        write(out, f, layout(c, f"{ttl} · {c['name']}", ttl, "/" + f, b))

    urls = [("/", now_iso)] + [(f"/{g.lower()}/", now_iso) for g in geos] + [("/historial/", now_iso)] + \
           [(f"/dia/{d}.html", now_iso) for d in days] + [(f"/tema/{s}.html", t["seen"]) for s, t in db.items()] + \
           [("/" + f, now_iso) for f in static]
    write(out, "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{E(c['site'] + u)}</loc><lastmod>{m[:10]}</lastmod></url>" for u, m in urls) + "</urlset>")
    write(out, "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {c['site']}/sitemap.xml\n")
    db_path.write_text(json.dumps(db, ensure_ascii=False, indent=1), "utf-8")
    print(f"OK: {len(db)} temas, {len(urls)} URLs, países: {','.join(geos)}")


if __name__ == "__main__":
    main()
