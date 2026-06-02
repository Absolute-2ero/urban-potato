# Business Logic

**Version:** v1.2
**Last Updated:** 2026-05-25

---

## 1. Core Business Rules

| Rule ID | Rule Description | Module(s) |
|---------|-----------------|-----------|
| BR-01 | All write operations (logs, profiles, saved restaurants, feedback) require authentication; unauthenticated requests return 401 | Global |
| BR-02 | Users may only read and write their own dietary profile, food logs, and saved restaurants | Diet module |
| BR-03 | Users may only read, edit, and delete their own personal food library entries (`user_food_items`) | Food database |
| BR-04 | `food_log_entries` must reference exactly one food source: either `food_id` (static DB) or `user_food_id` (personal library), never both and never neither | Diet module |
| BR-05 | Anonymous users may perform searches and view restaurant details; they may not save logs, save restaurants, or submit feedback | Search, diet module |
| BR-06 | Crawler-collected data must be cleaned and deduplicated before being written to Elasticsearch; raw data is never written directly | Crawler |
| BR-07 | `calories_kcal` in food log entries must be calculated and stored at write time (denormalised); it must not rely on calculation at query time | Diet module |
| BR-08 | Allergen matching is hard logic: any restaurant containing an allergen present in the user's profile must display a warning in the frontend regardless of its ranking position | Search results |
| BR-09 | Values in `diet_labels` must come from the predefined taxonomy (see requirements doc 5.1.2); arbitrary strings are rejected | Profile, index |
| BR-10 | Weight parameters for the search score fusion formula must be read from a configuration file and must not be hardcoded | IR engine |
| BR-11 | The SQLite food database file is read-only at runtime; no application code may INSERT, UPDATE, or DELETE from it | Food database |
| BR-12 | Denormalised `food_name` in `food_log_entries` must be written at log time and must not be updated if the source food record is later edited or deleted; historical logs must remain intact | Diet module |

---

## 2. User System

### 2.1 Registration Flow

```
Input: username, password, email

1. Check username uniqueness (query users table)
   └─ Already exists → return 400 "Username is already taken"

2. Validate password strength (≥ 8 characters, must contain letters and digits)
   └─ Invalid → return 400 "Password must be at least 8 characters and contain letters and digits"

3. bcrypt hash the password (cost = 12)

4. INSERT INTO users

5. INSERT INTO diet_profiles (empty profile, linked to user_id)

6. Write session, return success (user is automatically logged in)
```

### 2.2 Login Flow

```
Input: username, password

1. SELECT * FROM users WHERE username = ?
   └─ Not found → return 401

2. bcrypt compare password vs password_hash
   └─ No match → return 401 (do not distinguish between "wrong username" and "wrong password")

3. Write session (user_id)
4. UPDATE users SET last_login_at = now()
5. Return 200
```

### 2.3 Auth Middleware

```python
# FastAPI Dependency
async def get_current_user(session: Session = Depends(get_session)):
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401)
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=401)
    return user
```

---

## 3. Diet Module

### 3.1 Food Search Flow

```
Input: query (food name entered by the user)

Step 1: Search both food sources in parallel
  a) SQLite FTS5 (static library — read-only)
     SELECT * FROM food_fts
     WHERE food_fts MATCH '{query}*'
     ORDER BY rank LIMIT 10

  b) PostgreSQL personal library (this user only)
     SELECT * FROM user_food_items
     WHERE user_id = ? AND (name_zh ILIKE '%{query}%' OR name_en ILIKE '%{query}%')
     LIMIT 10

Step 2: Merge and return results
  ├─ Hits found
  │   → Personal library exact name matches take precedence over static DB matches
  │   → Return merged food list (with nutrition data pre-filled)
  │
  └─ No hits
      → Return empty result
      → Frontend prompts: "This food isn't in our database. Add it manually?"
      → User proceeds to manual entry flow (see 3.2)
```

### 3.2 Manual Food Entry Flow

```
Input: name_zh, name_en (optional), calories, protein_g, fat_g, carb_g,
       sodium_mg (optional), fiber_g (optional), diet_labels[]

Triggered when: food search returns no results and user chooses to add manually

1. Authenticate (BR-01, BR-03)

2. Validate required fields:
   └─ name_zh empty → return 400 "Food name is required"
   └─ calories < 0  → return 400 "Calories must be a positive number"

3. Validate diet_labels against predefined taxonomy (BR-09)
   └─ Invalid label → return 400 "Invalid diet label"

4. INSERT INTO user_food_items (source='user', user_id=current_user.id)

5. Return new user_food_items record
   → Frontend immediately pre-fills the log entry form with this record
   → User confirms quantity → log entry is created (see 3.3)
```

### 3.3 Food Log Entry Flow

