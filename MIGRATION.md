# Migrating to a New Machine

Two scripts handle the full migration. Run them from the **project root**.

---

## On the old machine

### 1. Export data

```powershell
.\export_data.ps1
```

This creates an `export/` folder containing:
- `food_db.sqlite` — HK crawler data (pipeline state + restaurant docs)
- `postgres_dump.sql` — user accounts, saved restaurants, preferences

### 2. (Optional) Add BJ restaurant data

If you want BJ search to work on the new machine, copy the BJ NDJSON export into `export/` and rename it:

```
export/restaurants_bj.ndjson
```

The default location for this file is `../backend-bj/restaurants-es-export/restaurants_data.ndjson`. You can also export it manually:

```powershell
# From backend/
py -3.12 -m scripts.import_bj_data --dry-run   # verify path first
```

### 3. Push your code

```powershell
git add .
git commit -m "your message"
git push origin feat/hk-frontend
```

### 4. Transfer the export folder

Copy the `export/` folder to the new machine via USB drive, cloud storage, etc. **Do not commit it to git** — it contains a full database dump.

---

## On the new machine

### Prerequisites

Install these before running setup:

| Tool | Where |
|------|-------|
| Docker Desktop | https://www.docker.com/products/docker-desktop/ |
| Python 3.12 | https://www.python.org/downloads/ |
| Node.js 18+ | https://nodejs.org/ |
| Git | https://git-scm.com/ |

### 1. Clone and set up

```powershell
git clone <your-repo-url>
cd urban-potato
git checkout feat/hk-frontend   # or main, whichever you pushed to
```

### 2. Copy your .env

```powershell
copy backend\.env.example backend\.env
# Then open backend\.env and fill in your real keys:
#   LLM_API_KEY, GAODE_API_KEY, SESSION_SECRET
```

Or copy `backend/.env` directly from the old machine if you have it.

### 3. Place the export folder

Put the `export/` folder from the old machine into the project root:

```
urban-potato/
  export/
    food_db.sqlite
    postgres_dump.sql
    restaurants_bj.ndjson   ← optional
```

### 4. Run setup

```powershell
.\setup.ps1
```

This will:
1. Create a Python virtualenv and install all dependencies
2. Run `npm install` for the frontend
3. Start Postgres, Elasticsearch, and Redis via Docker
4. Restore the Postgres dump
5. Copy the SQLite database
6. Re-index HK restaurants into Elasticsearch
7. Import BJ restaurants (if `restaurants_bj.ndjson` is present)

### 5. Start the app

**Backend** (in one terminal):
```powershell
cd backend
.\.venv\Scripts\uvicorn main:app --reload --port 8000
```

**Frontend** (in another terminal):
```powershell
cd frontend
npm run dev
```

App runs at http://localhost:5173

---

## After the initial setup

Docker volumes persist between reboots. To start services again after a restart:

```powershell
docker compose up -d
```

To stop all services:

```powershell
docker compose down
```

---

## Crawler utilities (HK)

| Script | What it does |
|--------|-------------|
| `py -3.12 -m crawler.hk.foodpanda_login_saver` | Save a logged-in Foodpanda session (run if crawler hits a login wall) |
| `py -3.12 -m crawler.actions.reset_llm` | Reset all HK restaurants for LLM re-labeling |
| `py -3.12 -m crawler.actions.reset_failed_llm` | Reset only restaurants with missing nutrition data |
| `py -3.12 -m scripts.reindex_hk_from_sqlite` | Re-index HK data from SQLite into Elasticsearch |

Run all commands from the `backend/` directory.
