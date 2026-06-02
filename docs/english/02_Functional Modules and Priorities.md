# Feature Modules & Priorities

**Version:** v1.1
**Last Updated:** 2026-05-25

---

## 1. Module Overview

```
MacroBite · Diet-Oriented Restaurant Search System
├── User System
│   ├── Register / Login / Session Auth
│   └── Personal Dietary Profile (restrictions / goals / allergens)
│
├── Diet Module
│   ├── Manual Diet Logging
│   │   ├── Food Search & Entry
│   │   ├── Portion & Calorie Calculation
│   │   └── Daily Food Log
│   ├── Food Database (Food DB)
│   │   ├── Static Preset Library (common foods ≥ 500 entries)
│   │   ├── User-Added Custom Foods (manually entered by user)
│   │   └── Pre-population on Search (auto-fill fields from DB match; user can edit before saving)
│   └── Dietary Goal Management
│       ├── Daily Calorie Goal Setting
│       ├── Macronutrient Goals (protein / fat / carbs)
│       └── Diet Progress Tracking (consumed vs. target)
│
├── Restaurant Data Collection (Crawler Module)
│   ├── Amap Places API collector (primary — official, free quota)
│   ├── Meituan web page fetcher (secondary — menu & prices)
│   ├── LLM dietary label inference (dish name / photo → labels)
│   └── Data Cleaning & Normalization Pipeline
│
├── IR Core Engine (Search Engine)
│   ├── Offline Index Construction
│   │   ├── Restaurant Main Index
│   │   └── Dish Sub-Index
│   ├── Query Processing
│   │   ├── Query Parsing & Intent Recognition
│   │   ├── Dietary Synonym Expansion
│   │   └── Spell Correction
│   └── Multi-Dimensional Ranking (BM25 + Dietary Match + Rating + Distance)
│
├── Restaurant Search Frontend (Search UI)
│   ├── Search Bar & Autocomplete
│   ├── Faceted Filter Panel (diet type / cuisine / price / rating)
│   ├── Search Results List (with relevance explanation)
│   ├── Restaurant Detail Page (dishes / allergens / nutrition)
│   └── Personalized Ranking (based on dietary profile)
│
└── Search Feedback & Evaluation
    ├── User Relevance Feedback (relevant / not relevant)
    └── System Evaluation Metrics (Precision / Recall / NDCG)
```

---

## 2. Module Priority Matrix

### 2.1 User System

| Sub-Feature | Priority | Status | Notes |
|-------------|----------|--------|-------|
| Register / Login / Session | P0 | 🔲 To Do | Core auth; prerequisite for all other modules |
| Personal Dietary Profile (diet types / allergens) | P0 | 🔲 To Do | Affects search ranking and personalization |
| Dietary Goal Setting (calories / nutrition) | P1 | 🔲 To Do | Depends on the diet logging module |

### 2.2 Diet Module — Manual Diet Logging

| Sub-Feature | Priority | Status | Notes |
|-------------|----------|--------|-------|
| Food keyword search (queries static DB + user-added foods) | P0 | 🔲 To Do | Primary input entry point |
| Pre-population on DB match (fields auto-filled; user can edit before logging) | P0 | 🔲 To Do | If a food is found in DB, its fields are pre-filled for convenience; user may adjust portion, calories, etc. before confirming |
| Portion selection & automatic calorie calculation | P0 | 🔲 To Do | Depends on Food DB |
| Daily food log (CRUD) | P0 | 🔲 To Do | Records the user's daily food intake |
| Manual food entry (when item not in DB) | P0 | 🔲 To Do | User fills in all fields manually; entry is saved to their personal food library for future use |
| Diet progress bar (consumed vs. target) | P1 | 🔲 To Do | Requires goal setting to be complete first |
| Historical log browsing (view by date) | P1 | 🔲 To Do | |

### 2.3 Diet Module — Food Database (Food DB)

| Sub-Feature | Priority | Status | Notes |
|-------------|----------|--------|-------|
| Static preset library (500+ common foods) | P0 | 🔲 To Do | Offline JSON / SQLite storage; covers common Chinese dishes, staples, vegetables, and fruits |
| Food fields: name / calories (kcal/100g) / protein / fat / carbs / diet labels | P0 | 🔲 To Do | Core fields for the static library |
| In-database search (fuzzy match + pinyin support) | P0 | 🔲 To Do | User input of "红烧肉" or "hongshaorou" both return a hit |
| Pre-population flow (search hit → fields auto-filled → user edits → confirm log) | P0 | 🔲 To Do | See 2.3.1 |
| User-defined custom food entry (no DB match) | P0 | 🔲 To Do | See 2.3.2; user manually fills all fields and saves to personal library |
| Edit saved custom foods | P1 | 🔲 To Do | User can update fields of their own custom entries at any time |

