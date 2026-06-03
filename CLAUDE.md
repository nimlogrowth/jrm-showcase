# JRM Property Showcase — Project Context

## What This Is
A static property showcase site for JustRent Marbella (JRM) referral partners and agents. Lives at **properties.justrentestepona.com**. Built as a scraper + generator pipeline that produces static HTML deployed on Netlify.

## Architecture
1. `scraper.py` — Crawls justrentmarbella.com (Avantio CRS platform), visits every property page, extracts data into JSON files in `/data/`
2. `generator.py` — Reads JSON files, generates HTML property pages + index into `/output/`
3. Push to GitHub (nimlogrowth/jrm-showcase) → Netlify auto-deploys from `/output/`

## Live URLs
- **Site:** https://properties.justrentestepona.com
- **Netlify:** stirring-froyo-b5ba66.netlify.app
- **GitHub:** github.com/nimlogrowth/jrm-showcase
- **GoDaddy domain:** justrentestepona.com (CNAME: properties → stirring-froyo-b5ba66.netlify.app)

## File Locations (User's Machine)
- Project: `~/Documents/jrm-showcase/`
- Data: `~/Documents/jrm-showcase/data/` (JSON per property)
- Output: `~/Documents/jrm-showcase/output/` (generated HTML)

## Current State (3 June 2026)
- **202 properties live** with correct data (196 holiday rentals + 6 long-term)
- Site lists 196 holiday rentals ("of 196 accommodations" on the last listing page); offer-only pages with non-standard templates are skipped
- Scraper uses a single `requests.Session()` — the Avantio listing randomizes property order per request, so paginating without a persistent session re-draws overlapping random subsets and only collects ~122 of 196 (coupon-collector overlap). The session pins the shuffle so pagination walks the full catalog.
- Scraper v4 uses exact Avantio CSS selectors (built from actual page source HTML)
- Descriptions render with paragraph breaks
- OG meta tags added for WhatsApp/social link previews
- Airport removed from distances
- Properties sorted A-Z by default on index
- Sort options: Name A-Z, Name Z-A, Bedrooms low/high, Guests low/high
- Filters: search by name, location dropdown, type dropdown, bedrooms dropdown

## Scraper v4 — Key CSS Selectors
These are the exact selectors from the Avantio template:
- **Name:** `span.accommodationName`
- **Location:** `span.pobl` (with trailing " -" stripped)
- **Type:** `span.tipo`
- **Key facts:** `#caracteristicasAlojamiento li.tooltip` → tooltiptext contains "occupant"/"Bedroom"/"Bathroom"/"m²"
- **Description:** `#descriptionText` (HTML has `<br/><br/>` between paragraphs)
- **Photos:** `#galleryGrid a[href]` (only from main gallery, not similar properties)
- **Bedrooms:** `#bedrooms .bedroom-item` → `span.room-type` + `span.bed-type`
- **Views:** `#views .view span`
- **General features:** `#general .general-item`
- **Distances:** `li.liDistances` → `p.alignleft` + `p.alignright`
- **Included services:** `#mandatoryServices .mandatory-item span`
- **Optional services:** `#optionalServices .optional-item span`
- **Check-in/out:** `#schedules` (regex on text)
- **Deposit:** `#bondFeatures` (regex for "Amount: € X")
- **Rules:** `#observacionesGA` (regex for No smoking/No pets/groups)
- **Registration:** `#other_information_value`
- **Schema.org fallback for description:** `script[type="application/ld+json"]` with `@type: Product`

## Generator — Key Design Decisions
- **Unbranded pages** — no JRM logo, no pricing. For agents to share with renters.
- **Template:** Cormorant Garamond display + DM Sans body. Charcoal #2C2C2C, sand #F5F0EB, accent #8B7355.
- **Property page:** Hero image with gradient, key facts bar, paragraphed description, bedroom cards, feature tags, alternating gallery layout, Google Maps iframe, distances grid, services with check-in bar, registration footer.
- **Lightbox:** Click any photo → fullscreen with arrows, keyboard nav, swipe, thumbnail filmstrip.
- **Index page:** Property cards with hero photo, clean name, location · type, bedrooms, guests. Filters and sort.
- **Name cleaning:** `clean_name()` function strips location and type suffixes from scraped names (e.g. "Villa La QuintaBenahavís" → "Villa La Quinta").
- **Description paragraphs:** Scraper preserves `\n\n` breaks. Generator renders each as `<p>` with 16px margin-bottom.
- **OG tags:** Property pages show name, description, hero photo. Index shows count and first property photo.
- **Broken property filter:** Generator skips JSON files with no name or no photos.

## Scraper — Listing URLs Crawled
```python
LISTING_URLS = [
    "/rentals/holidays-rentals-rentals-d0/",
    "/long-term-rental/holidays-rentals-rentals-d0/",
    "/special-offers/",
]
```
- Deduplicates by property ID (number at end of URL)
- Prefers `/rentals/` URL over `/long-term-rental/` when both exist
- Skips `/offer-` URLs (different template, selectors fail)
- Never stops pagination early — always follows next page link until none exists

## Build Commands
```bash
cd ~/Documents/jrm-showcase
python3 scraper.py          # ~15 min, scrapes all properties
python3 generator.py        # ~5 sec, builds HTML
git add -A
git commit -m "message"
git push                    # triggers Netlify auto-deploy
```

## Python Compatibility
- User runs macOS with Python 3.9 via Homebrew
- No nested f-strings (not supported until Python 3.12)
- Use `pip3 install --break-system-packages` if installing packages
- Dependencies: `requests`, `beautifulsoup4`

## Known Issues / Future Work
1. **2-3 properties missing** — offer-only pages with non-standard templates
2. **Nightly auto-rebuild** not configured yet — could use GitHub Actions or Netlify build hooks
3. **PDF export** — attempted and abandoned due to CORS on Avantio image URLs
4. **Some feature tags** could be cleaner (e.g. "Floor heating" vs "Underfloor heating" dedup)
5. **Winter rental properties** that only exist at `/long-term-rental/` URLs are included but their page structure may differ slightly

## Netlify Config
- Build command: (blank — we push pre-built output)
- Publish directory: `output`
- Auto-deploy on push to main branch
- SSL provisioned via Let's Encrypt

## Git Auth
- GitHub org: nimlogrowth
- Auth: personal access token embedded in remote URL
