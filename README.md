# 🥗 DietSearch — Diet-Aware Restaurant Search Engine

A full-stack **Web Information Retrieval** project that helps users find restaurants matching their dietary needs (vegan, halal, gluten-free, keto, etc.) with real-time allergen warnings and nutrition tracking.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Semantic Search** | BM25 + Chinese/English tokenization (jieba), query expansion via a diet synonym dictionary |
| **Multi-dimensional Ranking** | Configurable weighted score: text relevance · diet match · rating · distance |
| **Allergen Guard** | User allergen profile cross-checked against restaurant data; warnings rendered in red (BR-08) |
| **Faceted Search** | Filter by diet label, price level, cuisine type; counts updated per query |
| **Spell Correction** | Levenshtein edit-distance correction for English diet terms |
| **Real-time Crawler** | Search-triggered background crawl via OpenStreetMap Overpass API + Gaode Web; results flow into ES automatically |
| **Scheduled Crawler** | Hourly batch crawl across 6 major Chinese cities × 14 diet keywords |
| **NLP Labeler** | Regex-based diet label & allergen inference from restaurant name/description |
| **Food Diary** | Log meals, track daily calorie/macro intake, visualise against DRI targets |
| **LLM Fallback** | Unknown foods estimated by DeepSeek API; user must confirm before DB insertion (BR-03) |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│               React + Ant Design             │  Vite 5, TypeScript, Zustand
│  HomePage · SearchPage · DietLogPage · ...  │  URL ↔ store sync via useSearch hook
└─────────────────┬───────────────────────────┘
                  │  REST / JSON
┌─────────────────▼───────────────────────────┐
│              FastAPI (Python 3.9)            │  Session auth (itsdangerous)
│  /api/search · /api/food · /api/diet · ...  │  25 routes, async throughout
└──┬──────────┬──────────┬────────────────────┘
   │          │          │
   ▼          ▼          ▼
Elasticsearch  PostgreSQL  SQLite (food DB)
  8.x BM25    (users,      FTS5 virtual table
  IK Chinese  diet_log,    + LLM fallback
  geo_point   saved)       + Redis cache
                              │
                         Redis 7
                         (session, crawl lock,
                          LLM result cache)
                              │
                    ┌─────────▼──────────┐
                    │  Crawler Pipeline  │
                    │  OSM Overpass API  │
                    │  Gaode Web (H5)    │
                    │  NLP Labeler       │
                    └────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.9+
- Node.js 18+

### 1. Start Infrastructure

```bash
docker-compose up -d
# PostgreSQL :5432  · Elasticsearch :9200  · Redis :6379
```

### 2. Backend

```bash
cd backend
cp .env.example .env          # Fill in secrets (SESSION_SECRET is required)
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# App: http://localhost:5173
```

### 4. Seed Data (optional — automatic crawl runs on first search)

```bash
cd backend
python -m crawler.pipeline --city 北京 --keywords 素食,清真,有机
```

---

## 📁 Project Structure

```
urban-potato/
├── docker-compose.yml          # PostgreSQL · Elasticsearch · Redis
├── backend/
│   ├── main.py                 # FastAPI app + lifespan + scheduler
│   ├── config.py               # pydantic-settings (reads .env)
│   ├── database.py             # Async connection pools (asyncpg, aiosqlite, redis, es)
│   ├── models/                 # Pydantic v2 models
│   ├── db/                     # PostgreSQL DDL + SQLite FTS5 schema + seed
│   ├── data/                   # diet_synonyms.json · food_seed.json · stopwords · ranking.yaml
│   ├── ir/                     # query_parser · synonyms · spell_checker
│   ├── services/               # auth · food · diet · search · ranking · index
│   ├── routers/                # FastAPI routers (auth/food/diet/search/restaurants/feedback)
│   ├── middleware/             # Request logging middleware
│   └── crawler/
│       ├── osm_crawler.py      # OpenStreetMap Overpass API (free, no key)
│       ├── web_crawler.py      # Gaode Web H5 endpoints + OSM fallback
│       ├── gaode_crawler.py    # Gaode official API (requires GAODE_API_KEY)
│       ├── nlp_labeler.py      # Regex-based diet label & allergen tagging
│       ├── realtime_crawler.py # Search-triggered async crawl + hourly scheduler
│       └── pipeline.py         # CLI: python -m crawler.pipeline --city ...
└── frontend/
    ├── src/
    │   ├── types/              # TypeScript type definitions
    │   ├── constants/          # Diet label metadata (color, emoji, zh label)
    │   ├── api/                # axios wrappers (auth/food/diet/search/restaurants)
    │   ├── stores/             # Zustand stores (auth · search · diet)
    │   ├── hooks/              # useSearch — URL ↔ store sync
    │   ├── components/         # SearchBar · DietBadge · ResultCard · NutritionBar · ...
    │   └── pages/              # HomePage · SearchPage · DietLogPage · RestaurantDetail · ...
    └── vite.config.ts          # Proxy /api → :8000
```

---

## ⚙️ Environment Variables

See [`backend/.env.example`](backend/.env.example) for the full list. Key variables:

| Variable | Description | Required |
|---|---|---|
| `SESSION_SECRET` | ≥32-char random string for cookie signing | ✅ |
| `POSTGRES_DSN` | PostgreSQL connection string | ✅ |
| `GAODE_API_KEY` | Gaode Maps official API key (batch crawler) | Optional |
| `DEEPSEEK_API_KEY` | DeepSeek API key for LLM food fallback | Optional |

---

## 🔍 IR Design Highlights

### Multi-dimensional Ranking

Final score formula (weights configurable in `backend/config/ranking.yaml`):

```
score = w_text  × norm_bm25
      + w_diet  × (diet_match_score + 2) / 4   # mapped from [-2,2] to [0,1]
      + w_rating × (rating / 5)
      + w_dist  × exp(-(dist_km / scale_km)²/2) # Gaussian decay
```

Four sort modes: `default` · `diet_first` · `rating_first` · `distance_first`

### Diet Score

- **+1.0** per matched diet label between query and restaurant
- **+0.5** per allergen declared allergen-free by restaurant
- **−2.0** per allergen in user profile that the restaurant contains

### Real-time Crawl Trigger

```
Search hits < 5  →  asyncio.create_task(crawl)   # non-blocking
                 →  return current results immediately
                 →  frontend shows 10s countdown + auto-refresh
```

---

## 📊 Offline Evaluation Metrics

- **Precision@10** — fraction of top-10 results that are relevant
- **NDCG@10** — ranking quality with graded relevance
- **MRR** — Mean Reciprocal Rank for first relevant result
- **Allergen Recall** — fraction of allergen-flagged restaurants correctly warned

See [`docs/11_测试策略.md`](docs/11_测试策略.md) for the full evaluation plan.

---

## 📄 License

MIT