```
Input: food_source ('static' | 'user'), food_id, quantity_g, meal_type,
       log_date (defaults to today)

1. Authenticate (BR-01)

2. Fetch nutrition data based on source:
   ├─ source = 'static'
   │   → SELECT * FROM food_items WHERE id = food_id        [SQLite]
   │   └─ Not found → return 400
   └─ source = 'user'
       → SELECT * FROM user_food_items WHERE id = food_id AND user_id = ?  [PostgreSQL]
       └─ Not found or wrong user → return 400

3. Calculate nutrition values:
   calories_kcal = food.calories × quantity_g / 100
   protein_g     = food.protein_g × quantity_g / 100
   fat_g         = food.fat_g × quantity_g / 100
   carb_g        = food.carb_g × quantity_g / 100

4. INSERT INTO food_log_entries (BR-07: calculate at write time, not at query time)
   → Set food_id or user_food_id depending on source (BR-04)
   → Denormalise food_name from source record (BR-12)

5. Return new entry (including id and calculated nutrition values)
```

### 3.4 Personal Food Library Management

```
Edit entry
  Input: user_food_id, updated fields

  1. Authenticate (BR-01, BR-03)
  2. SELECT * FROM user_food_items WHERE id = ? AND user_id = ?
     └─ Not found or wrong user → return 404
  3. Validate updated fields (same rules as 3.2)
  4. UPDATE user_food_items SET ..., updated_at = now()
  5. Return updated record
  Note: existing food_log_entries that referenced this entry are unaffected —
        they retain their denormalised food_name and calculated values (BR-12)

Delete entry
  Input: user_food_id

  1. Authenticate (BR-01, BR-03)
  2. SELECT * FROM user_food_items WHERE id = ? AND user_id = ?
     └─ Not found or wrong user → return 404
  3. DELETE FROM user_food_items WHERE id = ?
  4. Return 204
  Note: food_log_entries that referenced this entry remain intact via denormalised
        fields; the foreign key user_food_id will be a dangling reference — set to
        NULL on delete (ON DELETE SET NULL) so historical logs are not deleted (BR-12)
```

### 3.5 Daily Diet Progress Calculation

```
Input: user_id, date

1. SELECT SUM(calories_kcal), SUM(protein_g), SUM(fat_g), SUM(carb_g)
   FROM food_log_entries
   WHERE user_id = ? AND log_date = ?

2. SELECT calorie_goal, protein_goal_g, fat_goal_g, carb_goal_g
   FROM diet_profiles
   WHERE user_id = ?

3. Calculate completion percentage for each metric (consumed / goal × 100%)
   └─ If goal is NULL → do not show a progress bar for that metric; display intake value only

4. Return aggregated result
```

---

## 4. Restaurant Data Collection (Crawler)

### 4.1 Collection Pipeline

```
Trigger: manual (v1.0) / scheduled task (v1.2)

Step 1: Amap POI collection (P0 — runs first)
  → Call Amap Place Search API (keyword="餐厅", specify city)
  → Returns POI list (name, location, address, type, rating)
  → Normalise into Restaurant document skeleton
  → Write to temporary storage (JSON file / memory)

Step 2: Meituan web fetcher (P1 — enriches the Amap skeleton)
  → Use Amap restaurant name as search keyword on Meituan
  → requests + BeautifulSoup to extract:
      - Menu items (menu_items)
      - Prices and promotional info
  → Match to same-name restaurant and merge fields

Step 3: Data cleaning & normalisation
  → Deduplication (same name + coordinates within 50m = same restaurant)
  → LLM dietary label inference (see 4.2)
  → Field completeness validation

Step 4: Write to Elasticsearch
  → Bulk index (100 documents per batch)
  → Record crawl log (source, count, timestamp)
```

> **Note:** Dianping HTML scraping is deferred to v1.2 due to high anti-scraping risk (JS rendering, login wall, CAPTCHA). See Feature Modules 2.4 for the full tier rationale.

> **Note:** LLM is invoked only during this offline batch pipeline (Step 3). No LLM calls occur at query time or during normal application runtime.

### 4.2 Dietary Label Inference Rules

Raw collected data has no dietary labels. Labels are inferred automatically using the following rules:

```
Rule matching (descending priority):

1. Restaurant name keyword matching:
   "素食" | "蔬食" | "vegetarian" → diet_labels += "vegetarian"
   "纯素" | "vegan"               → diet_labels += "vegan"
   "清真" | "halal" | "穆斯林"    → diet_labels += "halal"
   "无麸质" | "gluten-free"       → diet_labels += "gluten-free"

2. LLM inference over dish names and descriptions:
   → Send dish name list to LLM; receive dietary labels and allergen flags as JSON
   → Labels are stored with source: "llm_inferred"

3. Menu-level aggregate analysis (rule-based fallback):
   70%+ of dishes contain "豆腐"|"蔬菜"|"素"  → vegetarian candidate
   No dishes contain "猪"|"牛"|"羊"|"鸡"|"鱼"|"虾" → vegan candidate
   (Candidate labels have lower confidence; tagged as inferred, not confirmed)

4. Confidence tagging:
   diet_labels_source: "name_match" | "llm_inferred" | "menu_inferred"
   (Frontend can use this to decide whether to show a confidence indicator)
```

