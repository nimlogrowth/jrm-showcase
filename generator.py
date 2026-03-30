#!/usr/bin/env python3
"""
JustRent Marbella Showcase Generator
Reads property JSON files and generates a static site.
"""

import json
import os
import glob
import html
from urllib.parse import quote
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def load_properties():
    """Load all property JSON files."""
    properties = []
    for filepath in sorted(glob.glob(os.path.join(DATA_DIR, "*.json"))):
        with open(filepath, "r", encoding="utf-8") as f:
            properties.append(json.load(f))
    return properties


def esc(text):
    """HTML-escape text."""
    return html.escape(str(text)) if text else ""


def build_gallery_rows(photos):
    """Build alternating 2-wide and 3-wide gallery rows."""
    if len(photos) <= 1:
        return ""

    gallery_photos = photos[1:]  # First photo is hero
    rows_html = []
    i = 0
    row_type = 2  # Start with 2-wide

    while i < len(gallery_photos):
        if row_type == 2:
            chunk = gallery_photos[i:i+2]
            if len(chunk) == 2:
                rows_html.append(f'''    <div class="gallery-grid gallery-row-2"{' style="margin-top:6px;"' if rows_html else ''}>
      <img src="{esc(chunk[0])}" alt="Property photo">
      <img src="{esc(chunk[1])}" alt="Property photo">
    </div>''')
                i += 2
            else:
                rows_html.append(f'''    <div class="gallery-grid gallery-row-2"{' style="margin-top:6px;"' if rows_html else ''}>
      <img src="{esc(chunk[0])}" alt="Property photo">
    </div>''')
                i += 1
            row_type = 3
        else:
            chunk = gallery_photos[i:i+3]
            margin = ' style="margin-top:6px;"' if rows_html else ''
            if len(chunk) == 3:
                rows_html.append(f'''    <div class="gallery-grid gallery-row-3"{margin}>
      <img src="{esc(chunk[0])}" alt="Property photo">
      <img src="{esc(chunk[1])}" alt="Property photo">
      <img src="{esc(chunk[2])}" alt="Property photo">
    </div>''')
                i += 3
            elif len(chunk) == 2:
                rows_html.append(f'''    <div class="gallery-grid gallery-row-2"{margin}>
      <img src="{esc(chunk[0])}" alt="Property photo">
      <img src="{esc(chunk[1])}" alt="Property photo">
    </div>''')
                i += 2
            else:
                rows_html.append(f'''    <div class="gallery-grid gallery-row-3"{margin}>
      <img src="{esc(chunk[0])}" alt="Property photo">
    </div>''')
                i += 1
            row_type = 2

    return "\n".join(rows_html)


