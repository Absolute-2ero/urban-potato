# System Architecture

**Version:** v1.1
**Last Updated:** 2026-05-25

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                          Client Layer                             │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │          Frontend (React + TypeScript + Ant Design)          │  │
│  │          Dev: localhost:3000  /  Prod: nginx :80             │  │
│  └─────────────────────────┬───────────────────────────────────┘  │
└────────────────────────────┼─────────────────────────────────────┘
                             │ HTTP/HTTPS (REST)
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                  Backend Service Layer (Python / FastAPI)         │
│                  0.0.0.0:8000  HTTPS                              │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │  Auth Router │  │  Diet Router │  │  Search Router           │  │
│  │  /api/auth   │  │  /api/diet   │  │  /api/search            │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬────────────┘  │
│         └─────────────────┴───────────────────────┘               │
│                             │                                      │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │                      Service Layer                           │  │
│  │  AuthService │ DietService │ FoodService │ SearchService     │  │
│  │  CrawlerService │ RankingService │ IndexService              │  │
│  └──┬───────────────┬────────────────┬────────────────┬────────┘  │
│     │               │                │                │            │
│  ┌──▼──┐  ┌─────────▼──┐  ┌─────────▼──┐  ┌─────────▼──────────┐ │
│  │ PG  │  │   SQLite   │  │    Redis   │  │  Elasticsearch 8.x  │ │
│  │:5432│  │ food_db    │  │   :6379    │  │     :9200           │ │
│  └─────┘  └────────────┘  └────────────┘  └────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                             │
             ┌───────────────┴───────────────┐
             ▼                               ▼
┌────────────────────────┐  ┌──────────────────────────┐
│  Amap Places API       │  │  Meituan                 │
│  (restaurant crawler)  │  │  requests + BS4          │
└────────────────────────┘  └──────────────────────────┘

External LLM (DeepSeek / Qwen) — offline crawler pipeline only;
not connected to the runtime backend.
```

---

## 2. Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Backend language | Python | 3.11+ | Main service; mature NLP ecosystem |
| HTTP framework | FastAPI | 0.110+ | Routing, dependency injection, auto-generated docs |
| Data validation | Pydantic v2 | 2.x | Request / response schemas |
| Session management | fastapi-sessions | — | Cookie session handling |
| PostgreSQL driver | asyncpg + SQLAlchemy 2.0 | — | Async PostgreSQL access |
| SQLite driver | aiosqlite | — | Async SQLite (static food database, read-only) |
| Elasticsearch client | elasticsearch-py (async) | 8.x | Index construction and search |
| Redis client | redis-py (asyncio) | — | Autocomplete cache, trending search terms |
| NLP (Chinese) | jieba | — | Chinese tokenisation |
| NLP (English) | spaCy (en_core_web_sm) | 3.x | Lemmatisation, NER |
| Password hashing | passlib[bcrypt] | — | User password storage |
| Crawler (JS rendering) | playwright (Python) | — | Dianping (deferred to v1.2) |
| Crawler (static pages) | httpx + BeautifulSoup | — | Meituan |
| Task scheduling | APScheduler | — | Scheduled crawls (v1.2) |
| Frontend framework | React + TypeScript | 18 / 5.x | Client-side SPA |
| UI component library | Ant Design | 5.x | UI components |
| Frontend routing | React Router | 6 | SPA routing |
| Frontend state | Zustand | — | Lightweight global state |
| HTTP client | Axios | — | Frontend API calls |

---

## 3. Package Structure (Backend)

```
backend/
├── main.py                        # Entry point: create FastAPI app, register routers, start server
├── config.py                      # Load config from environment variables / .env (central config)
├── database.py                    # Connection pool initialisation (PG + SQLite + ES + Redis)
│
├── routers/
│   ├── auth.py                    # Register / login / logout
│   ├── diet.py                    # Food logs, dietary profile
│   ├── food.py                    # Food search (SQLite static DB + PG personal library)
│   ├── search.py                  # Restaurant search
│   ├── restaurants.py             # Restaurant detail, saved restaurants
│   └── feedback.py                # Search feedback
│
├── services/
│   ├── auth_service.py            # Registration / login business logic
│   ├── diet_service.py            # Log CRUD, progress calculation
│   ├── food_service.py            # Food search, manual entry, personal library CRUD
│   ├── search_service.py          # Query processing → ES → re-ranking
│   ├── ranking_service.py         # Multi-dimensional score fusion
│   └── index_service.py           # Elasticsearch index management (build / update)
│
├── crawler/
│   ├── gaode_crawler.py           # Amap POI API collector
│   ├── dianping_crawler.py        # Dianping Playwright crawler (v1.2)
│   ├── meituan_crawler.py         # Meituan httpx crawler
│   ├── pipeline.py                # Clean → deduplicate → infer labels → write to ES
│   └── nlp_labeler.py             # Dietary label inference (rule-based + LLM, offline only)
│
├── models/
│   ├── user.py                    # Pydantic + SQLAlchemy ORM models (User)
│   ├── diet.py                    # FoodLogEntry, DietProfile
│   ├── food.py                    # FoodItem (SQLite mapping), UserFoodItem (PG mapping)
│   └── restaurant.py              # Restaurant ES document model (Pydantic)
│
├── middleware/
│   ├── auth_middleware.py         # Session auth middleware
│   └── rate_limit.py              # Basic request rate limiting
│
├── ir/
│   ├── query_parser.py            # Query parsing (tokenisation, intent recognition, expansion)
│   ├── synonyms.py                # Dietary synonym dictionary (load + lookup)
│   └── spell_checker.py           # Spell correction (English, edit distance)
│
├── data/
│   ├── food_db.sqlite             # Static food database (binary, read-only at runtime)
│   ├── food_seed.json             # Seed data for the static library (used to rebuild SQLite)
│   ├── diet_synonyms.txt          # Synonym file loaded by Elasticsearch
│   └── stopwords/
│       ├── zh_stopwords.txt       # Chinese stopwords
│       └── en_stopwords.txt       # English stopwords (negation terms preserved)
│
└── tests/
    ├── test_food_service.py
    ├── test_search_service.py
    ├── test_ranking_service.py
    └── test_query_parser.py
