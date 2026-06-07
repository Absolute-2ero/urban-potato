# MacroBite — Final Presentation

---

## Slide 1 — Title

# 🥗 MacroBite
### "Find the Right Macros for Every Bite"

**A diet-aware restaurant search platform for Beijing & Hong Kong**

*Powered by Elasticsearch · ZhipuAI · Kimi · Gaode*

---

## Slide 2 — The Problem

### THE ETERNAL QUESTION:

> "I want something vegan, high-protein, under ¥50, within 2km, and not spicy."

- **Google:** 🤷 "Here's a random hotpot place."
- **Dianping:** 🤷 "Have you tried McDonald's?"
- **Your friend:** 🤷 "Just eat whatever lah."

Existing platforms don't filter by:
- ✗ Dietary labels (vegan / halal / gluten-free)
- ✗ Dish-level nutrition (protein / calories)
- ✗ Natural language intent ("something light for my diet")
- ✗ Allergens you actually care about

---

## Slide 3 — What is MacroBite?

MacroBite is a full-stack restaurant search app that:

- 🔍 Understands what you **mean**, not just what you type
- 🥦 Filters by diet labels, allergens & nutrition
- 📍 Searches by location (any landmark, not just GPS)
- 🧠 Learns your food preferences over time
- 🤖 Has a mascot named **Mac** who gives you life advice

### Coverage:
| City | Restaurants | Data Source |
|------|-------------|-------------|
| 🇨🇳 Beijing | 55,514 | Gaode / AMap POI |
| 🇭🇰 Hong Kong | 2,188 | OpenRice (dish-level) |
| **Total** | **57,702** | |

---

## Slide 4 — MacroBite Unique Features

| Feature | Description |
|---------|-------------|
| 🥗 **Mac the Mascot** | Your snarky AI dining companion (GLM-4) |
| 🔍 **Dual Search Mode** | Smart (LLM intent) + Semantic (vector similarity) |
| 🍱 **Dish-Level Search** | HK data has per-dish calories, protein, allergens |
| 📋 **Diet Tracking** | Log meals, track macros daily |
| ❤️ **Saved Restaurants** | Bookmark favorites, persisted to DB |
| 👤 **Personalization** | Learns from views & saves; re-ranks to match taste |
| 🌍 **Multi-City** | Beijing + Hong Kong; extensible architecture |

---

## Slide 5 — System Architecture

```
USER
 │
 ▼
REACT FRONTEND  ──────── Vite + Ant Design + Zustand
 │  │
 │  └── /api/search/parse ──▶  Kimi LLM
 │                              (intent extraction + Gaode geocoding)
 ▼
FASTAPI BACKEND
 │
 ├── IR Parser  (jieba + synonyms + landmarks)
 ├── Embedding Service  (ZhipuAI embedding-2)
 │
 ▼
ELASTICSEARCH 8.13
 ├── BM25 full-text  (IK Analyzer)
 └── kNN vector search  (1024-dim cosine)
 │
 ▼
RANKING SERVICE
 ├── text_score · diet_score · rating_score
 ├── distance_score  (Gaussian decay)
 ├── pref_score  (user preference vector)
 └── diversity injection
```

---

## Slide 6 — The Data Pipeline

### HOW WE GOT THE DATA *(a love story with many plot twists)*

**Phase 1: The Dream**
- Target Dianping & Ele.me
- "Rich review data, dish info, ratings — perfect!"
- Build scrapers. Test. **Success! 🎉**

**Phase 2: Reality Strikes**
- Deploy scrapers at scale…
- 🚫 **BANNED. Both of them. Immediately.**
- *"Your IP has been blocked. Have a nice day."*

**Phase 3: Pivot**
- **Beijing** → Gaode / AMap Web Service API *(30,000 free calls/day · POI data · no dish info)*
- **Hong Kong** → Foodpanda + OpenRice *(dish-level data · nutrition · allergens ✓)*

---

## Slide 7 — The Great Ban of 2024 🚫

### *We thought we were hackers. Dianping thought otherwise.*

