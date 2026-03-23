"""
HTML card renderers for the custom embed system.
Renders beautiful informational cards and static map images.
"""

import urllib.parse
from html import escape

from config import get_settings


def render_places_card(data: dict) -> str:
    """Render a rich card for places (search/explore results)."""
    title = escape(data.get("title", "Places"))
    subtitle = escape(data.get("subtitle") or "")
    places = data.get("places", [])
    count = len(places)

    place_rows = ""
    for i, p in enumerate(places):
        name = escape(p.get("name", "Unknown"))
        address = escape(p.get("address", ""))
        rating = p.get("rating")
        reviews = p.get("user_ratings_total")
        price_level = p.get("price_level")
        open_now = p.get("open_now")
        types = p.get("types", [])[:2]

        rating_html = ""
        if rating:
            full = int(rating)
            stars = "\u2605" * full + "\u2606" * (5 - full)
            rating_html = (
                f'<span class="stars">{stars}</span> <span class="rn">{rating}</span>'
            )
            if reviews:
                rating_html += f' <span class="rv">({reviews:,} reviews)</span>'

        price_html = ""
        if price_level is not None:
            price_html = f'<span class="pr">{"$" * (price_level + 1)}</span>'

        status_html = ""
        if open_now is not None:
            if open_now:
                status_html = '<span class="op">\u25cf Open</span>'
            else:
                status_html = '<span class="cl">\u25cf Closed</span>'

        types_html = ""
        if types:
            t_str = " \u00b7 ".join(escape(t.replace("_", " ").title()) for t in types)
            types_html = f'<div class="pt">{t_str}</div>'

        meta = " ".join(filter(None, [rating_html, price_html, status_html]))
        maps_url = p.get("maps_url", "")
        if maps_url:
            safe_url = escape(maps_url)
            name_html = (
                f'<a class="nm" href="{safe_url}" onclick="return gl(this)">{name}</a>'
            )
        else:
            name_html = f'<div class="nm">{name}</div>'

        place_rows += f"""
        <div class="p">
            <div class="pn">{i + 1}</div>
            <div class="pi">
                {name_html}
                {types_html}
                {f'<div class="mt">{meta}</div>' if meta else ""}
                <div class="ad">\U0001f4cd {address}</div>
            </div>
        </div>"""

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#1a1a2e;color:#e0e0e0}}
.c{{padding:16px 20px}}
.hd{{margin-bottom:14px}}
.tl{{font-size:16px;font-weight:700;color:#fff;display:flex;align-items:center;gap:8px}}
.ti{{font-size:20px}}
.st{{font-size:12px;color:#8888aa;margin-top:4px}}
.ct{{background:#2d2d4a;color:#7c7cff;font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600}}
.p{{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #2a2a3e}}
.p:last-child{{border-bottom:none}}
.pn{{min-width:24px;height:24px;background:#2d2d4a;color:#7c7cff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;margin-top:2px}}
.pi{{flex:1;min-width:0}}
a.nm{{text-decoration:none}}
.nm{{font-size:14px;font-weight:600;color:#fff;margin-bottom:3px}}
.pt{{font-size:11px;color:#8888aa;margin-bottom:3px}}
.mt{{font-size:12px;color:#b0b0cc;margin-bottom:3px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}}
.stars{{color:#ffc107;letter-spacing:1px}}
.rn{{color:#ffc107;font-weight:600}}
.rv{{color:#8888aa;font-size:11px}}
.pr{{color:#66bb6a;font-weight:600}}
.op{{color:#66bb6a;font-size:11px;font-weight:600}}
.cl{{color:#ef5350;font-size:11px;font-weight:600}}
.ad{{font-size:11px;color:#8888aa;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
</style></head><body>
<div class="c">
    <div class="hd">
        <div class="tl">
            <span class="ti">\U0001f4cd</span>
            {title}
            <span class="ct">{count} places</span>
        </div>
        {f'<div class="st">{subtitle}</div>' if subtitle else ""}
    </div>
    {place_rows}
</div>
<script>
function gl(a){{try{{window.top.location.href=a.href}}catch(e){{window.open(a.href,'_blank')}}return false}}
const h=document.body.scrollHeight;
window.parent.postMessage({{type:'iframe:height',height:h}},'*');
window.addEventListener('load',()=>window.parent.postMessage({{type:'iframe:height',height:document.body.scrollHeight}},'*'));
</script>
</body></html>"""


def render_directions_card(data: dict) -> str:
    """Render a rich card for directions results."""
    origin = escape(data.get("origin", ""))
    destination = escape(data.get("destination", ""))
    distance = escape(data.get("distance", ""))
    duration = escape(data.get("duration", ""))
    travel_mode = data.get("travel_mode", "driving")
    steps = data.get("steps", [])

    mode_icons = {
        "driving": "\U0001f697",
        "walking": "\U0001f6b6",
        "transit": "\U0001f68c",
        "bicycling": "\U0001f6b2",
    }
    mode_icon = mode_icons.get(travel_mode, "\U0001f5fa\ufe0f")
    mode_label = escape(travel_mode.title())

    step_rows = ""
    for i, s in enumerate(steps):
        instruction = s.get("instruction", "")
        dist = escape(s.get("distance", ""))
        dur = escape(s.get("duration", ""))
        step_rows += f"""
        <div class="s">
            <div class="sn">{i + 1}</div>
            <div class="si">
                <div class="sx">{instruction}</div>
                <div class="sm">{dist} \u00b7 {dur}</div>
            </div>
        </div>"""

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#1a1a2e;color:#e0e0e0}}
.c{{padding:16px 20px}}
.rh{{background:#2d2d4a;border-radius:10px;padding:14px 16px;margin-bottom:14px}}
.rm{{display:flex;align-items:center;gap:8px;margin-bottom:10px}}
.mi{{font-size:22px}}
.ml{{font-size:13px;color:#7c7cff;font-weight:600;text-transform:uppercase;letter-spacing:.5px}}
.rp{{display:flex;flex-direction:column;gap:6px}}
.rpt{{display:flex;align-items:center;gap:8px;font-size:13px}}
.dot{{width:10px;height:10px;border-radius:50%}}
.dot.og{{background:#66bb6a}}
.dot.ds{{background:#ef5350}}
.rs{{display:flex;gap:16px;margin-top:10px;padding-top:10px;border-top:1px solid #3a3a5a}}
.ri{{text-align:center;flex:1}}
.rv{{font-size:18px;font-weight:700;color:#fff}}
.rl{{font-size:11px;color:#8888aa;margin-top:2px}}
.sh{{font-size:13px;font-weight:600;color:#8888aa;margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px}}
.s{{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #2a2a3e}}
.s:last-child{{border-bottom:none}}
.sn{{min-width:22px;height:22px;background:#2d2d4a;color:#7c7cff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;margin-top:2px}}
.si{{flex:1}}
.sx{{font-size:13px;color:#e0e0e0;line-height:1.4}}
.sm{{font-size:11px;color:#8888aa;margin-top:2px}}
</style></head><body>
<div class="c">
    <div class="rh">
        <div class="rm">
            <span class="mi">{mode_icon}</span>
            <span class="ml">{mode_label}</span>
        </div>
        <div class="rp">
            <div class="rpt"><span class="dot og"></span><span>{origin}</span></div>
            <div class="rpt"><span class="dot ds"></span><span>{destination}</span></div>
        </div>
        <div class="rs">
            <div class="ri"><div class="rv">{distance}</div><div class="rl">Distance</div></div>
            <div class="ri"><div class="rv">{duration}</div><div class="rl">Duration</div></div>
        </div>
    </div>
    <div class="sh">Route Steps ({len(steps)})</div>
    {step_rows}
</div>
<script>
const h=document.body.scrollHeight;
window.parent.postMessage({{type:'iframe:height',height:h}},'*');
window.addEventListener('load',()=>window.parent.postMessage({{type:'iframe:height',height:document.body.scrollHeight}},'*'));
</script>
</body></html>"""


def render_places_map(data: dict) -> str:
    """Render a Google Maps Static API image with numbered markers for places."""
    places = data.get("places", [])
    api_key = get_settings().google_maps_api_key

    marker_parts = []
    for i, p in enumerate(places):
        lat = p.get("lat")
        lng = p.get("lng")
        if lat is not None and lng is not None:
            label = str(i + 1) if i < 9 else chr(65 + i - 9)
            marker_parts.append(f"markers=color:red%7Clabel:{label}%7C{lat},{lng}")

    markers_str = "&".join(marker_parts)
    map_url = (
        f"https://maps.googleapis.com/maps/api/staticmap"
        f"?size=640x400&scale=2&maptype=roadmap&{markers_str}"
        f"&key={api_key}"
    )

    gmaps_url = data.get("maps_url", "")
    if gmaps_url:
        safe_gmaps = escape(gmaps_url)
        img_html = f'<a href="{safe_gmaps}" onclick="return gl(this)"><img src="{map_url}" alt="Map"></a>'
    else:
        img_html = f'<img src="{map_url}" alt="Map">'

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:#1a1a2e;overflow:hidden}}
.w{{padding:6px}}
img{{width:100%;display:block;border-radius:8px;cursor:pointer}}
</style></head><body>
<div class="w">
    {img_html}
</div>
<script>
function gl(a){{try{{window.top.location.href=a.href}}catch(e){{window.open(a.href,'_blank')}}return false}}
window.addEventListener('load',()=>{{
const h=document.body.scrollHeight;
window.parent.postMessage({{type:'iframe:height',height:h}},'*');
}});
</script>
</body></html>"""


def render_directions_map(data: dict) -> str:
    """Render a Google Maps Static API image with route polyline."""
    api_key = get_settings().google_maps_api_key
    polyline = data.get("overview_polyline", "")
    origin_lat = data.get("origin_lat")
    origin_lng = data.get("origin_lng")
    dest_lat = data.get("dest_lat")
    dest_lng = data.get("dest_lng")

    parts = ["size=640x400", "scale=2", "maptype=roadmap"]

    if polyline:
        encoded_poly = urllib.parse.quote(polyline, safe="")
        parts.append(f"path=weight:4%7Ccolor:0x4285F4FF%7Cenc:{encoded_poly}")

    if origin_lat is not None and origin_lng is not None:
        parts.append(f"markers=color:green%7Clabel:A%7C{origin_lat},{origin_lng}")

    if dest_lat is not None and dest_lng is not None:
        parts.append(f"markers=color:red%7Clabel:B%7C{dest_lat},{dest_lng}")

    map_url = (
        f"https://maps.googleapis.com/maps/api/staticmap"
        f"?{'&'.join(parts)}&key={api_key}"
    )

    gmaps_url = data.get("maps_url", "")
    if gmaps_url:
        safe_gmaps = escape(gmaps_url)
        img_html = f'<a href="{safe_gmaps}" onclick="return gl(this)"><img src="{map_url}" alt="Route map"></a>'
    else:
        img_html = f'<img src="{map_url}" alt="Route map">'

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:#1a1a2e;overflow:hidden}}
.w{{padding:6px}}
img{{width:100%;display:block;border-radius:8px;cursor:pointer}}
</style></head><body>
<div class="w">
    {img_html}
</div>
<script>
function gl(a){{try{{window.top.location.href=a.href}}catch(e){{window.open(a.href,'_blank')}}return false}}
window.addEventListener('load',()=>{{
const h=document.body.scrollHeight;
window.parent.postMessage({{type:'iframe:height',height:h}},'*');
}});
</script>
</body></html>"""