```

---

## 4. Key Data Flows

### 4.1 Food Search (Diet Tracker)

```
GET /api/food/search?q=红烧肉
    → food.router → FoodService.search(query, user_id)
        → SQLite FTS5 query (static DB, read-only)        [parallel]
        → PostgreSQL query on user_food_items (this user) [parallel]
        ├─ Hits found
        │   → Personal library exact matches take precedence
        │   → Return merged results list (nutrition fields pre-filled)
        │
        └─ No hits
            → Return empty list
            → Frontend prompts: "Not found — add it manually?"

POST /api/food/manual {name_zh, calories, protein_g, fat_g, carb_g, diet_labels, ...}
    → FoodService.create_user_food(data, user_id)
        → Validate fields
        → INSERT INTO user_food_items (source='user')
        → Return new record (frontend pre-fills log entry form)

POST /api/diet/log {food_source, food_id, quantity_g, meal_type, log_date}
    → DietService.create_log_entry(data, user_id)
        → Fetch nutrition from SQLite or user_food_items depending on food_source
        → Calculate calories_kcal, protein_g, fat_g, carb_g at write time
        → INSERT INTO food_log_entries
        → Return new entry
```

### 4.2 Restaurant Search

```
GET /api/search?q=素食&diet_labels=vegan&sort=default&lat=39.9&lng=116.4
    → search.router → SearchService.search(params)
        → QueryParser.parse(q)                   # tokenise, detect intent, expand synonyms
        → RankingService.get_weights(sort_mode)  # read ranking.yaml
        → ES async_search(bool_query)
        → hits → RankingService.rerank(hits, user_profile)
                    → calc_diet_match_score(restaurant, query_labels, user_allergens)
                    → calc_distance_score(restaurant.geo, user_geo)
                    → weighted_sum → sort
        → format_response(sorted_hits)           # attach highlights, allergen_warning
        → return JSON
