#!/usr/bin/env python3
"""
JustRent Marbella Property Scraper
Scrapes all properties from justrentmarbella.com and outputs JSON files.
Run locally or via GitHub Actions (domain access required).
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
import sys

BASE_URL = "https://www.justrentmarbella.com"
LISTING_URL = BASE_URL + "/rentals/holidays-rentals-rentals-d0/"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}
DELAY = 1.5  # seconds between requests


def get_soup(url):
    """Fetch a URL and return BeautifulSoup object."""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def get_all_property_urls():
    """Scrape all property URLs from paginated listing pages."""
    urls = []
    page = 1
    while True:
        page_url = LISTING_URL if page == 1 else f"{LISTING_URL}?pagina={page}"
        print(f"  Listing page {page}: {page_url}")
        try:
            soup = get_soup(page_url)
        except Exception as e:
            print(f"  Error fetching page {page}: {e}")
            break

        # Find property links (they follow pattern /rentals/TYPE-LOCATION-NAME-ID.html)
        links = soup.select('a[href*="/rentals/"][href$=".html"]')
        page_urls = set()
        for link in links:
            href = link.get("href", "")
            # Filter to actual property pages (have a numeric ID pattern)
            if re.search(r"-\d{5,}\.html$", href):
                full_url = href if href.startswith("http") else BASE_URL + href
                page_urls.add(full_url)

        if not page_urls:
            print(f"  No properties found on page {page}, stopping.")
            break

        urls.extend(page_urls)
        print(f"  Found {len(page_urls)} properties on page {page}")

        # Check if there is a next page
        next_link = soup.select_one(f'a[href*="pagina={page + 1}"]')
        if not next_link:
            break

        page += 1
        time.sleep(DELAY)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    return unique


def extract_property(url):
    """Extract all property data from a single property page."""
    soup = get_soup(url)
    data = {"url": url, "source_url": url}

    # ── Slug (for filename) ──
    slug = url.split("/")[-1].replace(".html", "")
    data["slug"] = slug

    # ── Name ──
    h1 = soup.select_one("h1")
    if h1:
        # Name is usually "Villa La Quinta Benahavís - Villa"
        raw = h1.get_text(strip=True)
        # Split on location/type suffix
        parts = raw.split(" - ")
        data["name"] = parts[0].strip() if parts else raw
        data["type"] = parts[1].strip() if len(parts) > 1 else ""
    else:
        data["name"] = slug.replace("-", " ").title()
        data["type"] = ""

    # ── Location from breadcrumb or URL ──
    breadcrumb = soup.select_one('a[href*="/rentals/rentals-"]')
    if breadcrumb:
        data["location"] = breadcrumb.get_text(strip=True)
    else:
        # Try to extract from URL pattern: type-location-name-id
        match = re.search(r"/rentals/\w+-(\w+)-", url)
        data["location"] = match.group(1).replace("-", " ").title() if match else ""

    # ── Key facts (occupants, bedrooms, bathrooms, area) ──
    # These are typically in the icon row at top of description
    desc_section = soup.select_one(".descripcionf, #descripcionf, .ficha-descripcion")

    # Try structured selectors first
    data["guests"] = ""
    data["bedrooms"] = ""
    data["bathrooms"] = ""
    data["area"] = ""

    # Look for the facts in list items or spans with specific patterns
    page_text = soup.get_text()

    # Occupants
    occ_el = soup.select_one('[class*="ocupant"], [class*="person"]')
    if occ_el:
        data["guests"] = occ_el.get_text(strip=True)

    # Try extracting from the structured info block
    info_items = soup.select(".descripcion-iconos li, .ficha-iconos li, .datos-alojamiento li")
    for item in info_items:
        text = item.get_text(strip=True)
        if "occupant" in text.lower() or "person" in text.lower():
            nums = re.findall(r"\d+", text)
            if nums:
                data["guests"] = nums[0]
        if "bedroom" in text.lower():
            nums = re.findall(r"\d+", text)
            if nums:
                data["bedrooms"] = nums[0]
        if "bathroom" in text.lower():
            nums = re.findall(r"\d+", text)
            if nums:
                data["bathrooms"] = nums[0]
        if "m²" in text or "m2" in text.lower():
            match_area = re.search(r"(\d[\d,.]*)\s*m", text)
            if match_area:
                data["area"] = match_area.group(1) + " m²"

    # Fallback: scan for patterns in broader elements
    if not data["guests"] or not data["bedrooms"]:
        top_section = soup.select_one(".descripcion-ficha, .ficha-top, .alojamiento-info")
        if top_section:
            top_text = top_section.get_text()
            if not data["guests"]:
                m = re.search(r"(\d+)\s*(?:occupant|guest|person|pax)", top_text, re.I)
                if m:
                    data["guests"] = m.group(1)
            if not data["bedrooms"]:
                m = re.search(r"(\d+)\s*(?:bedroom|bed room)", top_text, re.I)
                if m:
                    data["bedrooms"] = m.group(1)

    # ── Broader fallback: parse the raw page for key numbers ──
    # The Avantio template puts these in specific divs
    all_text_blocks = soup.select("div, span, p, li")
    for block in all_text_blocks:
        t = block.get_text(strip=True)
        # Match patterns like "10" next to icons, or "5 Bedrooms"
        if not data["guests"] and re.match(r"^\d{1,2}$", t):
            # Could be occupants if it's in the right context
            parent_text = block.parent.get_text(strip=True) if block.parent else ""
            if "occupant" in parent_text.lower() or "guest" in parent_text.lower():
                data["guests"] = t
        if not data["bedrooms"] and "Bedroom" in t:
            nums = re.findall(r"\d+", t)
            if nums:
                data["bedrooms"] = nums[-1]
        if not data["bathrooms"] and "Bathroom" in t:
            nums = re.findall(r"\d+", t)
            if nums:
                data["bathrooms"] = str(sum(int(n) for n in nums))
        if not data["area"] and "m²" in t and "Property" in t:
            m = re.search(r"(\d[\d,.]*)\s*m²", t)
            if m:
                data["area"] = m.group(1) + " m²"

    # ── Description ──
    desc_el = soup.select_one(".descripcion-texto, .description-text, .texto-descripcion")
    if desc_el:
        data["description"] = desc_el.get_text(strip=True)
    else:
        # Fallback: look for the first substantial paragraph after "Description"
        desc_header = soup.find(string=re.compile(r"Description|About", re.I))
        if desc_header:
            parent = desc_header.find_parent()
            if parent:
                next_p = parent.find_next("p")
                data["description"] = next_p.get_text(strip=True) if next_p else ""
            else:
                data["description"] = ""
        else:
            data["description"] = ""

    # If still no description, try meta description
    if not data["description"]:
        meta = soup.select_one('meta[name="description"]')
        if meta:
            data["description"] = meta.get("content", "")

    # ── Photos ──
    photos = []
    # Look for gallery images and hero images
    for img in soup.select('img[src*="/fotos/"], img[src*="/rentals/fotos/"]'):
        src = img.get("src", "")
        # Get full-size URL (remove 'huge' or 'big' prefix in filename)
        if "/huge" in src:
            full = src.replace("/huge", "/")
        elif "/big" in src:
            full = src.replace("/big", "/")
        else:
            full = src
        if full.startswith("/"):
            full = BASE_URL + full
        if full not in photos:
            photos.append(full)

    # Also check links that point to full-size photos
    for a in soup.select('a[href*="/fotos/"]'):
        href = a.get("href", "")
        if href.endswith((".jpg", ".jpeg", ".png", ".webp")):
            full = href if href.startswith("http") else BASE_URL + href
            if full not in photos:
                photos.append(full)

    data["photos"] = photos

    # ── Bedroom distribution ──
    bedrooms_list = []
    bedroom_sections = soup.find_all(string=re.compile(r"Bedroom \d", re.I))
    for bs in bedroom_sections:
        parent = bs.find_parent()
        if parent:
            container = parent.find_parent()
            if container:
                text = container.get_text(strip=True)
                room_match = re.search(r"(Bedroom \d+)", text, re.I)
                bed_match = re.search(
                    r"(King size bed|Double bed|Single bed|Twin bed|Bunk bed|Sofa bed)",
                    text, re.I
                )
                if room_match:
                    bedrooms_list.append({
                        "room": room_match.group(1),
                        "bed": bed_match.group(1) if bed_match else "Bed"
                    })

    # Deduplicate
    seen_rooms = set()
    unique_bedrooms = []
    for b in bedrooms_list:
        if b["room"] not in seen_rooms:
            seen_rooms.add(b["room"])
            unique_bedrooms.append(b)
    data["bedrooms_detail"] = unique_bedrooms

    # ── Views / Features ──
    features = []
    feature_keywords = [
        "Sea views", "Mountain views", "Garden views", "Pool views",
        "Private Pool", "Private Heated", "Heated Pool", "Heated swimming pool",
        "terrace", "BBQ", "Barbecue", "Fenced garden", "Air-Conditioned",
        "Air conditioning", "Underfloor", "Floor heating", "Alarm",
        "Secured parking", "Jacuzzi", "Sauna", "Gym", "Tennis",
        "Padel", "Elevator", "Ocean view", "Golf views", "Frontline",
        "Direct Beach", "Communal Swimming Pool", "Indoor Pool",
        "Outdoor Kitchen", "Walking Distance"
    ]
    for kw in feature_keywords:
        if kw.lower() in page_text.lower():
            features.append(kw)
    data["features"] = features

    # ── Distances ──
    distances = []
    distance_patterns = [
        (r"golf.*?(\d[\d,.]*\s*(?:m|km))", "Golf course"),
        (r"restaurant.*?(\d[\d,.]*\s*(?:m|km))", "Restaurant"),
        (r"(?:shop|supermarket).*?(\d[\d,.]*\s*(?:m|km))", "Shops"),
        (r"(?:town|city|centre|center).*?(\d[\d,.]*\s*(?:m|km))", "Town centre"),
        (r"(?:sand|beach).*?(\d[\d,.]*\s*(?:m|km))", "Sandy beach"),
        (r"hospital.*?(\d[\d,.]*\s*(?:m|km))", "Hospital"),
        (r"airport.*?(\d[\d,.]*\s*(?:m|km))", "Airport"),
        (r"(?:cafe|café).*?(\d[\d,.]*\s*(?:m|km))", "Cafe"),
    ]
    for pattern, label in distance_patterns:
        match = re.search(pattern, page_text, re.I)
        if match:
            distances.append({"place": label, "distance": match.group(1).strip()})
    data["distances"] = distances

    # ── Services (included / optional) ──
    included = []
    optional = []

    # Look for mandatory/optional service sections
    mandatory_section = soup.find(string=re.compile(r"Mandatory|Included", re.I))
    optional_section = soup.find(string=re.compile(r"Optional", re.I))

    if mandatory_section:
        container = mandatory_section.find_parent()
        if container:
            for sib in container.find_next_siblings():
                text = sib.get_text(strip=True)
                if not text or "Optional" in text:
                    break
                if ":" in text:
                    included.append(text)

    if optional_section:
        container = optional_section.find_parent()
        if container:
            for sib in container.find_next_siblings():
                text = sib.get_text(strip=True)
                if not text or text.startswith("Your schedule"):
                    break
                if ":" in text or "€" in text:
                    optional.append(text)

    data["services_included"] = included
    data["services_optional"] = optional

    # ── Check-in / Check-out ──
    checkin_match = re.search(r"Check-in.*?(\d{1,2}:\d{2}).*?(\d{1,2}:\d{2})", page_text)
    checkout_match = re.search(r"Check-out.*?(?:Before\s+)?(\d{1,2}:\d{2})", page_text)
    data["checkin"] = f"{checkin_match.group(1)} to {checkin_match.group(2)}" if checkin_match else ""
    data["checkout"] = f"Before {checkout_match.group(1)}" if checkout_match else ""

    # ── Security deposit ──
    deposit_match = re.search(r"(?:deposit|Security Deposit).*?(€\s*[\d,.]+)", page_text, re.I)
    data["deposit"] = deposit_match.group(1) if deposit_match else ""

    # ── House rules ──
    rules = []
    if re.search(r"No smoking", page_text, re.I):
        rules.append("No smoking")
    if re.search(r"No pets", page_text, re.I):
        rules.append("No pets")
    if re.search(r"No.*?groups.*?under.*?30", page_text, re.I):
        rules.append("No groups under 30 years of age")
    data["rules"] = rules

    # ── Registration number ──
    reg_match = re.search(r"(VFT/\w+/\d+)", page_text)
    data["registration"] = reg_match.group(1) if reg_match else ""

    # ── Map query (for Google Maps embed) ──
    data["map_query"] = f"{data['name']}, {data['location']}, Costa del Sol, Spain"

    return data


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("=" * 60)
    print("JustRent Marbella Property Scraper")
    print("=" * 60)

    # Step 1: Get all property URLs
    print("\n[1/2] Collecting property URLs from listing pages...")
    urls = get_all_property_urls()
    print(f"\nFound {len(urls)} unique properties.\n")

    if not urls:
        print("ERROR: No properties found. Check network access.")
        sys.exit(1)

    # Step 2: Scrape each property
    print("[2/2] Scraping individual property pages...\n")
    success = 0
    errors = []

    for i, url in enumerate(urls):
        slug = url.split("/")[-1].replace(".html", "")
        print(f"  [{i+1}/{len(urls)}] {slug}")

        try:
            data = extract_property(url)
            filepath = os.path.join(DATA_DIR, f"{data['slug']}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            success += 1
        except Exception as e:
            print(f"    ERROR: {e}")
            errors.append({"url": url, "error": str(e)})

        time.sleep(DELAY)

    print(f"\n{'=' * 60}")
    print(f"Done. {success} properties scraped, {len(errors)} errors.")
    if errors:
        print("\nFailed URLs:")
        for err in errors:
            print(f"  {err['url']}: {err['error']}")
    print(f"\nData saved to: {DATA_DIR}")


if __name__ == "__main__":
    main()
