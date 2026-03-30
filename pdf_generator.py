#!/usr/bin/env python3
"""
JustRent Marbella PDF Generator
Downloads property images and builds styled A4 PDFs with ReportLab.
Run after scraper.py, before or alongside generator.py.
"""

import json
import os
import glob
import io
import requests
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, Color
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CACHE_DIR = os.path.join(BASE_DIR, ".image_cache")

W, H = A4
MARGIN = 20 * mm
CONTENT_W = W - 2 * MARGIN

# ── Colours ──
CHARCOAL = HexColor("#2C2C2C")
MID = HexColor("#6B6B6B")
LIGHT = HexColor("#E8E8E8")
SAND = HexColor("#F5F0EB")
ACCENT = HexColor("#8B7355")

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def download_image(url):
    """Download an image and return its local cached path."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    fname = url.split("/")[-1]
    cached = os.path.join(CACHE_DIR, fname)
    if os.path.exists(cached):
        return cached
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        with open(cached, "wb") as f:
            f.write(resp.content)
        return cached
    except Exception as e:
        print(f"      Image failed: {e}")
        return None


def fit_image(c, img_path, x, y, max_w, max_h):
    """Draw an image scaled to fit within max_w x max_h, covering the area."""
    try:
        with Image.open(img_path) as img:
            iw, ih = img.size
        aspect = iw / ih
        target_aspect = max_w / max_h

        if aspect > target_aspect:
            draw_h = max_h
            draw_w = max_h * aspect
        else:
            draw_w = max_w
            draw_h = max_w / aspect

        # Center crop via clipping
        c.saveState()
        p = c.beginPath()
        p.rect(x, y, max_w, max_h)
        p.close()
        c.clipPath(p, stroke=0)

        offset_x = x + (max_w - draw_w) / 2
        offset_y = y + (max_h - draw_h) / 2
        c.drawImage(img_path, offset_x, offset_y, draw_w, draw_h)
        c.restoreState()
        return True
    except Exception:
        return False


def draw_divider(c, y):
    c.setStrokeColor(LIGHT)
    c.setLineWidth(0.5)
    c.line(MARGIN, y, W - MARGIN, y)


def build_pdf(prop, output_path):
    """Build a complete property PDF."""
    c = canvas.Canvas(output_path, pagesize=A4)
    c.setTitle(f"{prop.get('name', 'Property')}")

    name = prop.get("name", "Property")
    location = prop.get("location", "")
    photos = prop.get("photos", [])
    description = prop.get("description", "")
    bedrooms_detail = prop.get("bedrooms_detail", [])
    features = prop.get("features", [])
    distances = prop.get("distances", [])
    services_incl = prop.get("services_included", [])
    services_opt = prop.get("services_optional", [])
    checkin = prop.get("checkin", "")
    checkout = prop.get("checkout", "")
    deposit = prop.get("deposit", "")
    rules = prop.get("rules", [])
    registration = prop.get("registration", "")

    facts = []
    if prop.get("bedrooms"):
        facts.append((prop["bedrooms"], "BEDROOMS"))
    if prop.get("bathrooms"):
        facts.append((prop["bathrooms"], "BATHROOMS"))
    if prop.get("guests"):
        facts.append((prop["guests"], "GUESTS"))
    if prop.get("area"):
        facts.append((prop["area"], "LIVING AREA"))

    # Download hero image
    hero_path = download_image(photos[0]) if photos else None

    # ═══════════════════════════════════════
    # PAGE 1 — Hero + Facts + Description
    # ═══════════════════════════════════════

    hero_h = 300
    hero_y = H - hero_h

    if hero_path:
        fit_image(c, hero_path, 0, hero_y, W, hero_h)

    # Dark gradient overlay at bottom of hero
    for i in range(80):
        alpha = (i / 80) * 0.8
        c.setFillColor(Color(0.08, 0.08, 0.08, alpha))
        c.rect(0, hero_y + (80 - i), W, 1, fill=1, stroke=0)

    # Property name
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 28)
    c.drawString(MARGIN, hero_y + 28, name)
    c.setFont("Helvetica", 12)
    c.setFillColor(Color(1, 1, 1, 0.8))
    c.drawString(MARGIN, hero_y + 10, f"{location}, Costa del Sol")

    # ── Key Facts ──
    if facts:
        facts_y = hero_y - 55
        col_w = CONTENT_W / len(facts)
        for i, (val, label) in enumerate(facts):
            cx = MARGIN + col_w * i + col_w / 2
            c.setFillColor(CHARCOAL)
            c.setFont("Helvetica-Bold", 20)
            c.drawCentredString(cx, facts_y + 6, str(val))
            c.setFillColor(MID)
            c.setFont("Helvetica", 7)
            c.drawCentredString(cx, facts_y - 8, label)
        draw_divider(c, facts_y - 18)
        cursor_y = facts_y - 36
    else:
        cursor_y = hero_y - 30

    # ── Description ──
    c.setFillColor(CHARCOAL)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, cursor_y, "About the Property")

    style = ParagraphStyle("desc", fontName="Helvetica", fontSize=9, leading=14,
                           textColor=MID, alignment=TA_JUSTIFY)
    p = Paragraph(description, style)
    pw, ph = p.wrap(CONTENT_W, 300)
    cursor_y -= 14
    p.drawOn(c, MARGIN, cursor_y - ph)
    cursor_y = cursor_y - ph - 12
    draw_divider(c, cursor_y)
    cursor_y -= 24

    # ── Bedrooms ──
    if bedrooms_detail:
        c.setFillColor(CHARCOAL)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(MARGIN, cursor_y, "Bedroom Layout")
        cursor_y -= 20

        col_w = CONTENT_W / min(len(bedrooms_detail), 5)
        for i, bd in enumerate(bedrooms_detail[:5]):
            cx = MARGIN + col_w * i + col_w / 2
            box_w = col_w - 8
            box_x = cx - box_w / 2
            c.setFillColor(SAND)
            c.roundRect(box_x, cursor_y - 26, box_w, 34, 4, fill=1, stroke=0)
            c.setFillColor(CHARCOAL)
            c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(cx, cursor_y - 6, bd["room"])
            c.setFillColor(MID)
            c.setFont("Helvetica", 7)
            c.drawCentredString(cx, cursor_y - 18, bd["bed"])

        cursor_y -= 40
        draw_divider(c, cursor_y)
        cursor_y -= 24

    # ── Features ──
    if features:
        c.setFillColor(CHARCOAL)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(MARGIN, cursor_y, "Views & Highlights")
        cursor_y -= 18

        tag_x = MARGIN
        tag_pad = 8
        for tag_text in features:
            tw = c.stringWidth(tag_text, "Helvetica", 8) + 2 * tag_pad
            if tag_x + tw > W - MARGIN:
                tag_x = MARGIN
                cursor_y -= 20
            c.setFillColor(SAND)
            c.roundRect(tag_x, cursor_y - 3, tw, 17, 8, fill=1, stroke=0)
            c.setFillColor(CHARCOAL)
            c.setFont("Helvetica", 8)
            c.drawString(tag_x + tag_pad, cursor_y + 2, tag_text)
            tag_x += tw + 5

        cursor_y -= 28
        draw_divider(c, cursor_y)
        cursor_y -= 24

    # ── Distances ──
    if distances:
        c.setFillColor(CHARCOAL)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(MARGIN, cursor_y, "Distances")
        cursor_y -= 18

        dist_col_w = CONTENT_W / 2
        for i, d in enumerate(distances):
            col = i % 2
            row = i // 2
            x = MARGIN + col * dist_col_w
            y = cursor_y - row * 16
            c.setFillColor(ACCENT)
            c.circle(x + 4, y + 3, 2, fill=1, stroke=0)
            c.setFillColor(CHARCOAL)
            c.setFont("Helvetica", 9)
            c.drawString(x + 12, y, d["place"])
            c.setFillColor(MID)
            c.setFont("Helvetica-Bold", 9)
            c.drawRightString(x + dist_col_w - 20, y, d["distance"])

        rows_needed = (len(distances) + 1) // 2
        cursor_y -= rows_needed * 16 + 12
        draw_divider(c, cursor_y)
        cursor_y -= 24

    # ── Services ──
    if services_incl or services_opt:
        c.setFillColor(CHARCOAL)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(MARGIN, cursor_y, "Included & Additional")
        cursor_y -= 18

        c.setFillColor(MID)
        c.setFont("Helvetica", 9)
        for item in services_incl:
            c.drawString(MARGIN + 8, cursor_y, item)
            cursor_y -= 13

        if services_opt:
            cursor_y -= 4
            c.setFillColor(CHARCOAL)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(MARGIN + 8, cursor_y, "Optional:")
            cursor_y -= 13
            c.setFillColor(MID)
            c.setFont("Helvetica", 9)
            for item in services_opt:
                c.drawString(MARGIN + 8, cursor_y, item)
                cursor_y -= 13

        cursor_y -= 8

    # ── Check-in / Rules ──
    if checkin or checkout:
        c.setFillColor(SAND)
        c.roundRect(MARGIN, cursor_y - 18, CONTENT_W, 28, 4, fill=1, stroke=0)
        c.setFillColor(CHARCOAL)
        c.setFont("Helvetica-Bold", 9)
        if checkin:
            c.drawString(MARGIN + 12, cursor_y - 8, f"Check-in: {checkin}")
        if checkout:
            c.drawString(W / 2, cursor_y - 8, f"Check-out: {checkout}")
        cursor_y -= 30

    if deposit:
        c.setFillColor(MID)
        c.setFont("Helvetica", 8)
        c.drawString(MARGIN, cursor_y, f"Security deposit: {deposit} (refundable)")
        cursor_y -= 12

    if rules:
        c.setFillColor(MID)
        c.setFont("Helvetica", 8)
        c.drawString(MARGIN, cursor_y, ". ".join(rules) + ".")
        cursor_y -= 12

    # Footer
    if registration:
        c.setFillColor(LIGHT)
        c.setFont("Helvetica", 7)
        c.drawCentredString(W / 2, 16, registration)

    # ═══════════════════════════════════════
    # PAGE 2 — Photo Grid
    # ═══════════════════════════════════════
    if len(photos) > 1:
        c.showPage()

        c.setFillColor(CHARCOAL)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(MARGIN, H - MARGIN - 4, "Gallery")

        grid_top = H - MARGIN - 24
        gutter = 5
        photo_paths = []
        for url in photos[1:12]:  # Up to 11 gallery photos
            path = download_image(url)
            if path:
                photo_paths.append(path)

        if photo_paths:
            # Row 1: 2 large photos
            row_y = grid_top
            ph_h_large = 170
            ph_w_2 = (CONTENT_W - gutter) / 2

            for i, path in enumerate(photo_paths[:2]):
                x = MARGIN + i * (ph_w_2 + gutter)
                fit_image(c, path, x, row_y - ph_h_large, ph_w_2, ph_h_large)

            row_y -= ph_h_large + gutter

            # Row 2+: 3-column grid
            ph_w_3 = (CONTENT_W - 2 * gutter) / 3
            ph_h_small = 130
            remaining = photo_paths[2:]

            for i, path in enumerate(remaining):
                col = i % 3
                row = i // 3
                x = MARGIN + col * (ph_w_3 + gutter)
                y = row_y - (row + 1) * (ph_h_small + gutter) + gutter
                if y < 30:
                    break
                fit_image(c, path, x, y, ph_w_3, ph_h_small)

        if registration:
            c.setFillColor(LIGHT)
            c.setFont("Helvetica", 7)
            c.drawCentredString(W / 2, 16, registration)

    c.save()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("JustRent Marbella PDF Generator")
    print("=" * 60)

    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    print(f"\nFound {len(files)} properties\n")

    for i, filepath in enumerate(files):
        with open(filepath, "r", encoding="utf-8") as f:
            prop = json.load(f)

        slug = prop.get("slug", f"property-{i}")
        pdf_path = os.path.join(OUTPUT_DIR, f"{slug}.pdf")
        print(f"  [{i+1}/{len(files)}] {slug}")

        try:
            build_pdf(prop, pdf_path)
            print(f"    -> {slug}.pdf")
        except Exception as e:
            print(f"    ERROR: {e}")

    print(f"\n{'=' * 60}")
    print(f"PDFs saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