```

### 4.3 Crawler Pipeline (Offline Batch — not part of runtime backend)

```
python -m crawler.pipeline --city beijing --source all

→ GaodeCrawler.fetch_all()
    → Amap API paginated POI fetch (20 per page, N restaurants total)
    → output List[RestaurantDoc] (skeleton records)

→ MeituanCrawler.enrich(restaurants)
    → httpx requests to Meituan; extract menu items and prices → merge into RestaurantDoc

→ NLPLabeler.infer_diet_labels(restaurants)
    → rule-based keyword matching (fast pass)
    → LLM inference over dish names (DeepSeek / Qwen) for remaining unlabelled dishes
    → populate diet_labels per restaurant

→ Pipeline.dedup(restaurants)
    → coordinate proximity deduplication (R-tree spatial index)

→ IndexService.bulk_index(restaurants)
    → ES bulk API, 100 documents per batch
    → write crawl log
```

> This pipeline runs manually in v1.0 (scheduled in v1.2). The LLM is only called here — once per crawl run, offline, before the index is built. The running backend never calls the LLM.

---

## 5. IR Core Design

### 5.1 Index Build Strategy

```
Full build (initial):
  python -m ir.index_builder --source data/restaurants.json

Incremental update (v1.2):
  python -m ir.index_builder --mode incremental --since 2026-05-01
  → Re-index only documents where indexed_at < since or source_updated_at > since
```

### 5.2 Analyser Configuration (Elasticsearch)

```json
{
  "settings": {
    "analysis": {
      "analyzer": {
        "zh_diet_analyzer": {
          "type": "custom",
          "tokenizer": "ik_smart",
          "filter": ["lowercase", "zh_stop", "diet_synonyms"]
        },
        "en_diet_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "en_stop", "diet_synonyms", "porter_stem"]
        }
      }
    }
  }
}
```

### 5.3 Query Construction Example

User input: `"gluten free high protein near me"`

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "multi_match": {
            "query": "gluten-free high-protein",
            "fields": ["name^3", "description", "diet_labels_text^2", "menu_items.name^1.5"],
            "type": "best_fields",
            "analyzer": "en_diet_analyzer"
          }
        }
      ],
      "filter": [
        { "terms": { "diet_labels": ["gluten-free", "high-protein"] } }
      ],
      "should": [
        {
          "function_score": {
            "gauss": {
              "geo": {
                "origin": "39.9,116.4",
                "scale": "2km",
                "offset": "500m",
                "decay": 0.5
              }
            }
          }
        }
      ]
    }
  },
  "highlight": {
    "fields": { "name": {}, "description": {}, "menu_items.name": {} }
  }
}
```

---

## 6. Security Design

| Concern | Implementation |
|---------|---------------|
| Transport security | Full-site HTTPS in production (Let's Encrypt certificate) |
| Authentication | Cookie session (HttpOnly + Secure + SameSite=Lax) |
| Password storage | bcrypt hash, cost=12; plaintext never stored |
| API key management | Injected via `.env` + environment variables; zero hardcoding in source |
| Data isolation | All user data queries include `WHERE user_id = ?` (BR-02, BR-03) |
| Allergen warnings | Computed server-side and included in the response; cannot be bypassed by the frontend (BR-08) |
| Crawler compliance | Respect robots.txt; maintain reasonable request intervals; no user private data stored |

---

## 7. Deployment Topology (Current)

```
Single-machine deployment (Linux server / local development)

┌──────────────────────────────────────────────────────────┐
│  Process: uvicorn main:app          :8000  HTTPS          │
│  Process: React Dev Server / nginx  :3000 / :80          │
│  Process: PostgreSQL 16             :5432                 │
│  Process: Elasticsearch 8.x         :9200                 │
│  Process: Redis 7                   :6379                 │
│  File:    data/food_db.sqlite        ./data/  (read-only) │
│  File:    .env (chmod 600)           ./backend/           │
└──────────────────────────────────────────────────────────┘

Crawler pipeline runs separately (offline, on demand):
  python -m crawler.pipeline --city beijing --source all
  (requires LLM API key in .env; not needed for normal app operation)
```