### 4.3 Rate Limiting & Anti-Scraping Rules (BR-06)

| Source | Request Interval | User-Agent Strategy | Error Handling |
|--------|-----------------|---------------------|----------------|
| Amap API | No limit (official API) | Fixed API key | Back off 60s on 429 |
| Meituan | ≥ 3s per request | Random rotation from UA pool (10+ entries) | Switch IP or pause on 403/429 |

---

## 5. Search Business Logic

### 5.1 Query Processing Flow

```
Input: query_text, filters (diet_labels[], price_level[], rating_min),
       geo (lat, lng), sort_mode, page

Step 1: Query preprocessing
  → Language detection (Chinese / English / mixed)
  → Tokenisation (ik_smart for Chinese / standard for English)
  → Stopword filtering (preserve negation terms: 无, 不含, free, without)
  → Spell correction (edit distance ≤ 2, English only)

Step 2: Query expansion
  → Iterate over tokens; look up dietary synonym dictionary
  → Matched terms expanded to synonym group (original term boost=1.5, synonyms boost=1.0)

Step 3: Build Elasticsearch Bool Query
  must:   full-text match (name^3, description, diet_labels_text^2, menu_items.name^1.5)
  filter: diet_labels (terms), price_level (terms), rating (range)
  should: geo_distance decay (Gaussian function), rating boost

Step 4: Execute Elasticsearch query (BM25 ranking)

Step 5: Multi-dimensional re-ranking (Python side)
  final_score = α×text_score + β×diet_score + γ×rating_score + δ×distance_score
  (weights read from config file — BR-10)

Step 6: Allergen flagging (BR-08)
  For each result: check restaurant.allergens ∩ user_profile.allergens
  ├─ Intersection non-empty → attach allergen_warning field (frontend must display red warning)
  └─ No intersection → display normally

Step 7: Serialise results
  → Each result includes: highlights (matched term positions), diet_match_detail, allergen_warning
  → Return paginated results (default page_size = 10)
```

### 5.2 Dietary Match Score Calculation

```python
def calc_diet_match_score(restaurant, query_diet_labels, user_allergens):
    score = 0.0

    # Positive: restaurant-level label match
    for label in query_diet_labels:
        if label in restaurant.diet_labels:
            score += 1.0

    # Positive: dish-level label match (fallback when no restaurant-level label matches)
    if score == 0:
        menu_hit = any(
            label in item.diet_labels
            for item in restaurant.menu_items
            for label in query_diet_labels
        )
        if menu_hit:
            score += 0.6

    # Positive: restaurant declares itself free of a user allergen
    for allergen in user_allergens:
        if allergen in restaurant.allergen_free:
            score += 0.5

    # Penalty: restaurant contains a user allergen (severe penalty — BR-08)
    for allergen in user_allergens:
        if allergen in restaurant.allergens:
            score -= 2.0

    return max(score, -2.0)   # floor at -2.0 (when allergen is present)
```

### 5.3 Sort Mode Weight Configuration

```yaml
# config/ranking.yaml
sort_modes:
  default:
    text_score:      0.40
    diet_score:      0.30
    rating_score:    0.15
    distance_score:  0.10
    personalization: 0.05
  diet_first:
    text_score:      0.20
    diet_score:      0.60
    rating_score:    0.10
    distance_score:  0.05
    personalization: 0.05
  rating_first:
    text_score:      0.30
    diet_score:      0.20
    rating_score:    0.40
    distance_score:  0.05
    personalization: 0.05
  distance_first:
    text_score:      0.30
    diet_score:      0.20
    rating_score:    0.10
    distance_score:  0.35
    personalization: 0.05
```

---

## 6. Error Handling

### 6.1 Food Database Errors

| Error | Handling |
|-------|----------|
| SQLite file corrupted | Detect on startup; if corrupted, rebuild static library from seed file |
| user_food_items record not found or wrong user | Return 404; do not reveal whether the record exists for another user |
| Manual entry fails validation | Return 400 with specific field error; do not partially write |

### 6.2 Search Errors

| Error | Handling |
|-------|----------|
| Elasticsearch unavailable | Return 503; frontend displays "Search service temporarily unavailable" |
| Empty query results | Return 200 with empty list + suggestion to relax filters |
| Re-ranking calculation error | Fall back to raw Elasticsearch BM25 scores; log a warning |
| Geolocation not provided | Set distance dimension weight to 0; other dimensions are unaffected |

### 6.3 Crawler Errors

| Error | Handling |
|-------|----------|
| Meituan returns 403 | Pause that source for 30 minutes; continue processing other sources |
| Meituan triggers CAPTCHA | Pause; log alert; wait for manual intervention |
| Amap API quota exceeded | Stop collection for the day; resume the next day (quota resets daily) |
| Restaurant record has missing fields | Allow partial records; do not reject an entry due to missing fields |
| LLM API error during ingestion | Log error; skip label inference for that batch; labels can be re-inferred on next crawl run |