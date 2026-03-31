#!/usr/bin/env python3
"""
JustRent Marbella Property Scraper v4 (Final)
Built from actual Avantio DOM structure with exact CSS selectors.
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
import sys

BASE_URL = "https://www.justrentmarbella.com"
LISTING_URLS = [
    BASE_URL + "/rentals/holidays-rentals-rentals-d0/",
    BASE_URL + "/long-term-rental/holidays-rentals-rentals-d0/",
    BASE_URL + "/special-offers/",
]
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}
DELAY = 1.5


def get_soup(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def get_all_property_urls():
    """Crawl all listing sections. Never stop early. Follow every page."""
    url_by_id = {}

    for listing_url in LISTING_URLS:
        section_name = listing_url.split("/")[-2] or listing_url.split("/")[-3]
        print("\n  Section: " + section_name)
        page = 1
        max_pages = 50

        while page <= max_pages:
            page_url = listing_url if page == 1 else listing_url + "?pagina=" + str(page)
            print("    Page " + str(page) + "...", end=" ")
            try:
                soup = get_soup(page_url)
            except Exception as e:
                print("Error: " + str(e))
                break

            links = soup.select('a[href$=".html"]')
            page_count = 0
            for link in links:
                href = link.get("href", "")
                id_match = re.search(r"-(\d{5,})\.html$", href)
                if not id_match:
                    continue
                prop_id = id_match.group(1)
                full_url = href if href.startswith("http") else BASE_URL + href

                if prop_id not in url_by_id:
                    url_by_id[prop_id] = full_url
                    page_count += 1
                elif "/rentals/" in full_url and "/long-term-rental/" in url_by_id[prop_id]:
                    url_by_id[prop_id] = full_url

            print(str(page_count) + " new")

            # Always check for next page. Never stop based on count.
            next_page = soup.select_one('a[href*="pagina=' + str(page + 1) + '"]')
            if not next_page:
                break

            page += 1
            time.sleep(DELAY)

    unique = sorted(url_by_id.values())
    return unique


def extract_property(url):
    """Extract all property data using exact Avantio CSS selectors."""
    soup = get_soup(url)
    data = {"url": url, "source_url": url}
    slug = url.split("/")[-1].replace(".html", "")
    data["slug"] = slug

    # ── Name (exact selector: span.accommodationName) ──
    name_el = soup.select_one("span.accommodationName")
    data["name"] = name_el.get_text(strip=True) if name_el else ""

    # ── Location (span.tagSubCabecera.pobl) ──
    loc_el = soup.select_one("span.pobl")
    data["location"] = loc_el.get_text(strip=True).rstrip(" -").strip() if loc_el else ""

    # ── Type (span.tagSubCabecera.tipo) ──
    type_el = soup.select_one("span.tipo")
    data["type"] = type_el.get_text(strip=True) if type_el else ""

    # ── Key Facts from #caracteristicasAlojamiento ──
    facts_el = soup.select_one("#caracteristicasAlojamiento")
    data["guests"] = ""
    data["bedrooms"] = ""
    data["bathrooms"] = ""
    data["area"] = ""
    data["plot"] = ""

    if facts_el:
        for li in facts_el.select("li.tooltip"):
            tooltip = li.select_one("span.tooltiptext")
            value = li.select("span")[-1].get_text(strip=True) if li.select("span") else ""
            tip_text = tooltip.get_text(strip=True) if tooltip else ""

            if "occupant" in tip_text.lower():
                data["guests"] = value
            elif "Bedroom" in tip_text:
                data["bedrooms"] = value
            elif "Bathroom" in tip_text or "tooltipbath" in (tooltip.get("class", []) if tooltip else []):
                data["bathrooms"] = value
            elif "m\u00b2" in tip_text and "Plot" not in tip_text:
                data["area"] = value

    # Plot from general items
    for item in soup.select("#general .general-item"):
        text = item.get_text(strip=True)
        m = re.search(r"(\d+)\s*m.\s*Plot", text)
        if m:
            data["plot"] = m.group(1) + " m\u00b2"
            break

    # ── Description from #descriptionText (preserving paragraphs) ──
    desc_el = soup.select_one("#descriptionText")
    if desc_el:
        # Replace <br/><br/> with paragraph markers, then extract
        html_str = str(desc_el)
        # Replace double br tags with newline markers
        html_str = re.sub(r"<br\s*/?\s*>\s*<br\s*/?\s*>", "\n\n", html_str)
        # Replace single br with newline
        html_str = re.sub(r"<br\s*/?\s*>", "\n", html_str)
        # Parse again and get text
        desc_soup = BeautifulSoup(html_str, "html.parser")
        data["description"] = desc_soup.get_text(strip=True)
        # Restore paragraph breaks
        lines = [l.strip() for l in desc_soup.get_text().split("\n") if l.strip()]
        data["description"] = "\n\n".join(lines)
    else:
        # Fallback: schema.org JSON-LD
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                ld = json.loads(script.string)
                if ld.get("@type") == "Product" and ld.get("description"):
                    data["description"] = ld["description"]
                    break
            except Exception:
                pass
        if not data.get("description"):
            meta = soup.select_one('meta[name="description"]')
            data["description"] = meta.get("content", "") if meta else ""

    # ── Photos from #galleryGrid only (not similar properties) ──
    photos = []
    seen_fnames = set()
    gallery = soup.select_one("#galleryGrid")
    if gallery:
        for a in gallery.select("a[href]"):
            href = a.get("href", "")
            if re.search(r"\.(jpg|jpeg|png|webp)$", href, re.I):
                full = href if href.startswith("http") else BASE_URL + href
                fname = full.split("/")[-1]
                if fname not in seen_fnames:
                    seen_fnames.add(fname)
                    photos.append(full)
    data["photos"] = photos

    # ── Bedrooms from #bedrooms .bedroom-item ──
    bedrooms_list = []
    for item in soup.select("#bedrooms .bedroom-item"):
        room = item.select_one("span.room-type")
        bed = item.select_one("span.bed-type")
        if room and bed:
            bed_text = bed.get_text(strip=True)
            # Remove leading "1 " from "1 King size bed"
            bed_text = re.sub(r"^\d+\s+", "", bed_text)
            bedrooms_list.append({
                "room": room.get_text(strip=True),
                "bed": bed_text
            })
    data["bedrooms_detail"] = bedrooms_list

    # ── Views from #views .view span ──
    features = []
    for item in soup.select("#views .view span"):
        v = item.get_text(strip=True)
        if v in ["Sea", "Garden", "Mountain", "Lake"]:
            v = v + " views"
        elif v == "Swimming pool":
            v = "Pool views"
        elif v == "beach":
            v = "Beach views"
        elif v == "golf-course":
            v = "Golf course views"
        if v and v not in features:
            features.append(v)

    # ── Key highlights from #general .general-item ──
    amenity_map = {
        "Private Heated swimming pool": "Private heated pool",
        "Private Swimming pool": "Private pool",
        "Communal Swimming pool": "Communal pool",
        "Air-Conditioned": "Air-conditioned",
        "Central heating": "Central heating",
        "Floor heating": "Underfloor heating",
        "Barbecue": "BBQ",
        "Gas bbq": "BBQ",
        "Fenced garden": "Fenced garden",
        "Jacuzzi": "Jacuzzi",
        "Sauna": "Sauna",
        "Gym / fitness centre": "Gym / fitness",
        "Tennis court": "Tennis court",
        "Paddle tennis court": "Padel court",
        "Alarm": "Alarm system",
        "Safe": "Safe",
        "Fireplace": "Fireplace",
        "Lift": "Lift",
        "Secured parking": "Secured parking",
        "Ping pong table": "Ping pong",
        "Darts": "Darts",
        "Salt-water pool": "Saltwater pool",
        "Infinity pool": "Infinity pool",
        "Ocean view": "Ocean views",
        "Mountain view": "Mountain views",
        "Security system": "Security system",
        "Dryer": "Dryer",
        "Balcony": "Balcony",
    }

    for item in soup.select("#general .general-item"):
        text = item.get_text(" ", strip=True)
        for keyword, clean in amenity_map.items():
            if keyword in text and clean not in features:
                features.append(clean)

    # Terrace size
    for item in soup.select("#general .general-item"):
        text = item.get_text(strip=True)
        m = re.search(r"(\d+)\s*m.\s*terrace", text, re.I)
        if m:
            tf = m.group(1) + " m\u00b2 terrace"
            if tf not in features:
                features.append(tf)
            break

    data["features"] = features

    # ── Distances from .liDistances ──
    distances = []
    seen_places = set()
    for li in soup.select("li.liDistances"):
        left = li.select_one("p.alignleft")
        right = li.select_one("p.alignright")
        if left and right:
            place = left.get_text(strip=True)
            dist = right.get_text(strip=True)
            # Skip airport entries
            if "airport" in place.lower():
                continue
            if place not in seen_places:
                seen_places.add(place)
                distances.append({"place": place, "distance": dist})
    data["distances"] = distances

    # ── Mandatory/Included Services from #mandatoryServices .mandatory-item ──
    included = []
    for item in soup.select("#mandatoryServices .mandatory-item span"):
        text = item.get_text(strip=True)
        if text and len(text) > 3:
            included.append(text)
    data["services_included"] = included

    # ── Optional Services from #optionalServices .optional-item ──
    optional = []
    for item in soup.select("#optionalServices .optional-item span"):
        text = item.get_text(strip=True)
        if text and len(text) > 3:
            optional.append(text)
    data["services_optional"] = optional

    # ── Check-in / Check-out from #schedules ──
    schedules = soup.select_one("#schedules")
    data["checkin"] = ""
    data["checkout"] = ""
    if schedules:
        sched_text = schedules.get_text(" ", strip=True)
        ci = re.search(r"Check-in\s+from\s+(\d{1,2}:\d{2})\s+to\s+(\d{1,2}:\d{2})", sched_text)
        if ci:
            data["checkin"] = ci.group(1) + " to " + ci.group(2)
        co = re.search(r"Check-out\s*Before\s+(\d{1,2}:\d{2})", sched_text)
        if co:
            data["checkout"] = "Before " + co.group(1)

    # ── Security Deposit from #bondFeatures ──
    bond = soup.select_one("#bondFeatures")
    data["deposit"] = ""
    if bond:
        bond_text = bond.get_text(" ", strip=True)
        dep = re.search(r"Amount:\s*[€\u20ac]\s*([\d,.]+)", bond_text)
        if dep:
            data["deposit"] = "\u20ac" + dep.group(1).strip()

    # ── Rules from #observacionesGA ──
    rules = []
    obs = soup.select_one("#observacionesGA")
    if obs:
        obs_text = obs.get_text(" ", strip=True)
        if re.search(r"No smoking", obs_text, re.I):
            rules.append("No smoking")
        if re.search(r"No pets|Pets not allowed", obs_text, re.I):
            rules.append("No pets")
        if re.search(r"not accept groups|groups of young", obs_text, re.I):
            rules.append("No groups under 30 years of age")
    data["rules"] = rules

    # ── Registration from #other_information_value ──
    reg_el = soup.select_one("#other_information_value")
    data["registration"] = reg_el.get_text(strip=True) if reg_el else ""

    # ── Map Query ──
    data["map_query"] = data["name"] + ", " + data["location"] + ", Costa del Sol, Spain"

    return data


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("=" * 60)
    print("JustRent Marbella Property Scraper v4 (Final)")
    print("=" * 60)

    print("\n[1/2] Collecting property URLs...")
    urls = get_all_property_urls()
    print("\nFound " + str(len(urls)) + " unique properties.\n")

    if not urls:
        print("ERROR: No properties found.")
        sys.exit(1)

    print("[2/2] Scraping properties...\n")
    success = 0
    errors = []

    for i, url in enumerate(urls):
        slug = url.split("/")[-1].replace(".html", "")
        print("  [" + str(i + 1) + "/" + str(len(urls)) + "] " + slug)

        try:
            data = extract_property(url)
            filepath = os.path.join(DATA_DIR, data["slug"] + ".json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            success += 1
            pc = str(len(data.get("photos", [])))
            bd = data.get("bedrooms", "?")
            nm = data.get("name", "")
            print("    " + nm + " | " + pc + " photos, " + bd + " bed")
        except Exception as e:
            print("    ERROR: " + str(e))
            errors.append({"url": url, "error": str(e)})

        time.sleep(DELAY)

    print("\n" + "=" * 60)
    print("Done. " + str(success) + " scraped, " + str(len(errors)) + " errors.")
    if errors:
        print("\nFailed:")
        for err in errors:
            print("  " + err["url"] + ": " + err["error"])
    print("\nData: " + DATA_DIR)


if __name__ == "__main__":
    main()
