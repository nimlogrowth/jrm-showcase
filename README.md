# JRM Property Showcase

Static property showcase site for JustRent Marbella. Scrapes property data from justrentmarbella.com and generates a browsable directory with individual property pages.

## How it works

1. `scraper.py` visits justrentmarbella.com, loops through all listing pages, and extracts property data into JSON files in `/data/`.
2. `generator.py` reads those JSON files and generates HTML pages (one per property + a directory page) in `/output/`.
3. GitHub Actions runs this nightly and deploys to GitHub Pages.

## Local setup

```bash
pip install requests beautifulsoup4
python scraper.py      # Takes ~10 minutes for 188 properties
python generator.py    # Generates static site in /output/
```

Or run both at once:

```bash
chmod +x build.sh
./build.sh
```

Open `output/index.html` in a browser to preview.

## Deployment

The GitHub Action in `.github/workflows/build.yml` runs nightly at 03:00 UTC. It scrapes, generates, and deploys to GitHub Pages automatically.

To set up:
1. Push this repo to GitHub
2. Go to Settings > Pages > Source: Deploy from a branch > Branch: gh-pages
3. Optionally add a custom domain (e.g. showcase.justrentmarbella.com)

Manual trigger: Actions tab > Build & Deploy Showcase > Run workflow.

## Structure

```
jrm-showcase/
  scraper.py          Scrapes justrentmarbella.com
  generator.py        Generates HTML from JSON
  build.sh            Runs both
  data/               JSON files (one per property)
  output/             Generated static site
  .github/workflows/  GitHub Actions config
```