def build_property_page(prop):
    """Generate a full HTML page for a single property."""

    raw_name = prop.get("name", "Property")
    loc_raw = prop.get("location", "")
    type_raw = prop.get("type", "")
    name = esc(clean_name(raw_name, loc_raw, type_raw))
    location = esc(loc_raw)
    prop_type = esc(prop.get("type", ""))
    guests = esc(prop.get("guests", ""))
    bedrooms = esc(prop.get("bedrooms", ""))
    bathrooms = esc(prop.get("bathrooms", ""))
    area = esc(prop.get("area", ""))
    plot = esc(prop.get("plot", ""))
    raw_desc = prop.get("description", "")
    # Build paragraph HTML from newline-separated text
    desc_paragraphs = [p.strip() for p in raw_desc.split("\n\n") if p.strip()]
    if desc_paragraphs:
        description_html = "\n    ".join('<p>' + esc(p) + '</p>' for p in desc_paragraphs)
    else:
        description_html = '<p>' + esc(raw_desc) + '</p>'
    registration = esc(prop.get("registration", ""))
    checkin = esc(prop.get("checkin", ""))
    checkout = esc(prop.get("checkout", ""))
    deposit = esc(prop.get("deposit", ""))
    photos = prop.get("photos", [])
    hero_photo = photos[0] if photos else ""
    map_query = quote(prop.get("map_query", f"{location}, Costa del Sol"))

    # Bedrooms detail
    bedrooms_html = ""
    for bd in prop.get("bedrooms_detail", []):
        bedrooms_html += f'''      <div class="bedroom-card">
        <div class="room">{esc(bd["room"])}</div>
        <div class="bed">{esc(bd["bed"])}</div>
      </div>\n'''

    # Features tags
    features_html = ""
    for f in prop.get("features", []):
        features_html += f'      <span class="tag">{esc(f)}</span>\n'

    # Gallery
    gallery_html = build_gallery_rows(photos)

    # Distances
    distances_html = ""
    for d in prop.get("distances", []):
        distances_html += f'''      <div class="distance-row">
        <div class="distance-place"><span class="distance-dot"></span>{esc(d["place"])}</div>
        <div class="distance-value">{esc(d["distance"])}</div>
      </div>\n'''

    # Services
    included_html = ""
    for s in prop.get("services_included", []):
        included_html += f'        <div class="service-item">{esc(s)}</div>\n'
    optional_html = ""
    for s in prop.get("services_optional", []):
        optional_html += f'        <div class="service-item">{esc(s)}</div>\n'

    # Rules
    rules_text = ". ".join(prop.get("rules", []))
    if rules_text and not rules_text.endswith("."):
        rules_text += "."

    # Key facts row
    facts_items = []
    if bedrooms:
        facts_items.append(("bedrooms", bedrooms, "Bedrooms"))
    if bathrooms:
        facts_items.append(("bathrooms", bathrooms, "Bathrooms"))
    if guests:
        facts_items.append(("guests", guests, "Guests"))
    if area:
        facts_items.append(("area", area, "Living Area"))
    if plot:
        facts_items.append(("plot", plot, "Plot"))

    facts_html = ""
    for _, val, label in facts_items:
        facts_html += f'''    <div class="fact">
      <div class="fact-value">{val}</div>
      <div class="fact-label">{label}</div>
    </div>\n'''

    # Pre-build conditional sections (avoids nested f-strings for Python <3.12)
    bedrooms_section = ""
    if bedrooms_html:
        bedrooms_section = '<div class="section">\n    <h2 class="section-title">Bedroom Layout</h2>\n    <div class="bedrooms-grid">\n' + bedrooms_html + '    </div>\n  </div>'

    features_section = ""
    if features_html:
        features_section = '<div class="section">\n    <h2 class="section-title">Views &amp; Highlights</h2>\n    <div class="tags">\n' + features_html + '    </div>\n  </div>'

    gallery_section = ""
    if gallery_html:
        gallery_section = '<div class="section page-break">\n    <h2 class="section-title">Gallery</h2>\n' + gallery_html + '\n  </div>'

    distances_section = ""
    if distances_html:
        distances_section = '<h2 class="section-title" style="margin-top:8px;">Distances</h2>\n    <div class="distances-grid">\n' + distances_html + '    </div>'

    deposit_line = ""
    if deposit:
        deposit_line = '<div class="checkin-item"><strong>Security deposit</strong><span>' + deposit + ' (refundable)</span></div>'

    rules_line = ""
    if rules_text:
        rules_line = '<div class="rules">' + esc(rules_text) + '</div>'

    services_section = ""
    if included_html or optional_html:
        services_section = '<div class="section">\n    <h2 class="section-title">Included &amp; Additional</h2>\n    <div class="services-columns">\n      <div class="service-group">\n        <h4>Included</h4>\n' + included_html + '      </div>\n      <div class="service-group">\n        <h4>Optional</h4>\n' + optional_html + '      </div>\n    </div>\n    <div class="checkin-bar">\n      <div class="checkin-item"><strong>Check-in</strong><span>' + checkin + '</span></div>\n      <div class="checkin-item"><strong>Check-out</strong><span>' + checkout + '</span></div>\n      ' + deposit_line + '\n    </div>\n    ' + rules_line + '\n  </div>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} — {location}</title>
