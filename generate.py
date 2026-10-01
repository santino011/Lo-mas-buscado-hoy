#!/usr/bin/env python3
"""Generador de sitio de tendencias de Google (v2).

  python3 generate.py --geo AR,MX,CL --site https://tudominio.com --out ./public

Variables de entorno opcionales:
  GEO, SITE_NAME, OWNER_NAME, CONTACT_EMAIL, PLAUSIBLE_DOMAIN, ADSENSE_CLIENT, ADSENSE_SLOT, ANTHROPIC_API_KEY, AI_MODEL
Texto propio por tema: extras/<slug>.txt (párrafos separados por línea en blanco).
"""
import argparse, json, os, re, unicodedata, urllib.request
from datetime import datetime, timezone, timedelta
from html import escape as E
from pathlib import Path
from email.utils import format_datetime
from urllib.parse import quote
import xml.etree.ElementTree as ET

FEED = "https://trends.google.com/trending/rss?geo={geo}"
COUNTRIES = {"AR": "Argentina", "BR": "Brasil", "CL": "Chile", "CO": "Colombia", "PE": "Perú", "UY": "Uruguay",
             "EC": "Ecuador", "VE": "Venezuela", "BO": "Bolivia", "PY": "Paraguay",
             "US": "Estados Unidos", "MX": "México", "CA": "Canadá", "ES": "España"}
REGIONS = [("Sudamérica", ["AR", "BR", "CL", "CO", "PE", "UY", "EC", "VE", "BO", "PY"]),
           ("Norteamérica", ["US", "MX", "CA"])]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
SENSIBLE = re.compile(r"muri|muer|falleci|accident|tragedi|atentad|asesin|violaci|suicid|c[aá]ncer|"
                      r"medicament|retiro|recall|incendio|tiroteo|femicid|desaparec|abuso", re.I)

