# HireFlow PWA — Phase 1

Mobile-first Progressive Web App served by the existing FastAPI backend.
Installable on iPhone (Add to Home Screen in Safari) and Android (Add to
Home Screen / Install prompt in Chrome).

## Run it locally

```bash
# 1. Install deps (one-time)
pip install -r requirements.txt
python -m playwright install chromium

# 2. Start the API server (also serves the PWA at /)
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8765
```

Open `http://localhost:8765/` in any browser. To reach it from your phone
on the same Wi-Fi, find your laptop's LAN IP and open
`http://<laptop-ip>:8765/` on your phone.

## Install to home screen

- **iPhone (Safari)**: Share → Add to Home Screen
- **Android (Chrome)**: ⋮ menu → Install app / Add to Home Screen

After install the app opens in standalone mode (no browser chrome) and
launches from a home-screen icon — same UX as a native app.

## File layout

```
app/web/
├── index.html              # SPA shell, all 4 views (jobs, detail, stats, scrape)
├── manifest.webmanifest    # PWA manifest (name, icons, theme color)
├── sw.js                   # service worker (static cache-first, API network-first)
├── js/app.js               # Alpine.js logic: filters, fetch, scrape polling
├── css/style.css           # custom CSS layered on top of Tailwind CDN
├── icons/                  # 192/512 PWA icons (reused from desktop logo)
└── README.md               # this file
```

The PWA is mounted as static files in `app/api/main.py` AFTER all API
routes are registered, so `/jobs`, `/stats`, etc. always hit the API
and anything else falls through to a static file.

## Endpoints used

| Endpoint              | Method | Purpose                          |
|-----------------------|--------|----------------------------------|
| `/jobs`               | GET    | Paginated jobs list + filters    |
| `/jobs/{id}`          | GET    | Single job detail                |
| `/stats`              | GET    | Dashboard stats                  |
| `/sources`            | GET    | Available scraper sources        |
| `/countries`          | GET    | Country name -> ISO code         |
| `/scrape`             | POST   | Start a new scrape (non-blocking)|
| `/scrape/status`      | GET    | Polled until `running: false`    |

## What's next (later phases)

- **Phase 2**: Dockerfile + deploy to Railway/Fly.io so it has a real
  `https://` URL. (PWAs require HTTPS for install + service worker on
  non-localhost origins.)
- **Phase 3**: User accounts / login. Currently any visitor on the LAN
  can scrape and read jobs — fine for local use, not for a public URL.
- **Phase 4**: Push notifications when a scrape finishes; richer
  offline support; pretty empty-states.
