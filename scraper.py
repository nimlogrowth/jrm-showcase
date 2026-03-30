#!/usr/bin/env python3
"""
JustRent Marbella Property Scraper v2
Properly parses Avantio CRS property pages.
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


def get_soup(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def get_all_property_urls():
    urls = []
    page = 1
    while True:
        page_url = LISTING_URL if page == 1 else LISTING_URL + "?pagina=" + str(page)
        print("  Listing page " + str(page))
        try:
            soup = get_soup(page_url)
        except Exception as e:
            print("  Error: " + str(e))
            break

        links = soup.select('a[href*="/rentals/"][href$=".html"]')
        page_urls = set()
        for link in links:
            href = link.get("href", "")
            if re.search(r"-\d{5,}\.html$", href):
                full_url = href if href.startswith("http") else BASE_URL + href
                page_urls.add(full_url)

        if not page_urls:
            break

        urls.extend(page_urls)
        print("  Found " + str(len(page_urls)) + " properties")

        next_link = soup.select_one('a[href*="pagina=' + str(page + 1) + '"]')
        if not next_link:
            break

        page += 1
        time.sleep(DELAY)

    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def extract_property(url):
    soup = get_soup(url)
    data = {"url": url, "source_url": url}
    slug = url.split("/")[-1].replace(".html", "")
    data["slug"] = slug

    # ── Strip cookie banners, scripts, styles, similar properties ──
    for tag in soup.select('script, style, noscript'):
        tag.decompose()

    # Remove "Similar properties" and everything after
    for heading in soup.find_all(string=re.compile(r"Similar properties", re.I)):
        parent = heading.find_parent()
        if parent:
            for sib in list(parent.find_next_siblings()):
                sib.decompose()
            parent.decompose()

    # ── Name, Location, Type from H1 ──
    h1 = soup.select_one("h1")
    # Use separator to avoid concatenated words
    raw_title = h1.get_text(" ", strip=True) if h1 else slug.replace("-", " ").title()

    # H1 format: "Villa La Quinta Benahavís - Villa"
    parts = raw_title.rsplit(" - ", 1)
    name_loc = parts[0].strip()
    data["type"] = parts[1].strip() if len(parts) > 1 else ""

    # Location from breadcrumb
    breadcrumb = soup.select_one('a[href*="/rentals/rentals-"]')
    data["location"] = breadcrumb.get_text(strip=True) if breadcrumb else ""

    # Remove location from name
    if data["location"] and name_loc.endswith(data["location"]):
        data["name"] = name_loc[:-len(data["location"])].strip()
    elif data["location"] and name_loc.endswith(" " + data["location"]):
        data["name"] = name_loc[:-(len(data["location"]) + 1)].strip()
    else:
        data["name"] = name_loc

    # ── Photos: only from main gallery, not similar properties ──
    photos = []
    seen_fnames = set()

    # Primary method: <a> tags linking to full-size photos in /fotos/ on the JRM domain
    for a_tag in soup.select('a[href*="/rentals/fotos/"]'):
        href = a_tag.get("href", "")
        if not re.search(r"\.(jpg|jpeg|png|webp)$", href, re.I):
            continue
        full = href if href.startswith("http") else BASE_URL + href
        # Skip img.avantio.com (those are from similar properties)
        if "img.avantio.com" in full:
            continue
        fname = full.split("/")[-1]
        if fname not in seen_fnames:
            seen_fnames.add(fname)
            photos.append(full)

    # Fallback: also check <a> tags with /fotos/ on the /3/ path (some properties use this)
    if not photos:
        for a_tag in soup.select('a[href*="/fotos/"]'):
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

    # ── Key Facts ──
    # Use the full page text for regex matching
    page_text = soup.get_text(" ", strip=True)

    # Guests (occupants)
    data["guests"] = ""
    m = re.search(r"occupants\s+(\d{1,3})\b", page_text, re.I)
    if m:
        data["guests"] = m.group(1)

    # Bedrooms count - "X Bedrooms"
    data["bedrooms"] = ""
    m = re.search(r"(\d{1,2})\s+Bedrooms?\b", page_text)
    if m:
        data["bedrooms"] = m.group(1)

    # Bathrooms - sum all "X Bathroom" and "X Toilet"
    bath_total = 0
    for m in re.finditer(r"(\d{1,2})\s+Bathroom", page_text):
        bath_total += int(m.group(1))
    for m in re.finditer(r"(\d{1,2})\s+Toilet", page_text):
        bath_total += int(m.group(1))
    data["bathrooms"] = str(bath_total) if bath_total > 0 else ""

    # Area - "XXX m² Property"
    data["area"] = ""
    m = re.search(r"(\d{2,5})\s*m.\s*Property", page_text)
    if m:
        data["area"] = m.group(1) + " m\u00b2"

    # Plot - "XXX m² Plot"
    data["plot"] = ""
    m = re.search(r"(\d{2,5})\s*m.\s*Plot", page_text)
    if m:
        data["plot"] = m.group(1) + " m\u00b2"

    # ── Description ──
    data["description"] = ""

    # Strategy 1: Find "Description" heading and get the text after it
    desc_heading = soup.find(string=re.compile(r"Description", re.I))
    if desc_heading:
        heading_el = desc_heading.find_parent()
        if heading_el:
            for sib in heading_el.find_next_siblings():
                t = sib.get_text(" ", strip=True)
                if not t:
                    continue
                if t in ["More Details", "Hide Details"]:
                    continue
                if sib.name and sib.name.startswith("h"):
                    break
                if "Distribution of bedrooms" in t or "Special features" in t:
                    break
                if "cookies" in t.lower() and "necessary" in t.lower():
                    continue
                if "Cookies Policy" in t:
                    continue
                if len(t) > 20:
                    data["description"] = t
                    break

    # Strategy 2: Look for text right after "Accommodation" section heading
    if not data["description"]:
        accom_heading = soup.find(string=re.compile(r"^Accommodation$", re.I))
        if accom_heading:
            parent = accom_heading.find_parent()
            if parent:
                for sib in parent.find_next_siblings():
                    t = sib.get_text(" ", strip=True)
                    if not t or t == "Description":
                        continue
                    if t in ["More Details", "Hide Details"]:
                        continue
                    if sib.name and sib.name.startswith("h"):
                        break
                    if "cookies" in t.lower():
                        continue
                    if len(t) > 20:
                        data["description"] = t
                        break

    # Strategy 3: Find any substantial paragraph in the description/accommodation area
    if not data["description"]:
        for div in soup.select('[class*="descripcion"], [class*="description"], [id*="descripcion"]'):
            for p in div.find_all(["p", "div"]):
                t = p.get_text(" ", strip=True)
                if t and len(t) > 50 and "cookie" not in t.lower() and "Cookie" not in t:
                    data["description"] = t
                    break
            if data["description"]:
                break

    # Fallback to meta description
    if not data["description"]:
        meta = soup.select_one('meta[name="description"]')
        if meta and meta.get("content"):
            data["description"] = meta["content"]

    # ── Bedroom Distribution ──
    bedrooms_list = []
    dist_heading = soup.find(string=re.compile(r"Distribution of bedrooms", re.I))
    if dist_heading:
        # Navigate up to find the container, then parse bedroom/bed pairs
        container = dist_heading.find_parent()
        while container and container.name not in ["div", "section"]:
            container = container.find_parent()

        if container:
            text_block = container.get_text("\n")
            # Find patterns like "Bedroom 1\n1 King size bed" or "Bedroom 2\n1 Double bed"
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

    data["bedrooms_detail"] = bedrooms_list

    # ── Features ──
    features = []

    # Views section
    views_heading = soup.find(string=re.compile(r"^\s*Views\s*$"))
    if views_heading:
        parent = views_heading.find_parent()
        if parent:
            container = parent.find_parent()
            if container:
                view_text = container.get_text("\n")
                view_items = [
                    line.strip() for line in view_text.split("\n")
                    if line.strip() and line.strip() not in ["Views", "See more", "See less"]
                ]
                for v in view_items:
                    clean = v.replace("golf-course", "Golf course").replace("beach", "Beach")
                    if clean in ["Sea", "Garden", "Mountain", "Lake", "Beach"]:
                        clean = clean + " views"
                    if clean == "Swimming pool":
                        clean = "Pool views"
                    if clean and clean not in features and len(clean) > 1:
                        features.append(clean)

    # Key amenity highlights from General section
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
        "Indoor Pool": "Indoor pool",
        "Ocean view": "Ocean views",
        "Direct Beach Access": "Direct beach access",
        "Frontline Beach": "Frontline beach",
        "Frontline Golf": "Frontline golf",
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
    dist_label = soup.find(string=re.compile(r"^\s*Distances\s*$"))
    if dist_label:
        parent = dist_label.find_parent()
        if parent:
            # Go up to find the list container
            container = parent
            for _ in range(5):
                container = container.find_parent()
                if container and container.find("li"):
                    break

            if container:
                for li in container.find_all("li"):
                    text = li.get_text(" ", strip=True)
                    m = re.match(r"(.+?)\s+([\d,.]+\s*(?:km|m))\s*$", text)
                    if m:
                        place = m.group(1).strip()
                        dist_val = m.group(2).strip()
                        # Deduplicate (prefer first occurrence)
                        existing = [d["place"] for d in distances]
                        # Skip "International airport" if we already have "Airport"
                        if place == "International airport":
                            if "Airport" in existing:
                                continue
                            place = "Airport"
                        if place not in existing:
                            distances.append({"place": place, "distance": dist_val})

    data["distances"] = distances

    # ── Mandatory/Included Services ──
    included = []
    mand_h = soup.find(string=re.compile(r"Mandatory or included services", re.I))
    if mand_h:
        el = mand_h.find_parent()
        if el:
            container = el.find_parent()
            if container:
                text_lines = container.get_text("\n").split("\n")
                capture = False
                for line in text_lines:
                    line = line.strip()
                    if "Mandatory or included" in line:
                        capture = True
                        continue
                    if capture:
                        if "Optional" in line or "Your schedule" in line:
                            break
                        if ":" in line and len(line) > 5:
                            included.append(line)

    data["services_included"] = included

    # ── Optional Services ──
    optional = []
    opt_h = soup.find(string=re.compile(r"^\s*Optional services\s*$", re.I))
    if opt_h:
        el = opt_h.find_parent()
        if el:
            container = el.find_parent()
            if container:
                text_lines = container.get_text("\n").split("\n")
                capture = False
                for line in text_lines:
                    line = line.strip()
                    if "Optional services" in line:
                        capture = True
                        continue
                    if capture:
                        if "Your schedule" in line or "Check-in" in line:
                            break
                        if (":" in line or "\u20ac" in line) and len(line) > 5:
                            optional.append(line)

    data["services_optional"] = optional

    # ── Check-in / Check-out ──
    ci = re.search(r"Check-in\s+from\s+(\d{1,2}:\d{2})\s+to\s+(\d{1,2}:\d{2})", page_text)
    data["checkin"] = ci.group(1) + " to " + ci.group(2) if ci else ""

    co = re.search(r"Check-out\s*Before\s+(\d{1,2}:\d{2})", page_text)
    data["checkout"] = "Before " + co.group(1) if co else ""

    # ── Security Deposit ──
    dep = re.search(r"Amount:\s*\u20ac\s*([\d,.]+)", page_text)
    if not dep:
        dep = re.search(r"Amount:\s*€\s*([\d,.]+)", page_text)
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
    print("JustRent Marbella Property Scraper v2")
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
            print("    " + pc + " photos, " + bd + " bed, " + loc)
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