| Time | Event |
|------|-------|
| T+00:00 | Scrapers deployed, data flowing in ✅ |
| T+00:03 | "Wait, why are the responses empty?" 🤔 |
| T+00:05 | Check IP logs… |
| T+00:06 | ████████ **BANNED** ████████ |
| T+00:07 | Try VPN |
| T+00:08 | ████████ **BANNED** ████████ |
| T+00:09 | "Maybe Ele.me is easier?" |
| T+00:11 | ████████ **BANNED** ████████ |
| T+00:12 | (╯°□°）╯︵ ┻━┻ |

> **Lesson learned:** Always have a backup data source.
> *(and maybe don't scrape at 1000 req/s at 2am)*

---

## Slide 8 — Data Sources & Coverage

### BEIJING — Gaode / AMap Web Service API
- 55,514 restaurants indexed
- POI data: name, address, cuisine, rating, geo
- Diet labels inferred via keyword matching + LLM
- No dish-level data *(Gaode API limitation)*
- Grid-based crawl strategy covering core districts

### HONG KONG — OpenRice (partner export)
- 2,188 restaurants with full dish-level data
- Per-dish: calories, protein, fat, carbs
- Allergen flags per dish
- LLM-enriched diet labels (GLM-4 annotation pipeline)

### EMBEDDINGS
- All 57,702 restaurants embedded via **ZhipuAI embedding-2**
- 1,024 dimensions · cosine similarity · 99.96% coverage

---

## Slide 9 — Search: How It Works

### SMART MODE ⚡
```
User types: "cheap halal hotpot near Wudaokou"
     ↓
Kimi LLM extracts:
  q="火锅"  location="五道口"  diet=["halal"]
  price=[1,2]  radius=5km
     ↓
Gaode geocoding: "五道口" → (40.0023, 116.3394)
     ↓
Elasticsearch BM25 + geo filter → results
```

### SEMANTIC MODE 🎯
```
User types: "cozy place for a date with good vibes"
     ↓
ZhipuAI embeds raw query → 1024-dim vector
     ↓
ES kNN search → semantically similar restaurants
(no keyword match needed — pure meaning similarity)
```

**HYBRID (default):** BM25 score + kNN score summed by ES

---

## Slide 10 — Personalization Engine

### HOW MACROBITE LEARNS YOUR TASTE

1. **User views / saves a restaurant**
   - `POST /api/interactions` → SQLite `user_interactions` table

2. **Build preference vector**
   - Fetch embeddings of last 50 interacted restaurants from ES
   - Exponential weighted average *(recent = higher weight, decay = 0.92)*
   - L2-normalize → 1024-dim preference vector

3. **Re-rank search results**

```
final_score = 0.40 × text_score
            + 0.30 × diet_score
            + 0.15 × rating_score
            + 0.10 × distance_score
            + 0.05 × pref_score   ← you are here
```

4. **Diversity injection**
   - If top-10 results are >70% one diet label → inject up to 3 different ones

---

## Slide 11 — The Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 18, Vite, Ant Design 5, Zustand, TypeScript |
| **Backend** | FastAPI, Python 3.11, asyncpg, aiosqlite |
| **Search** | Elasticsearch 8.13, IK Analyzer, BM25 + kNN |
| **Database** | PostgreSQL, SQLite, Redis |
| **AI / LLM** | Kimi (query parsing), GLM-4 (Mac avatar), ZhipuAI embedding-2 |
| **Maps** | Gaode / AMap Web Service API |
| **IR** | jieba, synonym expansion, spell correction, landmark detection |

---

## Slide 12 — Query Understanding Pipeline

**Input:** `"五道口500米内便宜的清真火锅"`

```
STEP 1  Kimi LLM  →  { q:"火锅", location:"五道口",
                        radius_km:0.5, diet:["halal"], price:[1,2] }

STEP 2  Gaode Geocoding  →  "五道口" → (39.9913, 116.3393)

STEP 3  IR Parser (local, fast)
         jieba tokenization
         + diet synonym expansion  ("清真" → halal)
         + landmark detection  (local coordinate dict)

STEP 4  Elasticsearch  →  BM25 text + geo_distance + kNN
```

**English support:** `"hotpot"` → `"火锅"` *(LLM translates to Chinese before search)*

---

## Slide 13 — Database Stats

### BY THE NUMBERS

| Metric | Value |
|--------|-------|
| 🏪 Total restaurants | **57,702** |
| 🇨🇳 Beijing | **55,514** |
| 🇭🇰 Hong Kong | **2,188** |
| 🧬 With semantic embeddings | **57,453 (99.6%)** |

### Top Diet Labels
| Label | Count |
|-------|-------|
| 🥦 Vegetarian | 5,495 |
| 🌙 Halal | 2,451 |
| 🍃 Low-calorie | 1,414 |
| 💪 High-protein | 948 |
| 🌱 Vegan | 953 |

**Avg search latency:** ~120ms (BM25) · ~300ms (hybrid) · ~2.5s (Smart + LLM)

---

## Slide 14 — Challenges & Lessons

| Challenge | What Happened | Lesson |
|-----------|--------------|--------|
| 🚫 Getting banned | Dianping & Ele.me blocked us instantly | Read the ToS. Or be slower. |
| 📐 Coordinate chaos | Gaode returns GCJ-02 not WGS84 | "Why is my restaurant in the ocean?" |
| 🧩 ES hybrid search | RRF requires Enterprise license | Sum BM25 + kNN scores directly |
| ⚡ Per-keystroke search | Early build fired a search on every character | Search only on explicit submit |
| 🌐 Multi-city arch | BJ = restaurant-level, HK = dish-level | Two query strategies, one abstraction |

---

## Slide 15 — Future Improvements

- 🏠 **Homepage Recommendations** — Personalized feed without a query; collaborative filtering
- 🌆 **More Cities** — Shanghai, Shenzhen, Guangzhou, Singapore
- 🍽️ **Dish-level Data for Beijing** — Need a source that won't ban us 🙃
- 📱 **Mobile App** — React Native; push notifications at lunchtime
- 🤝 **Restaurant Partnerships** — Real-time menus, exclusive deals

---

## Slide 16 — Time for Demo 🎬

# 🥗

# Time for Demo

---

*Let's see if it works.*

*(it definitely works, we tested it this morning, probably)*

---

## Slide 17 — Contributions

### Built with ❤️ (and a lot of debugging) by:

**Teammate 1**
-
-
-

**Teammate 2**
-
-
-

---

*🥗 MacroBite — Find the Right Macros for Every Bite*