#### 2.3.1 Pre-population Flow (Food Found in DB)

When a food entered by the user **matches** an entry in the static database or their personal library, the pre-population path is triggered:

```
User searches for a food name
    → DB match found
    → Fields pre-filled in the log entry form:
        name, calories (kcal/100g), protein (g), fat (g), carbs (g), diet labels
    → User reviews and adjusts as needed (e.g. change portion size, tweak calories)
    → User confirms → entry written to daily food log
```

**Key points:**
- Pre-filled values are **always editable** before the log entry is saved
- Adjustments are applied only to that log entry; the source DB record is not modified
- Both the static preset library and the user's personal food library are searched; personal library takes precedence on exact name match

#### 2.3.2 Manual Entry Flow (Food Not Found in DB)

When a food entered by the user **does not match** anything in the database, the manual entry path is triggered:

```
User searches for a food name
    → No DB match found
    → User is prompted: "This food isn't in our database. Add it manually?"
    → User fills in all fields:
        name, calories (kcal/100g), protein (g), fat (g), carbs (g),
        applicable diet labels (select from list: vegan / vegetarian / gluten-free / ...)
    → User confirms → entry saved to their personal food library
    → Entry also written to daily food log immediately
    → Future searches for the same food name return this personal entry directly
```

**Key points:**
- All fields are filled by the user; no external data source is consulted
- Saved entries are tagged `source: "user"`, distinct from `source: "static"` in the preset library
- User can edit or delete their custom entries at any time from their personal food library
- Personal library entries are scoped to the individual user account

### 2.4 Restaurant Data Collection (Crawler Module)

| Sub-Feature | Priority | Status | Notes |
|-------------|----------|--------|-------|
| **Amap Places API collector** | P0 | 🔲 To Do | Official API, free quota, lowest legal risk; grid-search across Beijing districts; fields: name / category / coordinates / rating / address / hours |
| Scraped field normalization (map to unified Restaurant document schema) | P0 | 🔲 To Do | Normalise Amap + Meituan fields into a single document structure |
| **LLM dietary label inference** (dish name → labels + allergens) | P0 | 🔲 To Do | Primary method for obtaining dietary labels on the **restaurant side**; prompt LLM with dish name (and photo if available) to return labels, estimated calories, and allergen flags as JSON |
| **Meituan web page fetcher** | P1 | 🔲 To Do | Target: menu items and prices for restaurants already identified via Amap; match by name + coordinates; use requests + BeautifulSoup with ≥ 3s delays and User-Agent rotation |
| Automatic dietary label inference (NLP on dish names / descriptions) | P1 | 🔲 To Do | Lightweight rule-based pass before LLM; catch obvious cases (e.g. "纯素" → vegan) cheaply |
| Deduplication & merging (same restaurant across sources) | P1 | 🔲 To Do | Deduplicate by restaurant name + coordinate proximity; Amap coordinates are the canonical anchor |
| OpenStreetMap neighbourhood data | P1 | 🔲 To Do | Enrich restaurant records with district / neighbourhood context for proximity ranking |
| **Dianping HTML scraping** | P2 | 🔲 To Do | Heavy JS rendering, login wall, CAPTCHA, and anti-bot measures rotating every 72h — not viable for v1.0; revisit in v1.2 if needed |
| Incremental crawling (update only new / changed restaurants) | P2 | 🔲 To Do | v1.0 uses full offline batch collection; incremental refresh deferred |
| Crawl scheduling (periodic data refresh) | P2 | 🔲 To Do | v1.0 triggered manually |

> **Note:** LLM is used exclusively in the **restaurant data pipeline** (offline, at data-collection time) for inferring dietary labels from dish names. It is **not** used anywhere in the diet logging or food database module.

#### 2.4.1 Data Source Strategy