CSS = """:root{--bg:#f6f7fb;--fg:#14161f;--mu:#5b6072;--card:#fff;--ln:#e3e6f0;--ac:#5b3df5;--ac2:#00b8a9;--chip:#eceefb}
@media(prefers-color-scheme:dark){:root{--bg:#0e1120;--fg:#eef0fa;--mu:#9aa1bd;--card:#171b2f;--ln:#262b47;--ac:#8b7bff;--ac2:#2dd4bf;--chip:#20264a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
[hidden]{display:none!important}a{color:var(--ac)}
header,main,footer{max-width:960px;margin:0 auto;padding:16px}
header{display:flex;flex-wrap:wrap;gap:10px 20px;align-items:center}
.logo{font-weight:800;font-size:20px;color:var(--fg);text-decoration:none}
nav{display:flex;flex-wrap:wrap;gap:8px;font-size:14px}
nav a{padding:6px 12px;border-radius:99px;background:var(--chip);color:var(--fg);text-decoration:none}
nav a:hover{background:var(--ac);color:#fff}
h1{font-size:2rem;line-height:1.15;margin:.2em 0;font-weight:800}h2{font-size:1.2rem;margin:1.6em 0 .6em;font-weight:800}
.m{color:var(--mu);font-size:13px;line-height:1.4;margin:0}
.hero{background:linear-gradient(135deg,var(--ac),var(--ac2));color:#fff;border-radius:20px;padding:22px;margin:8px 0 16px}
.hero h1{color:#fff}.hero p{margin:6px 0 0}.hero .m{color:rgba(255,255,255,.88)}
.bar{display:flex;gap:8px;margin:14px 0}
.bar input{flex:1;min-width:0;padding:10px 14px;border:1px solid var(--ln);border-radius:12px;background:var(--card);color:var(--fg);font-size:15px}
.bar button{border:0;background:var(--ac);color:#fff;border-radius:12px;padding:10px 16px;cursor:pointer;font-size:14px;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.card{display:block;background:var(--card);border:1px solid var(--ln);border-radius:16px;padding:16px;text-decoration:none;color:var(--fg);box-shadow:0 1px 2px rgba(20,22,31,.06);transition:transform .15s,box-shadow .15s}
.card:hover{transform:translateY(-3px);box-shadow:0 8px 20px rgba(91,61,245,.15)}
.card .top{display:flex;justify-content:space-between;align-items:center}.tile{display:grid;place-items:center;width:44px;height:44px;border-radius:14px;background:color-mix(in srgb,var(--tc) 14%,transparent);color:var(--tc)}
.rk{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:13px;background:var(--chip);color:var(--ac)}
.rk.g1{background:#f5b301;color:#3b2a00}.rk.g2{background:#b8bfcc;color:#1e2530}.rk.g3{background:#d08a4f;color:#2e1800}
.card h3{margin:6px 0 8px;font-size:1.1rem;line-height:1.25;text-transform:capitalize}
.vol{display:inline-block;background:var(--chip);color:var(--ac);border-radius:99px;padding:2px 10px;font-size:12px;font-weight:700}
.card p{margin:4px 0}
.box{background:var(--card);border:1px solid var(--ln);border-left:4px solid var(--ac2);border-radius:14px;padding:14px 16px;margin:16px 0}
.links{display:grid;gap:10px}
.link{display:block;background:var(--card);border:1px solid var(--ln);border-radius:14px;padding:12px 14px;text-decoration:none;color:var(--fg)}
.link:hover{border-color:var(--ac)}.link b{display:block;margin-bottom:2px}
.ad{margin:18px 0;min-height:100px;text-align:center}.ad small{display:block;color:var(--mu);font-size:11px;margin-bottom:4px}.ad.wide{grid-column:1/-1}
.ic{flex:none;vertical-align:-3px}h2{display:flex;align-items:center;gap:8px}
.logo{display:inline-flex;align-items:center}
.mark{display:inline-grid;place-items:center;width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,var(--ac),var(--ac2));color:#fff;margin-right:8px}
nav a{display:inline-flex;align-items:center;gap:6px}
.cc{display:inline-block;margin-left:4px;padding:1px 7px;border-radius:99px;background:var(--chip);color:var(--ac);font-size:11px;font-weight:800;letter-spacing:.04em}
nav .cc{margin:0}.hero .cc{background:rgba(255,255,255,.22);color:#fff}
.hl{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.card .m{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.more{display:inline-flex;align-items:center;gap:6px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
.chips button{border:1px solid var(--ln);background:var(--card);color:var(--fg);border-radius:99px;padding:6px 12px;font-size:13px;cursor:pointer;display:inline-flex;gap:6px;align-items:center}
.chips button.on{background:var(--ac);border-color:var(--ac);color:#fff}
.share{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
.btn{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--ln);background:var(--card);color:var(--fg);border-radius:12px;padding:8px 14px;font-size:14px;font-weight:600;text-decoration:none;cursor:pointer}
.btn.wa{background:#25d366;border-color:#25d366;color:#083b1a}
.how{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}
.how>div{background:var(--card);border:1px solid var(--ln);border-radius:14px;padding:14px;color:var(--ac)}
.how b{display:block;color:var(--fg);margin:6px 0 2px}
.cn{display:flex;gap:8px;overflow-x:auto;padding-bottom:6px;margin:0 0 12px}
.cn a{white-space:nowrap;border:1px solid var(--ln);background:var(--card);color:var(--fg);border-radius:99px;padding:6px 12px;font-size:13px;text-decoration:none}
.cn a.on{background:var(--ac);border-color:var(--ac);color:#fff}
footer{border-top:1px solid var(--ln);margin-top:32px;font-size:13px;line-height:1.7;color:var(--mu)}"""

