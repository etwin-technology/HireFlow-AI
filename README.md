# HireFlow AI

**by Etwin Technology**

> Modern, AI-powered job aggregation platform for the desktop.
> Multi-source scraping · anti-bot stealth · dedup · live dashboard · Excel/CSV/JSON export · scheduler · FastAPI.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

---

## ✨ Features

- **8 supported sources**: LinkedIn · Indeed · RemoteOK · Rekrute · Emploi.ma · WelcomeToTheJungle · Arbeitnow · TheMuse
- **Real anti-bot stealth**: rotating user-agents, randomized fingerprints, Playwright stealth patches, throttling, retries
- **Multi-threaded scraping** that keeps the GUI responsive — bounded concurrency, cancellation, live progress
- **Hash-based deduplication** (`title · company · canonical_url`) against the local SQLite catalog
- **Modern CustomTkinter GUI**: dark mode, sidebar nav, dashboard, jobs table, exports, logs, analytics, settings, about
- **Filtering & presets**: keyword, country, city, source, remote-only, employment type, experience level
- **Exports**: timestamped `.xlsx` (with multi-sheet per-source breakdown, autosized columns, frozen header), `.csv`, `.json`
- **Scheduler**: APScheduler-based interval/daily/startup runs
- **FastAPI**: drop-in HTTP layer at `http://127.0.0.1:8765` (`/jobs`, `/stats`, `/scrape`, `/export`)
- **Logging**: Loguru with rotation + retention + live tail in-app
- **Docker**: API + scheduler services via `docker-compose up`
- **Windows installer-ready** via PyInstaller

---

## 📦 Project structure

```
jobhunter_pro/
├── app/
│   ├── api/                  FastAPI server
│   ├── core/                 Settings, constants, exceptions, security
│   ├── database/             SQLAlchemy models + repositories
│   ├── gui/                  CustomTkinter UI (main_window, dashboard, sidebar, …)
│   ├── scrapers/             1 base + 8 source-specific scrapers
│   ├── services/             Scraping / export / scheduler / analytics / …
│   ├── utils/                Logger, browser, helpers, validators, file manager
│   └── main.py               CLI entry-point (--api / --headless / GUI)
├── exports/                  Generated XLSX/CSV/JSON files
├── logs/                     Rotated log files
├── data/                     SQLite database
├── tests/
├── screenshots/
├── Dockerfile
├── docker-compose.yml
├── launcher.py               PyInstaller entry-point
├── requirements.txt
└── .env.example
```

---

## 🚀 Installation

### 1. Clone & set up a virtual environment

```bash
git clone <your repo> jobhunter_pro
cd jobhunter_pro
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. Configure environment

```bash
copy .env.example .env        # Windows
# or: cp .env.example .env
```

Edit `.env` to taste — sensible defaults are provided.

### 4. Run the app

```bash
# GUI (default)
python launcher.py

# GUI + background API
python -m app.main --with-api

# API only
python -m app.main --api

# Headless scrape (CLI)
python -m app.main --headless --keyword "Python Developer" --country Morocco
```

---

## 🖥️  Screenshots

Drop screenshots into `screenshots/` as you take them:

| Dashboard                       | Jobs table                      | Analytics                       |
| ------------------------------- | ------------------------------- | ------------------------------- |
| ![](screenshots/dashboard.png)  | ![](screenshots/jobs.png)       | ![](screenshots/analytics.png)  |

---

## 🧱 Architecture

```
┌────────────────────┐    events    ┌──────────────────┐
│  CustomTkinter GUI │◀────────────▶│ ScrapingService  │
└─────────┬──────────┘   queue.Queue└────────┬─────────┘
          │                                  │
          │ method calls                     │ async tasks
          ▼                                  ▼
┌────────────────────┐               ┌──────────────────┐
│  ExportService     │               │  8 × Scraper     │
│  AnalyticsService  │               │  (httpx / PW)    │
│  NotificationSvc   │               └──────────────────┘
│  SchedulerService  │                       │
└─────────┬──────────┘                       │
          │                                  │
          ▼                                  ▼