<meta name="description" content="{name} in {location}. {prop_type}. {bedrooms} bedrooms, {guests} guests.">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --charcoal: #2C2C2C;
    --dark: #1A1A1A;
    --mid: #6B6B6B;
    --light: #E8E8E8;
    --sand: #F5F0EB;
    --warm: #F9F6F2;
    --accent: #8B7355;
    --white: #FFFFFF;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'DM Sans', sans-serif;
    color: var(--charcoal);
    background: var(--white);
    -webkit-font-smoothing: antialiased;
  }}
  @media print {{
    body {{ font-size: 10pt; }}
    .hero {{ height: 420px !important; }}
    .gallery-grid img {{ break-inside: avoid; }}
    .page-break {{ page-break-before: always; }}
    .map-container, .lightbox, .back-link, .print-btn {{ display: none !important; }}
    @page {{ margin: 12mm; }}
  }}
  .back-link {{
    position: fixed;
    top: 20px;
    left: 20px;
    z-index: 100;
    background: rgba(255,255,255,0.92);
    backdrop-filter: blur(8px);
    padding: 10px 18px;
    border-radius: 24px;
    font-size: 13px;
    font-weight: 500;
    color: var(--charcoal);
    text-decoration: none;
    box-shadow: 0 2px 12px rgba(0,0,0,0.12);
    transition: background 0.15s;
  }}
  .back-link:hover {{ background: var(--white); }}
  .print-btn {{
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 100;
    background: rgba(255,255,255,0.92);
    backdrop-filter: blur(8px);
    padding: 10px 18px;
    border-radius: 24px;
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--charcoal);
    border: none;
    cursor: pointer;
    box-shadow: 0 2px 12px rgba(0,0,0,0.12);
    transition: background 0.15s;
  }}
  .print-btn:hover {{ background: var(--white); }}
  .hero {{
    position: relative;
    width: 100%;
    height: 520px;
    overflow: hidden;
    background: var(--sand);
  }}
  .hero img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }}
  .hero-overlay {{
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 48px 56px 40px;
    background: linear-gradient(transparent, rgba(20,20,20,0.85));
    color: var(--white);
  }}
  .hero-overlay h1 {{
    font-family: 'Cormorant Garamond', serif;
    font-weight: 600;
    font-size: 48px;
    letter-spacing: -0.5px;
    line-height: 1.1;
    margin-bottom: 4px;
  }}
  .hero-overlay .location {{
    font-size: 15px;
    font-weight: 300;
    opacity: 0.85;
    letter-spacing: 0.5px;
  }}
  .container {{ max-width: 1080px; margin: 0 auto; padding: 0 40px; }}
  .facts-bar {{
    display: flex;
    justify-content: space-between;
    padding: 40px 0;
    border-bottom: 1px solid var(--light);
  }}
  .fact {{ text-align: center; flex: 1; }}
  .fact-value {{
    font-family: 'Cormorant Garamond', serif;
    font-size: 32px;
    font-weight: 600;
    color: var(--charcoal);
    line-height: 1.2;
  }}
  .fact-label {{
    font-size: 11px;
    font-weight: 500;
    color: var(--mid);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-top: 4px;
  }}
  .section {{
    padding: 48px 0;
    border-bottom: 1px solid var(--light);
  }}
  .section:last-child {{ border-bottom: none; }}
  .section-title {{
    font-family: 'Cormorant Garamond', serif;
    font-size: 28px;
    font-weight: 600;
    margin-bottom: 20px;
    color: var(--charcoal);
  }}
  .section p {{
    font-size: 15px;
    line-height: 1.75;
    color: var(--mid);
    max-width: 820px;
  }}
  .bedrooms-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 10px;
    margin-top: 24px;
  }}
  .bedroom-card {{
    background: var(--sand);
    border-radius: 8px;
    padding: 20px 12px;
    text-align: center;
  }}
  .bedroom-card .room {{ font-weight: 600; font-size: 13px; margin-bottom: 4px; }}
  .bedroom-card .bed {{ font-size: 12px; color: var(--mid); }}
  .tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 20px;
  }}
  .tag {{
    background: var(--sand);
    padding: 8px 16px;
    border-radius: 24px;
    font-size: 13px;
    color: var(--charcoal);
  }}
  .gallery-grid {{ display: grid; gap: 6px; margin-top: 24px; }}
  .gallery-row-2 {{ grid-template-columns: 1fr 1fr; }}
  .gallery-row-3 {{ grid-template-columns: 1fr 1fr 1fr; }}
  .gallery-grid img {{
    width: 100%;
    height: 220px;
    object-fit: cover;
    border-radius: 6px;
    display: block;
    background: var(--sand);
    cursor: pointer;
    transition: opacity 0.15s;
  }}
  .gallery-grid img:hover, .hero img {{ cursor: pointer; }}
  .gallery-grid img:hover {{ opacity: 0.88; }}
  .gallery-row-2 img {{ height: 280px; }}
  .map-container {{
    width: 100%;
    height: 360px;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 36px;
    border: 1px solid var(--light);
  }}
  .map-container iframe {{
    width: 100%;
    height: 100%;
    border: 0;
    display: block;
  }}
  .distances-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
    margin-top: 20px;
  }}
  .distance-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 20px;
    border-bottom: 1px solid var(--light);
  }}
  .distance-row:nth-child(odd) {{
    border-right: 1px solid var(--light);
    padding-right: 40px;
  }}
  .distance-row:nth-child(even) {{ padding-left: 40px; }}
  .distance-place {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
  }}
  .distance-dot {{
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent);
    flex-shrink: 0;
  }}
  .distance-value {{
    font-weight: 600;
    font-size: 14px;
    color: var(--charcoal);
    white-space: nowrap;
  }}
  .services-columns {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 40px;
    margin-top: 20px;
  }}
  .service-group h4 {{
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--accent);
    margin-bottom: 14px;
  }}
  .service-item {{
    font-size: 14px;
    color: var(--mid);
    padding: 8px 0;
    border-bottom: 1px solid var(--light);
  }}
  .service-item:last-child {{ border-bottom: none; }}
  .checkin-bar {{
    display: flex;
    gap: 40px;
    margin-top: 32px;
    padding: 24px 32px;
    background: var(--sand);
    border-radius: 8px;
  }}
  .checkin-item strong {{
    font-size: 14px;
    display: block;
    margin-bottom: 2px;
  }}
  .checkin-item span {{ font-size: 13px; color: var(--mid); }}
  .rules {{ margin-top: 20px; font-size: 13px; color: var(--mid); line-height: 1.7; }}
  .footer {{
    text-align: center;
    padding: 32px 0;
    font-size: 11px;
    color: var(--light);
    letter-spacing: 0.5px;
  }}
  /* ── Lightbox ── */
  .lightbox {{
    display: none; position: fixed; inset: 0; z-index: 9999;
    background: rgba(10,10,10,0.97); flex-direction: column;
    opacity: 0; transition: opacity 0.25s ease;
  }}
  .lightbox.active {{ display: flex; opacity: 1; }}
  .lb-main {{
    flex: 1; display: flex; align-items: center; justify-content: center;
    position: relative; min-height: 0; padding: 20px 80px;
  }}
  .lb-main img {{
    max-width: 100%; max-height: 100%; object-fit: contain;
    border-radius: 4px; user-select: none; transition: opacity 0.2s ease;
  }}
  .lb-close {{
    position: absolute; top: 16px; right: 20px; width: 44px; height: 44px;
    background: none; border: none; cursor: pointer; z-index: 10001;
    display: flex; align-items: center; justify-content: center;
  }}
  .lb-close svg {{ width: 28px; height: 28px; stroke: rgba(255,255,255,0.7); transition: stroke 0.15s; }}
  .lb-close:hover svg {{ stroke: #fff; }}
  .lb-nav {{
    position: absolute; top: 50%; transform: translateY(-50%);
    width: 48px; height: 48px;
    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
    border-radius: 50%; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.15s, border-color 0.15s; z-index: 10001;
  }}
  .lb-nav:hover {{ background: rgba(255,255,255,0.15); border-color: rgba(255,255,255,0.3); }}
  .lb-nav svg {{ width: 20px; height: 20px; stroke: rgba(255,255,255,0.8); }}
  .lb-prev {{ left: 16px; }}
  .lb-next {{ right: 16px; }}
  .lb-counter {{
    position: absolute; top: 24px; left: 50%; transform: translateX(-50%);
    font-family: 'DM Sans', sans-serif; font-size: 13px;
    color: rgba(255,255,255,0.45); letter-spacing: 1px;
  }}
  .lb-thumbs {{ flex-shrink: 0; width: 100%; padding: 12px 0 16px; overflow: hidden; position: relative; }}
  .lb-thumbs-track {{
    display: flex; gap: 6px; padding: 0 24px;
    transition: transform 0.3s ease; will-change: transform;
  }}
  .lb-thumb {{
    flex-shrink: 0; width: 80px; height: 54px; border-radius: 4px;
    object-fit: cover; cursor: pointer; opacity: 0.35;
    transition: opacity 0.2s, outline-color 0.2s;
    outline: 2px solid transparent; outline-offset: 2px;
  }}
  .lb-thumb:hover {{ opacity: 0.7; }}
  .lb-thumb.active {{ opacity: 1; outline-color: rgba(255,255,255,0.6); }}
  @media (max-width: 768px) {{
    .hero {{ height: 360px; }}
    .hero-overlay {{ padding: 32px 24px 28px; }}
    .hero-overlay h1 {{ font-size: 32px; }}
    .container {{ padding: 0 20px; }}
    .facts-bar {{ flex-wrap: wrap; gap: 20px; }}
    .fact {{ min-width: 30%; }}
    .gallery-row-2 img {{ height: 180px; }}
    .gallery-grid img {{ height: 160px; }}
    .distances-grid {{ grid-template-columns: 1fr; }}
    .distance-row:nth-child(odd) {{ border-right: none; padding-right: 20px; }}
    .distance-row:nth-child(even) {{ padding-left: 20px; }}
    .services-columns {{ grid-template-columns: 1fr; gap: 24px; }}
    .checkin-bar {{ flex-direction: column; gap: 16px; }}
    .map-container {{ height: 260px; }}
    .lb-main {{ padding: 16px 52px; }}
    .lb-nav {{ width: 40px; height: 40px; }}
    .lb-prev {{ left: 8px; }}
    .lb-next {{ right: 8px; }}
    .lb-thumb {{ width: 60px; height: 40px; }}
    .lb-thumbs-track {{ gap: 4px; padding: 0 12px; }}
  }}
</style>
</head>
<body>

<a href="index.html" class="back-link">&#8592; All Properties</a>
<button class="print-btn" onclick="window.print()">Save as PDF</button>

<div class="hero">
  <img src="{esc(hero_photo)}" alt="{name}">
  <div class="hero-overlay">
    <h1>{name}</h1>
    <div class="location">{location}, Costa del Sol</div>
  </div>
</div>

<div class="container">
  <div class="facts-bar">
{facts_html}  </div>

  <div class="section">
    <h2 class="section-title">About the Property</h2>
    {description_html}
  </div>

  {bedrooms_section}

  {features_section}

  {gallery_section}

  <div class="section">
    <h2 class="section-title">Location</h2>
    <div class="map-container">
      <iframe src="https://maps.google.com/maps?q={map_query}&t=&z=14&ie=UTF8&iwloc=&output=embed" loading="lazy" allowfullscreen></iframe>
    </div>
    {distances_section}
  </div>

  {services_section}

</div>

<div class="footer">{registration}</div>

<!-- Lightbox -->
<div class="lightbox" id="lightbox">
  <button class="lb-close" id="lb-close" aria-label="Close">
    <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
  </button>
  <div class="lb-counter" id="lb-counter"></div>
  <div class="lb-main">
    <button class="lb-nav lb-prev" id="lb-prev" aria-label="Previous">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
    </button>
    <img id="lb-img" src="" alt="">
    <button class="lb-nav lb-next" id="lb-next" aria-label="Next">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 6 15 12 9 18"/></svg>
    </button>
  </div>
  <div class="lb-thumbs" id="lb-thumbs">
    <div class="lb-thumbs-track" id="lb-thumbs-track"></div>
  </div>
</div>

<script>
(function() {{
  var lb=document.getElementById('lightbox'),lbImg=document.getElementById('lb-img'),
  lbCounter=document.getElementById('lb-counter'),thumbsTrack=document.getElementById('lb-thumbs-track'),
  thumbsContainer=document.getElementById('lb-thumbs'),images=[],thumbEls=[],current=0;
  document.querySelectorAll('.hero img, .gallery-grid img').forEach(function(img,i){{
    images.push(img.src);img.addEventListener('click',function(){{open(i);}});
  }});
  images.forEach(function(src,i){{
    var t=document.createElement('img');t.className='lb-thumb';t.src=src;t.alt='';
    t.addEventListener('click',function(){{current=i;update();}});
    thumbsTrack.appendChild(t);thumbEls.push(t);
  }});
  function open(i){{current=i;update();lb.classList.add('active');document.body.style.overflow='hidden';}}
  function close(){{lb.classList.remove('active');document.body.style.overflow='';}}
  function update(){{
    lbImg.src=images[current];lbCounter.textContent=(current+1)+' / '+images.length;
    thumbEls.forEach(function(t,i){{t.classList.toggle('active',i===current);}});
    var thumb=thumbEls[current];if(thumb){{
      var o=thumb.offsetLeft-(thumbsContainer.offsetWidth/2)+(thumb.offsetWidth/2);
      thumbsTrack.style.transform='translateX('+(-Math.max(0,o))+'px)';
    }}
  }}
  function prev(){{current=(current-1+images.length)%images.length;update();}}
  function next(){{current=(current+1)%images.length;update();}}
  document.getElementById('lb-close').addEventListener('click',close);
  document.getElementById('lb-prev').addEventListener('click',prev);
  document.getElementById('lb-next').addEventListener('click',next);
  lb.addEventListener('click',function(e){{if(e.target===lb||e.target.classList.contains('lb-main'))close();}});
  document.addEventListener('keydown',function(e){{
    if(!lb.classList.contains('active'))return;
    if(e.key==='Escape')close();if(e.key==='ArrowLeft')prev();if(e.key==='ArrowRight')next();
  }});
  var tx=0,lbM=document.querySelector('.lb-main');
  lbM.addEventListener('touchstart',function(e){{tx=e.changedTouches[0].screenX;}},{{passive:true}});
  lbM.addEventListener('touchend',function(e){{var d=e.changedTouches[0].screenX-tx;if(Math.abs(d)>50)d>0?prev():next();}},{{passive:true}});
}})();
</script>

</body>
</html>'''


def clean_name(raw_name, location, prop_type):
    """Remove location and type suffixes from property name."""
    clean = raw_name
    # Try removing location with and without space
    for loc_variant in [location, location.replace(" ", "")]:
        if loc_variant and clean.endswith(loc_variant):
            clean = clean[:-len(loc_variant)].rstrip()
            break
    # Only remove type if preceded by a separator (not if it is part of the name)
    for sep in [" -", "- ", " - ", "-"]:
        suffix = sep + prop_type
        if prop_type and clean.endswith(suffix):
            clean = clean[:-len(suffix)].rstrip()
            break
    # Final cleanup
    clean = clean.rstrip(" -.,")
    return clean if clean else raw_name


def build_index_page(properties):
    """Generate the directory / index page."""

    # Sort properties A-Z by name
    properties = sorted(properties, key=lambda p: p.get("name", "").lower())

    # Collect unique locations and types for filters
    locations = sorted(set(p.get("location", "") for p in properties if p.get("location")))
    types = sorted(set(p.get("type", "") for p in properties if p.get("type")))

    # Build property cards
    cards_html = ""
    for p in properties:
        slug = p.get("slug", "")
        raw_name = p.get("name", "")
        location = esc(p.get("location", ""))
        prop_type = esc(p.get("type", ""))
        bedrooms = esc(p.get("bedrooms", ""))
        guests = esc(p.get("guests", ""))
        photo = esc(p["photos"][0]) if p.get("photos") else ""

        # Clean name: remove location and type suffixes
        name = esc(clean_name(raw_name, p.get("location", ""), p.get("type", "")))

        cards_html += f'''    <a href="{slug}.html" class="card" data-location="{location}" data-type="{prop_type}" data-bedrooms="{bedrooms}" data-guests="{guests}">
      <div class="card-img" style="background-image:url('{photo}')"></div>
      <div class="card-body">
        <h3>{name}</h3>
        <div class="card-meta">{location} &middot; {prop_type}</div>
        <div class="card-facts">
          {f'<span>{bedrooms} bed</span>' if bedrooms else ''}
          {f'<span>{guests} guests</span>' if guests else ''}
        </div>
      </div>
    </a>\n'''

    # Location filter options
    loc_options = '<option value="">All locations</option>\n'
    for loc in locations:
        loc_options += f'      <option value="{esc(loc)}">{esc(loc)}</option>\n'

    # Type filter options
    type_options = '<option value="">All types</option>\n'
    for t in types:
        type_options += f'      <option value="{esc(t)}">{esc(t)}</option>\n'

    now = datetime.utcnow().strftime("%d %B %Y")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Property Showcase — Costa del Sol</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --charcoal: #2C2C2C;
    --dark: #1A1A1A;
    --mid: #6B6B6B;
    --light: #E8E8E8;
    --sand: #F5F0EB;
    --accent: #8B7355;
    --white: #FFFFFF;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'DM Sans', sans-serif;
    color: var(--charcoal);
    background: var(--sand);
    -webkit-font-smoothing: antialiased;
  }}
  .header {{
    background: var(--white);
    padding: 40px 48px 32px;
    border-bottom: 1px solid var(--light);
  }}
  .header h1 {{
    font-family: 'Cormorant Garamond', serif;
    font-size: 36px;
    font-weight: 600;
    margin-bottom: 4px;
  }}
  .header .subtitle {{
    font-size: 14px;
    color: var(--mid);
  }}
  .filters {{
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 20px 48px;
    background: var(--white);
    border-bottom: 1px solid var(--light);
    flex-wrap: wrap;
  }}
  .filter-input {{
    padding: 10px 16px;
    border: 1px solid var(--light);
    border-radius: 8px;
    font-family: 'DM Sans', sans-serif;
    font-size: 14px;
    color: var(--charcoal);
    background: var(--white);
    outline: none;
    transition: border-color 0.15s;
  }}
  .filter-input:focus {{ border-color: var(--accent); }}
  .filter-input.search {{ flex: 1; min-width: 200px; }}
  .count {{
    margin-left: auto;
    font-size: 13px;
    color: var(--mid);
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 20px;
    padding: 32px 48px 64px;
    max-width: 1400px;
    margin: 0 auto;
  }}
  .card {{
    background: var(--white);
    border-radius: 12px;
    overflow: hidden;
    text-decoration: none;
    color: var(--charcoal);
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    transition: transform 0.2s, box-shadow 0.2s;
  }}
  .card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
  }}
  .card.hidden {{ display: none; }}
  .card-img {{
    width: 100%;
    height: 220px;
    background-size: cover;
    background-position: center;
    background-color: var(--sand);
  }}
  .card-body {{ padding: 20px 24px; }}
  .card-body h3 {{
    font-family: 'Cormorant Garamond', serif;
    font-size: 22px;
    font-weight: 600;
    margin-bottom: 4px;
  }}
  .card-meta {{
    font-size: 13px;
    color: var(--mid);
    margin-bottom: 12px;
  }}
  .card-facts {{
    display: flex;
    gap: 12px;
    font-size: 12px;
    color: var(--accent);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.8px;
  }}
  .footer-bar {{
    text-align: center;
    padding: 24px;
    font-size: 11px;
    color: var(--mid);
  }}
  @media (max-width: 768px) {{
    .header {{ padding: 24px 20px 20px; }}
    .header h1 {{ font-size: 28px; }}
    .filters {{ padding: 16px 20px; }}
    .grid {{ padding: 20px; grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<div class="header">
  <h1>Property Showcase</h1>
  <div class="subtitle">Costa del Sol &middot; {len(properties)} properties &middot; Updated {now}</div>
</div>

<div class="filters">
  <input type="text" class="filter-input search" id="search" placeholder="Search by name...">
  <select class="filter-input" id="filter-location">
    {loc_options}
  </select>
  <select class="filter-input" id="filter-type">
    {type_options}
  </select>
  <select class="filter-input" id="filter-bedrooms">
    <option value="">Bedrooms</option>
    <option value="1">1+</option>
    <option value="2">2+</option>
    <option value="3">3+</option>
    <option value="4">4+</option>
    <option value="5">5+</option>
  </select>
  <select class="filter-input" id="sort-by">
    <option value="az">Name A — Z</option>
    <option value="za">Name Z — A</option>
    <option value="beds-asc">Bedrooms: low to high</option>
    <option value="beds-desc">Bedrooms: high to low</option>
    <option value="guests-asc">Guests: low to high</option>
    <option value="guests-desc">Guests: high to low</option>
  </select>
  <span class="count" id="count">{len(properties)} properties</span>
</div>

<div class="grid" id="grid">
{cards_html}</div>

<div class="footer-bar">Last updated {now}</div>

<script>
(function() {{
  var search = document.getElementById('search');
  var locF = document.getElementById('filter-location');
  var typeF = document.getElementById('filter-type');
  var bedF = document.getElementById('filter-bedrooms');
  var sortF = document.getElementById('sort-by');
  var countEl = document.getElementById('count');
  var grid = document.getElementById('grid');
  var cards = Array.from(document.querySelectorAll('.card'));

  function sortCards() {{
    var val = sortF.value;
    cards.sort(function(a, b) {{
      if (val === 'az') return a.querySelector('h3').textContent.localeCompare(b.querySelector('h3').textContent);
      if (val === 'za') return b.querySelector('h3').textContent.localeCompare(a.querySelector('h3').textContent);
      if (val === 'beds-asc') return (parseInt(a.dataset.bedrooms)||0) - (parseInt(b.dataset.bedrooms)||0);
      if (val === 'beds-desc') return (parseInt(b.dataset.bedrooms)||0) - (parseInt(a.dataset.bedrooms)||0);
      if (val === 'guests-asc') return (parseInt(a.dataset.guests)||0) - (parseInt(b.dataset.guests)||0);
      if (val === 'guests-desc') return (parseInt(b.dataset.guests)||0) - (parseInt(a.dataset.guests)||0);
      return 0;
    }});
    cards.forEach(function(card) {{ grid.appendChild(card); }});
  }}

  function filter() {{
    var q = search.value.toLowerCase();
    var loc = locF.value;
    var typ = typeF.value;
    var beds = parseInt(bedF.value) || 0;
    var visible = 0;

    cards.forEach(function(card) {{
      var name = card.querySelector('h3').textContent.toLowerCase();
      var cLoc = card.dataset.location;
      var cType = card.dataset.type;
      var cBeds = parseInt(card.dataset.bedrooms) || 0;

      var show = true;
      if (q && name.indexOf(q) === -1) show = false;
      if (loc && cLoc !== loc) show = false;
      if (typ && cType !== typ) show = false;
      if (beds && cBeds < beds) show = false;

      card.classList.toggle('hidden', !show);
      if (show) visible++;
    }});

    countEl.textContent = visible + ' propert' + (visible === 1 ? 'y' : 'ies');
  }}

  search.addEventListener('input', filter);
  locF.addEventListener('change', filter);
  typeF.addEventListener('change', filter);
  bedF.addEventListener('change', filter);
  sortF.addEventListener('change', function() {{ sortCards(); filter(); }});
}})();
</script>

</body>
</html>'''


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("JustRent Marbella Showcase Generator")
    print("=" * 60)

    properties = load_properties()
    print(f"\nLoaded {len(properties)} properties from {DATA_DIR}\n")

    if not properties:
        print("ERROR: No property data found. Run scraper.py first.")
        return

    # Generate property pages
    for i, prop in enumerate(properties):
        slug = prop.get("slug", f"property-{i}")
        filepath = os.path.join(OUTPUT_DIR, f"{slug}.html")
        page_html = build_property_page(prop)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(page_html)
        print(f"  [{i+1}/{len(properties)}] {slug}.html")

    # Generate index page
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    index_html = build_index_page(properties)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"\n  index.html (directory page)")

    print(f"\n{'=' * 60}")
    print(f"Site generated in: {OUTPUT_DIR}")
    print(f"Open {index_path} in a browser to preview.")


if __name__ == "__main__":
    main()