JS = """var q=document.getElementById('q');
function apply(){var v=q?q.value.toLowerCase():'',k=window._k||'';document.querySelectorAll('.card').forEach(function(c){c.hidden=c.dataset.t.indexOf(v)<0||(k&&c.dataset.k!==k)})}
if(q)q.addEventListener('input',apply);
document.querySelectorAll('.chips button').forEach(function(b){b.addEventListener('click',function(){window._k=b.dataset.k;document.querySelectorAll('.chips button').forEach(function(x){x.classList.toggle('on',x===b)});apply()})});
function ago(m){return m<1?'ahora':m<60?'hace '+m+' min':m<1440?'hace '+Math.round(m/60)+' h':'hace '+Math.round(m/1440)+' d'}
document.querySelectorAll('.since').forEach(function(e){e.textContent='Detectado '+ago(Math.round((Date.now()-new Date(e.dataset.t0))/60000))});
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


ICONS = {
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "sport": '<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M9 20h6M10 17h4"/>',
    "match": '<path d="M5 21V4"/><path d="M5 5h12l-2 4 2 4H5"/>',
    "food": '<path d="M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10"/><path d="M17 3c-2 2-3 5-3 8h3v10"/>',
    "weather": '<path d="M7 16a4 4 0 0 1 .5-8 5 5 0 0 1 9.5 1.5A3.5 3.5 0 0 1 17 16z"/><path d="M9 19l-1 2M13 19l-1 2M17 19l-1 2"/>',
    "money": '<path d="M5 20V12M12 20V5M19 20v-9"/><path d="M3 20h18"/>',
    "film": '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 10h18M7 6l2 4M12 6l2 4M17 6l2 4"/>',
    "gov": '<path d="M3 9l9-5 9 5"/><path d="M5 10v8M10 10v8M14 10v8M19 10v8M3 20h18"/>',
    "tech": '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18h2"/>',
    "health": '<rect x="4" y="4" width="16" height="16" rx="4"/><path d="M12 8v8M8 12h8"/>',
    "news": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9h8M8 13h8M8 17h5"/>',
    "home": '<path d="M4 11l8-7 8 7"/><path d="M6 10v10h12V10"/>',
    "cal": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
    "out": '<path d="M8 16L16 8M9 8h7v7"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "chat": '<path d="M4 5h16v11H9l-5 4z"/>',
    "globe": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c3 3 3 14 0 17M12 3.5c-3 3-3 14 0 17"/>',
    "pin": '<path d="M12 21s6-5.500 6-11a6 6 0 0 0-12 0c0 5.500 6 11 6 11z"/><circle cx="12" cy="10" r="2"/>',
}
LABELS = {"sport": "Fútbol", "match": "Partidos", "food": "Recetas", "weather": "Clima", "money": "Economía",
          "film": "Espectáculos", "gov": "Política", "tech": "Tecnología", "health": "Salud", "trend": "Otros"}
CATS = [(r"f[uú]tbol|boca|river|racing|independiente|selecci[oó]n|mundial|liga|copa|gol\b", "sport", "#16a34a"),
        (r"\bvs\b|partido|nba|nfl|ufc|tenis|carrera|f1", "match", "#d97706"),
        (r"receta|comida|empanada|torta|pan dulce|salsa|cocina", "food", "#ea580c"),
        (r"clima|tormenta|lluvia|alerta|temperatura|calor", "weather", "#0284c7"),
        (r"d[oó]lar|bolsa|inflaci[oó]n|banco|precio|cripto|bitcoin", "money", "#059669"),
        (r"pel[ií]cula|serie|netflix|estreno|concierto|vmas|premios|cantante|festival", "film", "#db2777"),
        (r"elecci|presidente|gobierno|congreso|milei|ley\b", "gov", "#4f46e5"),
        (r"iphone|samsung|celular|chatgpt|tecnolog|juego|ps5", "tech", "#0891b2"),
        (r"salud|vacuna|gripe|hospital", "health", "#e11d48")]
FAVICON = "data:image/svg+xml," + quote(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#5b3df5"/><stop offset="1" stop-color="#00b8a9"/></linearGradient></defs>'
    '<rect width="32" height="32" rx="8" fill="url(#g)"/><g fill="none" stroke="#fff" stroke-width="2.6" '
    'stroke-linecap="round"><circle cx="14.5" cy="14.5" r="6.5"/><path d="M19.5 19.5l6 6"/></g></svg>')


def icon(name, size=20):
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def kind(term):
    return next(((n, col) for pat, n, col in CATS if re.search(pat, term, re.I)), ("trend", "#5b3df5"))


def cc(g):
    return f'<span class="cc">{E(g.upper())}</span>'


def ad(c, wide=False):
    """Espacio publicitario de AdSense: solo se dibuja si configuraste ADSENSE_CLIENT y ADSENSE_SLOT."""
    if not (c["ads"] and c["slot"]):
        return ""
    return (f'<div class="ad{" wide" if wide else ""}"><small>Publicidad</small><ins class="adsbygoogle" '
            f'style="display:block" data-ad-client="{E(c["ads"])}" data-ad-slot="{E(c["slot"])}" '
            f'data-ad-format="auto" data-full-width-responsive="true"></ins>'
            f'<script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script></div>')


def layout(c, title, desc, path, body, ld=None, top_ad=True):
    url = c["site"] + path
    multi = len(c["geos"]) > 1
    nav = (f'<a href="{c["site"]}/">{icon("home", 16)} Inicio</a>' +
           (f'<a href="{c["site"]}/america/">{icon("globe", 16)} América</a>'
            f'<a href="{c["site"]}/paises/">{icon("pin", 16)} Países</a>' if multi else "") +
           f'<a href="{c["site"]}/historial/">{icon("cal", 16)} Historial</a>')
    foot = (f'<a href="{c["site"]}/quienes-somos.html">Quiénes somos</a> · '
            f'<a href="{c["site"]}/privacidad.html">Privacidad</a> · '
            f'<a href="{c["site"]}/terminos.html">Términos</a> · <a href="{c["site"]}/cookies.html">Cookies</a>' +
            (f' · <a href="{c["site"]}/contacto.html">Contacto</a>' if c["email"] else ""))
    ana = (f'<script defer data-domain="{E(c["plausible"])}" src="https://plausible.io/js/script.js"></script>'
           if c["plausible"] else "")
    adjs = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={E(c["ads"])}" '
            f'crossorigin="anonymous"></script>' if c["ads"] else "")
    ldt = (f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("<", chr(92) + "u003c")}</script>'
           if ld else "")
    return (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{E(title)}</title><meta name="description" content="{E(desc)}">'
            f'<link rel="canonical" href="{E(url)}"><meta property="og:title" content="{E(title)}">'
            f'<meta property="og:description" content="{E(desc)}"><meta property="og:type" content="website">'
            f'<link rel="icon" href="{FAVICON}"><link rel="alternate" type="application/rss+xml" title="{E(c["name"])}" '
            f'href="{c["site"]}/feed.xml"><style>{CSS}</style>{ldt}{ana}{adjs}</head><body>'
            f'<header><a class="logo" href="{c["site"]}/"><span class="mark">{icon("search", 18)}</span>{E(c["name"])}</a><nav>{nav}</nav></header>'
            f'<main>{ad(c) if top_ad else ""}{body}</main><footer>{E(c["name"])} · Datos de Google Trends. Los enlaces '
            f'llevan a notas de otros medios.<br>{foot}</footer><script>{JS}</script></body></html>')


def strip(c, current):
    if len(c["geos"]) < 2:
        return ""
    opts = [("america", "América")] + [(g.lower(), COUNTRIES.get(g, g)) for g in c["geos"]]
    return '<div class="cn">' + "".join(
        f'<a href="{c["site"]}/{k}/"{" class=\"on\"" if k == current else ""}>{E(n)}</a>' for k, n in opts) + "</div>"


def cards(c, items, ranked=False):
    if not items:
        return '<p class="m">Todavía no hay temas.</p>'
    out = []
    for i, (slug, t) in enumerate(items):
        if ranked and i == 6:
            out.append(ad(c, wide=True))
        name, col = kind(t["term"])
        badge = f'<span class="rk g{i + 1 if i < 3 else 0}">{i + 1}</span>' if ranked else ""
        gl = list(t["geos"])
        chips = "".join(cc(g) for g in gl[:3]) + (f'<span class="cc">+{len(gl) - 3}</span>' if len(gl) > 3 else "")
        out.append(f'<a class="card" data-t="{E(t["term"].lower())}" data-k="{name}" href="{c["site"]}/tema/{slug}.html">'
                   f'<div class="top"><span class="tile" style="--tc:{col}">{icon(name, 24)}</span>{badge}</div>'
                   f'<h3>{E(t["term"])}</h3><p><span class="vol">{E(human(volume(t["traffic"])) or "En tendencia")}</span></p>'
                   f'<p class="m">{icon("news", 13)} {len(t["news"])} {"nota" if len(t["news"]) == 1 else "notas"} {chips}</p>'
                   f'<p class="m since" data-t0="{E(t["first"])}"></p></a>')
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
         "email": os.environ.get("CONTACT_EMAIL", ""), "plausible": os.environ.get("PLAUSIBLE_DOMAIN", ""),
         "ads": os.environ.get("ADSENSE_CLIENT", ""), "slot": os.environ.get("ADSENSE_SLOT", "")}
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
    cut = (now - timedelta(days=90)).isoformat()  # evita que el historial crezca sin límite
    for k in [k for k, t in db.items() if t.get("seen", now_iso) < cut]:
        del db[k]

    for g in geos:
        try:
            trends = fetch(g, a.feed_file)
        except Exception as e:
            print(f"No se pudo leer {g}: {e}")
            continue
        for t in trends:
            slug = slugify(t["term"])
            old = db.get(slug, {})
            tr = t["traffic"] or old.get("traffic", "")
            if old.get("seen") == now_iso and volume(old.get("traffic", "")) > volume(tr):
                tr = old["traffic"]  # mismo ciclo, otro país: nos quedamos con el mayor volumen
            geo_map = dict(old.get("geos", {}))
            geo_map[g] = now_iso
            db[slug] = {"term": t["term"], "traffic": tr,
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
        name = "América" if geo is None else COUNTRIES.get(geo, geo)
        items = recent(geo)
        cats = []
        for _, t in items:
            k = kind(t["term"])[0]
            if k not in cats:
                cats.append(k)
        chips = ('<div class="chips"><button type="button" class="on" data-k="">Todos</button>' + "".join(
            f'<button type="button" data-k="{k}">{icon(k, 15)} {LABELS[k]}</button>' for k in cats) + "</div>"
                 if len(cats) > 1 else "")
        how = ('<h2>Cómo funciona</h2><div class="how">'
               f'<div>{icon("trend", 22)}<b>Detectamos lo que sube</b><p class="m">Miramos qué temas crecen más en Google Trends.</p></div>'
               f'<div>{icon("news", 22)}<b>Reunimos las notas</b><p class="m">Cada tema enlaza a lo que publicaron los medios.</p></div>'
               f'<div>{icon("clock", 22)}<b>Actualizamos seguido</b><p class="m">La lista se renueva cada 30 minutos, aproximadamente.</p></div></div>')
        hero_upd = upd.replace("Actualizado", f"{len(items)} temas en 24 h · Actualizado")
        label = cc(geo) if geo else ""
        body = (f'<section class="hero"><p class="m hl">{icon("search", 15)} Tendencias en vivo {label}</p>'
                f'<h1>Lo más buscado hoy en {E(name)}</h1>'
                f'<p>Los temas que más crecieron en Google en las últimas 24 horas.</p>{hero_upd}</section>'
                f'{strip(c, "america" if geo is None else geo.lower())}'
                f'{tools}{chips}{cards(c, items, True)}{ad(c)}{how}')
        if len(days) > 1:
            body += f'<p><a class="more" href="{c["site"]}/dia/{days[1]}.html">{icon("cal", 16)} Ver lo que se buscó ayer →</a></p>'
        ld = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": t["term"], "url": f'{c["site"]}/tema/{sl}.html'}
            for i, (sl, t) in enumerate(items[:20])]}
        return layout(c, f"Lo más buscado hoy en {name}: tendencias de Google",
                      f"Qué está buscando la gente hoy en {name}: los temas en tendencia de Google, actualizados cada 30 minutos.",
                      path, body, ld)

    def feed(geo):
        its = "".join(
            f'<item><title>{E(t["term"])}</title><link>{c["site"]}/tema/{sl}.html</link>'
            f'<guid>{c["site"]}/tema/{sl}.html</guid><pubDate>{format_datetime(datetime.fromisoformat(t["first"]))}</pubDate>'
            f'<description>{E(t.get("ai") or human(volume(t["traffic"])) or "Tema en tendencia")}</description></item>'
            for sl, t in recent(geo)[:30])
        return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
                f'<title>{E(c["name"])} · {E(COUNTRIES.get(geo, geo))}</title><link>{c["site"]}/</link>'
                f'<description>Lo más buscado hoy en Google</description>{its}</channel></rss>')

    write(out, "index.html", index(geos[0], "/"))
    for g in geos:
        write(out, f"{g.lower()}/index.html", index(g, f"/{g.lower()}/"))
        write(out, f"{g.lower()}/feed.xml", feed(g))
    write(out, "feed.xml", feed(geos[0]))
    if len(geos) > 1:
        write(out, "america/index.html", index(None, "/america/"))
        secs = ""
        listed = [g for _, cs in REGIONS for g in cs]
        for reg, codes in REGIONS + [("Otros países", [g for g in geos if g not in listed])]:
            cs = [g for g in codes if g in geos]
            if not cs:
                continue
            box = ""
            for g in cs:
                its = recent(g)
                tops = "".join(f'<p class="m">{icon("trend", 13)} {E(t["term"])}</p>' for _, t in its[:3]) or \
                    '<p class="m">Sin datos por ahora.</p>'
                box += (f'<a class="card" data-t="{E(COUNTRIES.get(g, g).lower())}" data-k="" href="{c["site"]}/{g.lower()}/">'
                        f'<h3>{E(COUNTRIES.get(g, g))} {cc(g)}</h3>{tops}<p class="m">{len(its)} temas hoy</p></a>')
            secs += f'<h2>{reg}</h2><div class="grid">{box}</div>'
        write(out, "paises/index.html", layout(
            c, "Lo más buscado por país en América", "Los temas en tendencia de Google en cada país de América.",
            "/paises/", f'<h1>Lo más buscado por país</h1><p class="m">Elegí un país para ver sus tendencias de hoy.</p>'
                        f'{strip(c, "")}{secs}'))
    write(out, "404.html", layout(c, "Página no encontrada", "La página que buscás no existe.", "/404.html",
          f'<h1>No encontramos esa página</h1><p>Puede que el tema ya no esté en tendencia.</p>'
          f'<p><a class="more" href="{c["site"]}/">{icon("home", 16)} Volver a lo más buscado</a></p>', top_ad=False))

    for slug, t in db.items():
        extra = Path(a.extras, slug + ".txt")
        own = "".join(f"<p>{E(p)}</p>" for p in extra.read_text("utf-8").split("\n\n")) if extra.exists() else ""
        ai = (f'<div class="box"><p>{E(t["ai"])}</p><p class="m">Resumen generado automáticamente a partir de '
              f'los titulares de abajo.</p></div>') if t.get("ai") else ""
        links = "".join(f'<a class="link" href="{E(n["url"])}" target="_blank" rel="nofollow noopener noreferrer">'
                        f'<b>{E(n["title"] or n["url"])}</b><span class="m">Leer en {E(n["source"] or "el medio")} '
                        f'{icon("out", 13)}</span></a>' for n in t["news"])
        nolinks = '<p class="m">Sin notas asociadas por ahora.</p>'
        rel = [(s2, x) for s2, x in recent() if s2 != slug][:6]
        chips = "".join(cc(g) for g in t["geos"])
        meta = E(" · ".join(x for x in [human(volume(t["traffic"])), f'Desde el {fdate(t["first"])}'] if x))
        turl = f'{c["site"]}/tema/{slug}.html'
        msg = quote(f'{t["term"]}: por qué es tendencia hoy {turl}', safe="")
        share = (f'<div class="share"><a class="btn wa" href="https://wa.me/?text={msg}" target="_blank" rel="noopener">'
                 f'{icon("chat", 16)} WhatsApp</a><a class="btn" href="https://twitter.com/intent/tweet?text={msg}" '
                 f'target="_blank" rel="noopener">X</a><button class="btn" id="share" type="button">Compartir</button></div>')
        body = (f'<p class="m"><a href="{c["site"]}/">← Lo más buscado hoy</a></p>'
                f'<section class="hero"><p class="m hl">{icon(kind(t["term"])[0], 15)} Tendencia · {meta} {chips}</p>'
                f'<h1>{E(t["term"])}: por qué es tendencia hoy</h1></section>{share}{ai}{own}{ad(c)}'
                f'<h2>{icon("news", 20)} Qué dicen los medios</h2><div class="links">{links or nolinks}</div>{ad(c)}'
                f'<h2>{icon("trend", 20)} Otros temas del momento</h2>{cards(c, rel)}')
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
    owner = E(os.environ.get("OWNER_NAME") or "el titular de este sitio")
    hoy = fdate(now_iso)
    mail = (f' Podés escribirnos a <a href="mailto:{E(c["email"])}">{E(c["email"])}</a>.' if c["email"] else "")
    ads, ana_on = bool(c["ads"]), bool(c["plausible"])

    def doc(title, *secs):
        parts = "".join(f"<h2>{h}</h2>" + "".join(f"<p>{x}</p>" for x in ps) for h, ps in secs)
        return f'<h1>{title}</h1><p class="m">Última actualización: {hoy}</p>{parts}'

    terminos = doc("Términos y condiciones",
        ("1. Aceptación", [f"Al usar {name} aceptás estos términos. Si no estás de acuerdo, te pedimos que no uses el sitio. "
                           f"El sitio es operado por {owner}."]),
        ("2. Qué es este sitio", ["Es un sitio informativo que muestra los temas más buscados en Google según Google Trends "
                                  "y reúne enlaces a notas publicadas por otros medios. No es un medio de noticias ni "
                                  "produce información periodística propia."]),
        ("3. Contenido y enlaces de terceros", ["Los titulares, notas y marcas que se mencionan o enlazan pertenecen a sus "
            "respectivos titulares. No controlamos esos sitios ni somos responsables de su contenido, disponibilidad o "
            "políticas. Que enlacemos una nota no significa que la avalemos."]),
        ("4. Resúmenes automáticos", ["Algunos resúmenes se generan automáticamente a partir de los titulares enlazados y "
            "están señalados como tales. Pueden contener errores u omisiones: la fuente confiable es siempre la nota original."]),
        ("5. Sin asesoramiento", ["La información del sitio es general y no constituye asesoramiento médico, legal, "
            "financiero ni de ningún otro tipo profesional."]),
        ("6. Propiedad intelectual", ["El diseño, el código y los textos propios del sitio están protegidos por la "
            "legislación de propiedad intelectual. No está permitido copiarlos masivamente ni extraerlos de forma "
            "automatizada sin autorización. Las marcas de terceros pertenecen a sus dueños."]),
        ("7. Uso aceptable", ["Te comprometés a no interferir con el funcionamiento del sitio, no intentar acceder a "
            "sistemas o datos que no sean públicos y no realizar un uso automatizado que genere una carga excesiva."]),
        ("8. Publicidad", ["El sitio puede mostrar anuncios de terceros. No somos responsables de los productos, servicios "
            "o promesas de los anunciantes. Más información en la política de cookies."]),
        ("9. Disponibilidad y responsabilidad", ["El sitio se ofrece \"tal cual\", sin garantías de disponibilidad continua "
            "ni de que la información esté completa, actualizada o libre de errores. En la medida permitida por la ley, "
            "no respondemos por daños derivados del uso del sitio o de los sitios enlazados."]),
        ("10. Contenido que consideres inapropiado", [f"Si sos titular de derechos y creés que algún contenido los afecta, "
            f"o querés que retiremos un enlace, avisanos y lo revisamos.{mail}"]),
        ("11. Cambios", ["Podemos modificar estos términos en cualquier momento. La versión vigente es la publicada "
            "en esta página, con su fecha de actualización."]),
        ("12. Ley aplicable", ["Estos términos se rigen por las leyes de la República Argentina. Cualquier controversia se "
            "someterá a los tribunales competentes de ese país."]))

    cookies = doc("Política de cookies",
        ("Qué son las cookies", ["Son pequeños archivos que un sitio guarda en tu navegador para recordar información o "
            "medir el uso."]),
        ("Cookies propias", [f"{name} no usa cookies propias ni de seguimiento."]),
        ("Estadísticas", [("Usamos Plausible Analytics, un servicio de estadísticas que no usa cookies ni recolecta datos "
            "personales." if ana_on else "Este sitio no usa herramientas de estadísticas con cookies.")]),
        ("Publicidad", [("Este sitio muestra anuncios de Google AdSense. Google y sus socios pueden usar cookies e "
            "identificadores para mostrar anuncios, personalizarlos y medir su rendimiento. Si visitás el sitio desde el "
            "Espacio Económico Europeo, el Reino Unido o Suiza, vas a ver un aviso de Google para elegir si aceptás "
            "esas cookies. Podés administrar la personalización en "
            "<a href=\"https://adssettings.google.com\">adssettings.google.com</a> y leer cómo Google usa los datos en "
            "<a href=\"https://policies.google.com/technologies/ads\">policies.google.com/technologies/ads</a>."
            if ads else "Hoy este sitio no muestra publicidad. Si la incorporamos, actualizaremos esta página.")]),
        ("Sitios de terceros", ["Al abrir una nota de otro medio, ese sitio puede usar sus propias cookies, con sus "
            "propias políticas."]),
        ("Cómo controlarlas", ["Podés borrar o bloquear las cookies desde la configuración de tu navegador. Si las bloqueás, "
            f"el sitio sigue funcionando.{mail}"]))

    privacidad = doc("Política de privacidad",
        ("Responsable", [f"{owner} es el responsable de {name}.{mail}"]),
        ("Qué datos recolectamos", [f"{name} no requiere registro y no recolecta datos personales propios. Como en "
            "cualquier sitio web, el proveedor de alojamiento puede registrar datos técnicos de la visita, como la "
            "dirección IP, el navegador y la fecha de acceso, con fines de seguridad y funcionamiento."]),
        ("Estadísticas", [("Usamos Plausible Analytics para medir visitas de forma agregada, sin cookies y sin "
            "identificarte." if ana_on else "No usamos herramientas de análisis de visitas.")]),
        ("Publicidad", [("Mostramos anuncios de Google AdSense. Google puede recolectar datos de tu navegación para "
            "personalizarlos, según se explica en la política de cookies y en "
            "<a href=\"https://policies.google.com/technologies/ads\">policies.google.com/technologies/ads</a>."
            if ads else "Hoy no mostramos publicidad de terceros.")]),
        ("Si nos escribís", [("Si nos enviás un mensaje, usamos tus datos únicamente para responderte y no los cedemos a "
            "terceros." if c["email"] else "Por ahora no ofrecemos un canal de contacto que recolecte datos.")]),
        ("Enlaces a terceros", ["Los sitios que enlazamos tienen sus propias políticas de privacidad, que no controlamos."]),
        ("Menores", ["El sitio no está dirigido a menores de 13 años ni recolecta datos de ellos a sabiendas."]),
        ("Tus derechos", ["Podés pedir el acceso, la rectificación o la supresión de los datos personales que tengamos "
            "sobre vos. En Argentina, la Ley 25.326 de Protección de los Datos Personales te reconoce esos derechos, y "
            "la Agencia de Acceso a la Información Pública es el órgano de control ante el que podés presentar "
            f"reclamos.{mail}"]),
        ("Transferencias internacionales", ["Proveedores como el alojamiento, Google o Plausible pueden procesar datos "
            "en servidores fuera de Argentina, bajo sus propias políticas."]),
        ("Cambios", ["Podemos actualizar esta política. La versión vigente es la publicada aquí, con su fecha."]))

    static = {
        "quienes-somos.html": ("Quiénes somos", f"<h1>Quiénes somos</h1><p>{name} muestra qué está buscando la gente en "
            "Google en cada momento. Los temas salen de Google Trends y cada página reúne enlaces a notas de otros "
            "medios. Algunos resúmenes se generan automáticamente a partir de esos titulares y están señalados como "
            "tales. Ante cualquier duda, la fuente original es la nota enlazada.</p>"),
        "privacidad.html": ("Política de privacidad", privacidad),
        "terminos.html": ("Términos y condiciones", terminos),
        "cookies.html": ("Política de cookies", cookies),
    }
    if c["email"]:
        static["contacto.html"] = ("Contacto", f'<h1>Contacto</h1><p>Escribinos a <a href="mailto:{E(c["email"])}">'
                                   f'{E(c["email"])}</a>.</p>')
    for f, (ttl, b) in static.items():
        write(out, f, layout(c, f"{ttl} · {c['name']}", ttl, "/" + f, b, top_ad=False))

    urls = [("/", now_iso)] + [(f"/{g.lower()}/", now_iso) for g in geos] + [("/historial/", now_iso)] + \
           ([("/america/", now_iso), ("/paises/", now_iso)] if len(geos) > 1 else []) + \
           [(f"/dia/{d}.html", now_iso) for d in days] + [(f"/tema/{s}.html", t["seen"]) for s, t in db.items()] + \
           [("/" + f, now_iso) for f in static]
    write(out, "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{E(c['site'] + u)}</loc><lastmod>{m[:10]}</lastmod></url>" for u, m in urls) + "</urlset>")
    if c["ads"]:  # ads.txt solo sirve si el sitio está en la raíz de un dominio propio
        write(out, "ads.txt", f"google.com, {c['ads'].replace('ca-', '')}, DIRECT, f08c47fec0942fa0\n")
    write(out, "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {c['site']}/sitemap.xml\n")
    db_path.write_text(json.dumps(db, ensure_ascii=False, indent=1), "utf-8")
    print(f"OK: {len(db)} temas, {len(urls)} URLs, países: {','.join(geos)}")


if __name__ == "__main__":
    main()