┌────────────────────────────────────────────────────────┐
│  Repository layer (JobRepo / RunRepo / ExportRepo)     │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │   SQLite (WAL)       │
                └──────────────────────┘
```

Design principles:

- **Service layer pattern** — services orchestrate; repositories own DB queries
- **Single Responsibility** + **Dependency Injection** wherever it pays off
- **Cooperative cancellation** via `threading.Event` ↔ `asyncio.Event` bridge
- **Bounded concurrency** via `asyncio.Semaphore`
- **Thread-safe event bus** via `queue.Queue` so the Tk event loop never blocks

---

## 🐳 Docker

```bash
docker compose up --build
# API:   http://localhost:8765
# Data:  ./jobhunter_data volume
```

---

## 🛠️  PyInstaller build (Windows .exe)

A pre-configured PyInstaller spec ships with the project — works on **Windows 10 and 11** (x64).

### Build it yourself

```powershell
cd HireFlow-AI
.venv\Scripts\activate

# (optional) regenerate the logo / icon
python tools\generate_logo.py

# one-folder build — recommended
pyinstaller HireFlow.spec --clean --noconfirm

# …or via the convenience script (does both at once)
.\tools\build_exe.ps1
```

Output: **`dist\HireFlow\HireFlow.exe`** — ship the entire `dist\HireFlow\`
folder to end users (zip it up, or wrap with Inno Setup for a proper installer).

### First run on the user's machine
Playwright browsers are NOT bundled (would add 500 MB+). On first launch
HireFlow works fully on the API-driven sources (RemoteOK, Arbeitnow, TheMuse,
Jobicy, WeWorkRemotely). To unlock the Playwright-driven scrapers (LinkedIn,
Indeed, WelcomeToTheJungle, Bayt), open a terminal once and run:

```cmd
python -m playwright install chromium
```

Or set `PLAYWRIGHT_BROWSERS_PATH` to a pre-staged Chromium directory before
launching `HireFlow.exe`.

### One-file build (single .exe, slower startup)
Open `HireFlow.spec` — comment out the `COLLECT(...)` block and uncomment the
one-file `EXE(...)` block at the bottom, then re-run the same `pyinstaller`
command. Result: one self-extracting `HireFlow.exe` (~180 MB).

---

## 🔌 API quick-reference

| Method | Endpoint            | Purpose                             |
| ------ | ------------------- | ----------------------------------- |
| GET    | `/`                 | Service banner                      |
| GET    | `/sources`          | Supported job sources               |
| GET    | `/jobs`             | List + filter saved jobs            |
| GET    | `/jobs/{id}`        | Fetch a single job                  |
| GET    | `/stats`            | Analytics summary                   |
| POST   | `/scrape`           | Kick off a scrape                   |
| POST   | `/scrape/cancel`    | Cancel running scrape               |
| GET    | `/scrape/status`    | Whether a scrape is running         |
| GET    | `/export`           | Export jobs to xlsx/csv/json        |

Example:

```bash
curl -X POST http://127.0.0.1:8765/scrape \
     -H "Content-Type: application/json" \
     -d '{"keyword":"Python","country":"Morocco","sources":["LinkedIn","Rekrute"]}'
```

---

## 🐞 Troubleshooting

- **`playwright._impl._errors.Error: Executable doesn't exist`** → Run `python -m playwright install chromium`.
- **`ImportError: tkinter` on Linux** → `sudo apt install python3-tk`.
- **LinkedIn returns 0 results** → LinkedIn aggressively throttles guest queries; raise delays, lower `SCRAPER_CONCURRENT_LIMIT`, or wait.
- **The GUI freezes** → It shouldn't. If it does, check `logs/app.log`; UI work always happens on the main thread, scraping always on background threads.
- **High duplicate count** → Expected on repeated runs; deduplication is based on `title · company · canonical_url`.

---

## 📝 License

MIT © HireFlow AI Team
