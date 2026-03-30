#!/usr/bin/env python3
"""
JustRent Marbella Property Scraper v3
Full rebuild with fixes for: pagination, description, bathrooms,
distances, services, features, airport units.
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
DELAY = 1.5
MAX_PAGES = 40  # Safety limit


def get_soup(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


# ──────────────────────────────────────────────────────────
# PAGINATION FIX: keep going until 0 new properties found
# ──────────────────────────────────────────────────────────
def get_all_property_urls():
    all_urls = set()
    page = 1
    consecutive_empty = 0

    while page <= MAX_PAGES:
        page_url = LISTING_URL if page == 1 else LISTING_URL + "?pagina=" + str(page)
        print("  Listing page " + str(page) + "...", end=" ")
        try:
            soup = get_soup(page_url)
        except Exception as e:
            print("Error: " + str(e))
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break
            page += 1
            time.sleep(DELAY)
            continue

        # Find all property links (end with -NNNNN.html)
        page_urls = set()
        for link in soup.select('a[href$=".html"]'):
            href = link.get("href", "")
            if re.search(r"(villa|apartment|house|terraced|penthouse|townhouse|studio).*-\d{5,}\.html$", href, re.I):
                full_url = href if href.startswith("http") else BASE_URL + href
                # Skip contact pages, favourites, etc
                if "/contact-" in full_url or "/favourites" in full_url:
                    continue
                page_urls.add(full_url)

        new_count = len(page_urls - all_urls)
        print(str(new_count) + " new properties")

        if new_count == 0:
            consecutive_empty += 1
            if consecutive_empty >= 2:
                break
        else:
            consecutive_empty = 0
            all_urls.update(page_urls)

        page += 1
        time.sleep(DELAY)

    return sorted(all_urls)


# ──────────────────────────────────────────────────────────
# UI GARBAGE DETECTOR
# ──────────────────────────────────────────────────────────
UI_GARBAGE_WORDS = [
    "Share", "Link copied", "Add to favourites", "Favourites",
    "occupants", "Wi-Fi", "Bedrooms", "Bathroom",
    "cookies", "Cookies Policy", "strictly necessary",
    "Accept all", "Reject", "Save settings",
    "More Details", "Hide Details",
    "See more", "See less", "Show more", "Show fewer",
]

def is_ui_garbage(text):
    """Returns True if text looks like scraped UI elements, not real content."""
    if not text:
        return True
    garbage_count = sum(1 for w in UI_GARBAGE_WORDS if w in text)
    return garbage_count >= 2


# ──────────────────────────────────────────────────────────
# PROPERTY EXTRACTOR
# ──────────────────────────────────────────────────────────
def extract_property(url):
    soup = get_soup(url)
    data = {"url": url, "source_url": url}
    slug = url.split("/")[-1].replace(".html", "")
    data["slug"] = slug

    # ── Strip scripts, styles ──
    for tag in soup.select("script, style, noscript"):
        tag.decompose()

    # ── Remove "Similar properties" section and everything after ──
    for heading in soup.find_all(string=re.compile(r"Similar properties", re.I)):
        parent = heading.find_parent()
        if parent:
            for sib in list(parent.find_next_siblings()):
                sib.decompose()
            parent.decompose()

    # ── Name, Location, Type from H1 ──
    h1 = soup.select_one("h1")
    raw_title = h1.get_text(" ", strip=True) if h1 else slug.replace("-", " ").title()
    parts = raw_title.rsplit(" - ", 1)
    name_loc = parts[0].strip()
    data["type"] = parts[1].strip() if len(parts) > 1 else ""

    breadcrumb = soup.select_one('a[href*="/rentals/rentals-"]')
    data["location"] = breadcrumb.get_text(strip=True) if breadcrumb else ""

    # Remove location from name
    loc = data["location"]
    if loc and name_loc.endswith(" " + loc):
        data["name"] = name_loc[:-(len(loc) + 1)].strip()
    elif loc and name_loc.endswith(loc):
        data["name"] = name_loc[:-len(loc)].strip()
    else:
        data["name"] = name_loc
    if not data["name"]:
        data["name"] = name_loc

    # ── Photos: only JRM domain, not img.avantio.com ──
    photos = []
    seen_fnames = set()
    for a_tag in soup.select('a[href*="/rentals/fotos/"]'):
        href = a_tag.get("href", "")
        if not re.search(r"\.(jpg|jpeg|png|webp)$", href, re.I):
            continue
        full = href if href.startswith("http") else BASE_URL + href
        if "img.avantio.com" in full:
            continue
        fname = full.split("/")[-1]
        if fname not in seen_fnames:
            seen_fnames.add(fname)
            photos.append(full)
    data["photos"] = photos

    # ──────────────────────────────────────────────────
    # KEY FACTS: Extract from the Avantio accommodation
    # section, NOT from full page text (avoids doubling)
    # ──────────────────────────────────────────────────

    # Find the accommodation section by its anchor ID
    accom = soup.select_one('[id*="descripcion"], [id*="accommodation"]')
    # Fallback: find h2 "Accommodation"
    if not accom:
        for h2 in soup.find_all("h2"):
            if "Accommodation" in h2.get_text():
                accom = h2.find_parent()
                break

    # Use accommodation section text for facts (limits scope, avoids doubling)
    accom_text = accom.get_text(" ", strip=True) if accom else ""

    # Full page text (for things that appear outside accommodation section)
    page_text = soup.get_text(" ", strip=True)

    # Guests
    data["guests"] = ""
    m = re.search(r"occupants\s+(\d{1,3})\b", page_text, re.I)
    if m:
        data["guests"] = m.group(1)

    # Bedrooms count
    data["bedrooms"] = ""
    m = re.search(r"(\d{1,2})\s+Bedrooms?\b", page_text)
    if m:
        data["bedrooms"] = m.group(1)

    # ── Bathrooms: ONLY from the "Bathroom(s)" subsection ──
    bath_total = 0
    bath_heading = soup.find(string=re.compile(r"Bathroom", re.I))
    # Walk up to find h3 "Bathroom(s)"
    bath_section = None
    for h3 in soup.find_all("h3"):
        h3_text = h3.get_text(strip=True)
        if "Bathroom" in h3_text and "Distribution" not in h3_text:
            bath_section = h3
            break

    if bath_section:
        # Get text from the section between this h3 and the next h3
        bath_text_parts = []
        for sib in bath_section.find_next_siblings():
            if sib.name and sib.name.startswith("h"):
                break
            bath_text_parts.append(sib.get_text(" ", strip=True))
        bath_text = " ".join(bath_text_parts)
        for bm in re.finditer(r"(\d{1,2})\s+Bathroom", bath_text):
            bath_total += int(bm.group(1))
        for bm in re.finditer(r"(\d{1,2})\s+Toilet", bath_text):
            bath_total += int(bm.group(1))

    # Fallback: look in the first facts-bar occurrence only
    if bath_total == 0:
        # Find the icon row that shows "X Bathroom" text
        # Take only first occurrence of each pattern
        baths_found = re.findall(r"(\d{1,2})\s+Bathroom", page_text)
        toilets_found = re.findall(r"(\d{1,2})\s+Toilet", page_text)
        # If duplicated (appears twice), take first half
        if len(baths_found) >= 2:
            half = len(baths_found) // 2
            if baths_found[:half] == baths_found[half:2*half]:
                baths_found = baths_found[:half]
        for b in baths_found:
            bath_total += int(b)
        if len(toilets_found) >= 2:
            half = len(toilets_found) // 2
            if toilets_found[:half] == toilets_found[half:2*half]:
                toilets_found = toilets_found[:half]
        for t in toilets_found:
            bath_total += int(t)

    data["bathrooms"] = str(bath_total) if bath_total > 0 else ""

    # Area
    data["area"] = ""
    m = re.search(r"(\d{2,5})\s*m.\s*Property", page_text)
    if m:
        data["area"] = m.group(1) + " m\u00b2"

    # Plot
    data["plot"] = ""
    m = re.search(r"(\d{2,5})\s*m.\s*Plot", page_text)
    if m:
        data["plot"] = m.group(1) + " m\u00b2"

    # ──────────────────────────────────────────────────
    # DESCRIPTION: Multiple strategies, strict filtering
    # ──────────────────────────────────────────────────
    data["description"] = ""

    # Strategy 1: Find h3 "Description", then get FIRST child/descendant text
    for h3 in soup.find_all("h3"):
        if h3.get_text(strip=True).strip() == "Description":
            # Try finding the next text element that is NOT a heading
            el = h3
            for _ in range(20):  # Walk forward through the document
                el = el.find_next()
                if el is None:
                    break
                if el.name and el.name.startswith("h"):
                    # Hit another heading, skip it if it says Description
                    if "Description" in el.get_text():
                        continue
                    break
                t = el.get_text(" ", strip=True)
                if not t or len(t) < 20:
                    continue
                if t in ["More Details", "Hide Details", "Description"]:
                    continue
                if is_ui_garbage(t):
                    continue
                # Found a real description
                data["description"] = t
                break
            break

    # Strategy 2: Look for text in the accommodation section after Description heading
    if not data["description"] and accom:
        found_desc_heading = False
        for child in accom.descendants:
            if hasattr(child, 'get_text'):
                txt = child.get_text(strip=True)
                if txt == "Description":
                    found_desc_heading = True
                    continue
                if found_desc_heading and txt and len(txt) > 30:
                    if txt in ["More Details", "Hide Details"]:
                        continue
                    if is_ui_garbage(txt):
                        continue
                    if "Distribution of bedrooms" in txt:
                        break
                    data["description"] = txt
                    break

    # Strategy 3: CSS class selectors for Avantio description containers
    if not data["description"]:
        for selector in [".description-text", ".descripcion-texto", "[class*='desc'] p"]:
            el = soup.select_one(selector)
            if el:
                t = el.get_text(" ", strip=True)
                if t and len(t) > 30 and not is_ui_garbage(t):
                    data["description"] = t
                    break

    # Strategy 4: Find the largest paragraph in the accommodation section
    if not data["description"] and accom:
        best = ""
        for p in accom.find_all(["p"]):
            t = p.get_text(" ", strip=True)
            if t and len(t) > len(best) and not is_ui_garbage(t):
                best = t
        if len(best) > 30:
            data["description"] = best

    # Fallback: meta description (better than nothing)
    if not data["description"]:
        meta = soup.select_one('meta[name="description"]')
        if meta and meta.get("content"):
            data["description"] = meta["content"]

    # ── Bedroom Distribution ──
    bedrooms_list = []
    for h3 in soup.find_all("h3"):
        if "Distribution of bedrooms" in h3.get_text():
            container = h3.find_parent()
            while container and container.name not in ["div", "section"]:
                container = container.find_parent()
            if container:
                text_block = container.get_text("\n")
                pairs = re.findall(
                    r"(Bedroom\s+\d+)\s*\n\s*\d+\s+(King size bed|Double bed|Single bed|Twin bed|Bunk bed|Sofa bed)",
                    text_block, re.I
                )
                seen_rooms = set()
                for room, bed in pairs:
                    room_clean = room.strip()
                    if room_clean not in seen_rooms:
                        seen_rooms.add(room_clean)
                        bedrooms_list.append({"room": room_clean, "bed": bed.strip()})
            break
    data["bedrooms_detail"] = bedrooms_list

    # ── Features ──
    features = []

    # Views section
    for h3 in soup.find_all("h3"):
        if h3.get_text(strip=True).strip() == "Views":
            container = h3.find_parent()
            if container:
                view_text = container.get_text("\n")
                skip = {"Views", "See more", "See less", "Show more features", "Show fewer features", ""}
                for line in view_text.split("\n"):
                    v = line.strip()
                    if v in skip or len(v) < 2:
                        continue
                    clean = v.replace("golf-course", "Golf course")
                    if clean in ["Sea", "Garden", "Mountain", "Lake"]:
                        clean = clean + " views"
                    if clean == "beach":
                        clean = "Beach views"
                    if clean == "Swimming pool":
                        clean = "Pool views"
                    if clean not in features:
                        features.append(clean)
            break

    # Amenity highlights (keyword search in page text)
    amenity_map = {
        "Private Heated swimming pool": "Private heated pool",
        "Private Swimming pool": "Private pool",
        "Communal Swimming pool": "Communal pool",
        "Air-Conditioned": "Air-conditioned",
        "Central heating": "Central heating",
        "Underfloor heating": "Underfloor heating",
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
        "Indoor Pool": "Indoor pool",
        "Ocean view": "Ocean views",
        "Sea views": "Sea views",
        "Mountain view": "Mountain views",
        "Direct Beach Access": "Direct beach access",
        "Frontline Beach": "Frontline beach",
        "Frontline Golf": "Frontline golf",
        "Dryer": "Dryer",
        "Outdoor shower": "Outdoor shower",
        "Balcony": "Balcony",
        "Laptop friendly workspace": "Laptop workspace",
        "Pool towels": "Pool towels",
        "First aid kit": "First aid kit",
    }

    for keyword, clean_name in amenity_map.items():
        if keyword in page_text and clean_name not in features:
            features.append(clean_name)

    # Terrace size
    terrace_m = re.search(r"(\d+)\s*m.\s*terrace", page_text, re.I)
    if terrace_m:
        tf = terrace_m.group(1) + " m\u00b2 terrace"
        if tf not in features:
            features.append(tf)

    data["features"] = features

    # ── Distances ──
    distances = []
    # Find the "Distances" heading and then ALL list items in its container
    for el in soup.find_all(string=re.compile(r"^\s*Distances\s*$")):
        parent = el.find_parent()
        if not parent:
            continue
        # Walk up until we find a container with <li> elements
        container = parent
        for _ in range(8):
            container = container.find_parent()
            if container and container.find("li"):
                break
        if not container:
            continue

        for li in container.find_all("li"):
            text = li.get_text(" ", strip=True)
            m = re.match(r"(.+?)\s+([\d,.]+\s*(?:km|m))\s*$", text)
            if m:
                place = m.group(1).strip()
                dist_val = m.group(2).strip()

                # Fix airport showing "m" instead of "km"
                if "airport" in place.lower() or "Airport" in place:
                    num = re.match(r"([\d,.]+)", dist_val)
                    if num:
                        val = float(num.group(1).replace(",", "."))
                        if dist_val.endswith(" m") and val < 200:
                            dist_val = str(int(val)) + " km"

                # Deduplicate: merge "International airport" into "Airport"
                existing = [d["place"] for d in distances]
                if place == "International airport":
                    if "Airport" in existing:
                        continue
                    place = "Airport"
                if place not in existing:
                    distances.append({"place": place, "distance": dist_val})
        break  # Only process first Distances section

    data["distances"] = distances

    # ── Mandatory/Included Services ──
    included = []
    for h3 in soup.find_all("h3"):
        if "Mandatory" in h3.get_text() or "included services" in h3.get_text():
            # Collect text lines from siblings until next heading
            for sib in h3.find_next_siblings():
                if sib.name and sib.name.startswith("h"):
                    break
                text = sib.get_text(" ", strip=True)
                if text and ":" in text and len(text) > 5:
                    # Split if multiple items concatenated on one line
                    for item in re.split(r"(?<=\d)\s+(?=[A-Z])", text):
                        item = item.strip()
                        if item and ":" in item and item not in included:
                            included.append(item)
            break
    data["services_included"] = included

    # ── Optional Services ──
    optional = []
    for h3 in soup.find_all("h3"):
        if h3.get_text(strip=True) == "Optional services":
            for sib in h3.find_next_siblings():
                if sib.name and sib.name.startswith("h"):
                    break
                text = sib.get_text(" ", strip=True)
                if text and (":" in text or "\u20ac" in text or "€" in text) and len(text) > 5:
                    for item in re.split(r"(?<=\d)\s+(?=[A-Z])", text):
                        item = item.strip()
                        if item and item not in optional:
                            optional.append(item)
            break
    data["services_optional"] = optional

    # ── Check-in / Check-out ──
    ci = re.search(r"Check-in\s+from\s+(\d{1,2}:\d{2})\s+to\s+(\d{1,2}:\d{2})", page_text)
    data["checkin"] = ci.group(1) + " to " + ci.group(2) if ci else ""

    co = re.search(r"Check-out\s*Before\s+(\d{1,2}:\d{2})", page_text)
    data["checkout"] = "Before " + co.group(1) if co else ""

    # ── Security Deposit ──
    dep = re.search(r"Amount:\s*[€\u20ac]\s*([\d,.]+)", page_text)
    data["deposit"] = "\u20ac" + dep.group(1).strip() if dep else ""

    # ── Rules ──
    rules = []
    if re.search(r"No smoking", page_text, re.I):
        rules.append("No smoking")
    if re.search(r"No pets|Pets not allowed", page_text, re.I):
        rules.append("No pets")
    if re.search(r"not accept groups of young|groups under 30", page_text, re.I):
        rules.append("No groups under 30 years of age")
    data["rules"] = rules

    # ── Registration ──
    reg = re.search(r"(?:Registration Number|Accommodation Registration Number)\s*((?:VFT|VUT|CTC)[\w/\-]+)", page_text)
    data["registration"] = reg.group(1).strip() if reg else ""

    # ── Map Query ──
    data["map_query"] = data["name"] + ", " + data["location"] + ", Costa del Sol, Spain"

    return data


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("=" * 60)
    print("JustRent Marbella Property Scraper v3")
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
            loc = data.get("location", "")
            desc_ok = "DESC" if data.get("description") and not is_ui_garbage(data["description"]) else "no-desc"
            print("    " + pc + " photos, " + bd + " bed, " + loc + ", " + desc_ok)
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