| Source | Access Method | Primary Data Contribution | Risk |
|--------|---------------|--------------------------|------|
| Amap | Official Places API (free quota) | Restaurant skeleton: name / coords / category / hours / rating | Low — official API |
| LLM inference | DeepSeek / Qwen API | Dietary labels / allergen flags / calorie estimates per dish (restaurant pipeline only) | Low — no scraping |
| Meituan | HTML fetcher (requests + BeautifulSoup) | Menu items and prices for matched restaurants | Medium — requires rate limiting and User-Agent rotation |
| OpenStreetMap | Static data download (Overpass API) | District and neighbourhood context for proximity features | Low — open data |
| Dianping | HTML crawler (Playwright) | Reviews and feature tags | High — JS rendering + login wall + CAPTCHA; defer to v1.2 |

**v1.0 build order:**
1. Run Amap API collector across Beijing districts (grid search, `keywords=餐厅`) → restaurant skeleton dataset (target: ≥ 500 restaurants)
2. For each restaurant, run LLM inference over collected dish names → dietary labels, allergen flags, calorie estimates stored as JSON
3. Enrich with Meituan fetcher where feasible (menu items, prices) — match to Amap records by name + coordinates
4. Load enriched records into Elasticsearch index
5. Distance ranking uses coordinates already collected from Amap; browser `navigator.geolocation` provides the user's position at query time — no separate geo service needed

### 2.5 IR Core Engine

| Sub-Feature | Priority | Status | Notes |
|-------------|----------|--------|-------|
| Offline restaurant main index construction (Elasticsearch) | P0 | 🔲 To Do | Full-text fields + facet fields + geo fields |
| Text preprocessing pipeline (tokenization / stopwords / stemming) | P0 | 🔲 To Do | Dual-branch: English + Chinese |
| Dietary synonym dictionary (≥ 15 diet types) | P0 | 🔲 To Do | Core asset for query expansion |
| BM25 base text retrieval | P0 | 🔲 To Do | Built into Elasticsearch |
| Faceted filtering (diet type / cuisine / price / rating) | P0 | 🔲 To Do | |
| Multi-dimensional ranking fusion (BM25 + dietary match + rating + distance) | P1 | 🔲 To Do | Weighted linear combination |
| Query intent recognition (dietary restriction / nutrition goal / cuisine) | P1 | 🔲 To Do | Rule-based + keyword matching |
| Spell correction (edit distance ≤ 2) | P1 | 🔲 To Do | |
| Dish sub-index (dish-level retrieval) | P2 | 🔲 To Do | Build only after sufficient dish data is available |
| Personalized re-ranking (based on dietary profile) | P1 | 🔲 To Do | Profile labels injected into query `should` clauses |
| Learning to Rank (based on user click feedback) | P2 | 🔲 To Do | Requires accumulated feedback data before starting |

### 2.6 Restaurant Search Frontend (Search UI)

| Sub-Feature | Priority | Status | Notes |
|-------------|----------|--------|-------|
| Search bar (supports natural language input) | P0 | 🔲 To Do | |
| Autocomplete (real-time search suggestions) | P1 | 🔲 To Do | Triggered at ≥ 2 characters input |
| Faceted filter panel (left sidebar / top bar) | P0 | 🔲 To Do | Includes document frequency display |
| Search results list (card layout) | P0 | 🔲 To Do | Includes highlights, dietary label badges, relevance explanation |
| Sort mode toggle (overall / dietary match / rating / distance) | P1 | 🔲 To Do | |
| Restaurant detail page (dishes / allergens / nutrition info) | P1 | 🔲 To Do | |
| Allergen warning display (red badge) | P0 | 🔲 To Do | Active once user sets allergens in their profile |
| Save / favorite restaurants | P2 | 🔲 To Do | |
| Group mode (intersect multiple dietary requirement sets) | P2 | 🔲 To Do | |
| User location detection (prerequisite for distance-based sorting) | P1 | 🔲 To Do | Browser Geolocation API (`navigator.geolocation`); falls back to manual district input |

### 2.7 Search Feedback & Evaluation

| Sub-Feature | Priority | Status | Notes |
|-------------|----------|--------|-------|
| User relevance feedback (👍 / 👎) | P1 | 🔲 To Do | Optional, not required |
| Evaluation dataset construction (query–relevant document pairs) | P1 | 🔲 To Do | Used to compute Precision / NDCG |
| Offline evaluation reports (generated periodically) | P2 | 🔲 To Do | |

---

## 3. Release Roadmap

