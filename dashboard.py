"""Builds docs/index.html (one self-contained page, no JavaScript) from the niche scan and the clipped moments."""
from html import escape as e

CSS = """
:root{--bg:#f6f7fb;--card:#fff;--ink:#14161f;--mute:#6b7185;--line:#e6e8f0;--a:#7c5cff;--b:#22d3ee;--ok:#16a34a}
@media(prefers-color-scheme:dark){:root{--bg:#0b0d14;--card:#141824;--ink:#eef0f7;--mute:#8d94ab;--line:#232a3d;--ok:#4ade80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1080px;margin:0 auto;padding:32px 16px 64px}
header{display:flex;justify-content:space-between;align-items:end;flex-wrap:wrap;gap:8px;margin-bottom:24px}
h1{margin:0;font-size:28px;letter-spacing:-.02em;background:linear-gradient(90deg,var(--a),var(--b));-webkit-background-clip:text;background-clip:text;color:transparent}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--mute);margin:0 0 16px}
.mute{color:var(--mute);font-size:13px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px}
.kpi b{display:block;font-size:30px;line-height:1.1;letter-spacing:-.02em}
.kpi span{color:var(--mute);font-size:13px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:820px){.grid{grid-template-columns:1fr}}
.row{margin-bottom:14px}.row summary{cursor:pointer;list-style:none}.row summary::-webkit-details-marker{display:none}
.top{display:flex;justify-content:space-between;gap:8px;font-weight:600}.top i{font-style:normal;color:var(--mute);font-weight:400;font-variant-numeric:tabular-nums}
.bar{height:8px;border-radius:99px;background:var(--line);margin-top:6px;overflow:hidden}
.bar div{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--a),var(--b))}
.row ol{margin:10px 0 0;padding-left:20px;color:var(--mute);font-size:13px}.row li{margin:2px 0}
table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--mute);font-weight:500}tr:last-child td{border:0}
a{color:var(--a);text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.pill{display:inline-block;padding:2px 10px;border-radius:99px;background:var(--line);font-size:12px;color:var(--mute)}
.empty{color:var(--mute);padding:24px 0;text-align:center}
"""


def build(scan, seen):
    niches, posted = scan.get("niches", []), [s for s in seen if s.get("keep")]
    top = max((n["views"] for n in niches), default=0) or 1
    rows = "".join(
        f'<details class="row"><summary><div class="top"><span>{i}. {e(n["name"])}</span><i>{n["views"]:,} views</i></div>'
        f'<div class="bar"><div style="width:{n["views"] / top * 100:.1f}%"></div></div></summary><ol>'
        + "".join(f'<li>{e(c["title"])} <b>{c["views"]:,}</b></li>' for c in n["top"][:5]) + "</ol></details>"
        for i, n in enumerate(niches[:10], 1)) or '<p class="empty">No scan yet. Run the clip workflow.</p>'
    def link(s):
        url = s.get("youtube", "")
        return f'<a href="{e(url, quote=True)}">Watch</a>' if url.startswith("https") else '<span class="mute">not posted</span>'

    clips = "".join(
        f'<tr><td class="mute">{e(s["date"])}</td><td>{e(s["title"])}<br><span class="pill">{e(s.get("niche") or "other")}</span></td>'
        f"<td>{link(s)}</td></tr>" for s in reversed(posted[-15:]))
    table = (f"<table><tr><th>Date</th><th>Clip</th><th></th></tr>{clips}</table>" if clips
             else '<p class="empty">No clips yet.</p>')
    skipped = len(seen) - len(posted)
    live = sum(1 for s in posted if s.get("youtube", "").startswith("https"))
    kpi = lambda big, small: f'<div class="card kpi"><b>{big}</b><span>{small}</span></div>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clippa Dashboard</title><style>{CSS}</style></head><body><main>
<header><h1>Clippa</h1><span class="mute">Last scan: {e(scan.get("date", "never"))}</span></header>
<div class="kpis">{kpi(len(niches), "niches scanned")}{kpi(e(niches[0]["name"]) if niches else "-", "hottest niche this week")}
{kpi(live, "clips on YouTube")}{kpi(skipped, "moments skipped by Claude")}</div>
<div class="grid"><section class="card"><h2>Most viewed niches</h2>{rows}</section>
<section class="card"><h2>Latest clips</h2>{table}</section></div></main></body></html>"""


def write(scan, seen, out):
    out.parent.mkdir(exist_ok=True)
    out.write_text(build(scan, seen))