### v1.0 — MVP (Current Target)

**Goal:** Deliver an end-to-end working retrieval pipeline using reliable data sources only; validate IR core logic with static data.

**Must complete (P0):**
- User registration / login / dietary profile
- Static food database + manual diet logging + calorie calculation
- Food search with pre-population: DB match → fields auto-filled → user edits → confirm log
- Manual food entry: no DB match → user fills all fields → saved to personal food library
- Amap API restaurant collection (Beijing, ≥ 500 restaurants) → Elasticsearch index construction
- LLM dietary label inference over collected dish names → labels and allergen flags stored per restaurant
- BM25 full-text retrieval + faceted dietary type filtering
- Search results page (with dietary label badges and allergen warnings)
- Distance ranking via Amap coordinates + browser `navigator.geolocation`

**v1.0 target data scale:**
- Food database: ≥ 500 common foods (static preset library)
- Restaurant index: ≥ 500 restaurants (Amap API, Beijing single-city)

### v1.1 — Data Enrichment & Search Quality Improvements

**New additions (P1):**
- Meituan web fetcher goes live (adds menu items and prices to existing restaurant records)
- OpenStreetMap neighbourhood enrichment
- Automatic rule-based dietary label pre-pass (before LLM, restaurant pipeline only)
- Deduplication and merging across sources
- Edit / delete personal food library entries
- Multi-dimensional ranking fusion
- Query expansion (synonym dictionary) + spell correction
- Autocomplete
- Personalized re-ranking (based on dietary profile)
- Diet progress tracking

### v1.2 — Experience Improvements (Planned)

**New additions (P2):**
- Dish sub-index (dish-level retrieval)
- User relevance feedback + Learning to Rank
- Group mode (intersect multiple dietary requirements)
- Save / favorite restaurants
- Incremental crawl scheduling
- Dianping scraper (reassess feasibility at this stage)

---

## 4. Module Dependency Graph

```
User System
    └─► All modules (profile, logs, favorites only saved when logged in)

Food Database (static preset library)
    └─► Manual Diet Logging (data source for food search and pre-population)

User Personal Food Library
    └─► Manual Diet Logging (fallback when static DB has no match; user-added entries
        are searched alongside the preset library in future sessions)

Manual Diet Logging
    └─► Dietary Goal Tracking (accumulated intake vs. target)

Personal Dietary Profile
    ├─► IR Core Engine (input for personalized ranking)
    └─► Frontend Allergen Warnings (allergens in profile → highlighted in results)

Amap API Collector (restaurant skeleton + coordinates)
    ├─► LLM Dietary Label Inference (dish names sent to LLM for label generation)
    ├─► Meituan Fetcher (Amap coordinates used as deduplication anchor)
    └─► IR Core Engine (enriched records loaded into Elasticsearch index)

LLM Dietary Label Inference  ← restaurant pipeline only; not used in diet module
    └─► IR Core Engine (labels become searchable facets and ranking signals)

IR Core Engine
    └─► Restaurant Search Frontend (backend implementation of the search API)

User Relevance Feedback
    └─► Learning to Rank (feedback data drives ranking improvements, v1.2)
```

---

## 5. Technology Stack Summary

| Layer | Choice | Notes |
|-------|--------|-------|
| Indexing & Retrieval | Elasticsearch 8.x | Built-in BM25, facets, geo-distance |
| Text Preprocessing | spaCy (English) + jieba (Chinese) | |
| Food Database (static) | SQLite (development) / PostgreSQL (production) | Lightweight; no separate service needed |
| Personal Food Library | PostgreSQL (same DB as user data) | User-added custom food entries; scoped per user account |
| LLM — dietary label inference | DeepSeek API / Qwen API | **Restaurant pipeline only:** dish name / photo → dietary labels, allergen flags, calorie estimate; runs at data collection time, not query time. Not used in the diet module. |
| Restaurant data collection | Amap Official Places API + requests/BeautifulSoup (Meituan) | Playwright and Dianping deferred to v1.2 |
| Geo / proximity | Amap coordinates + OpenStreetMap (Overpass API) + browser `navigator.geolocation` | No separate geo service needed for v1.0 |
| User Data | PostgreSQL | Profiles / logs / favorites / feedback / personal food library |
| Cache | Redis | Autocomplete cache |
| Frontend Framework | React + TypeScript + Ant Design | |