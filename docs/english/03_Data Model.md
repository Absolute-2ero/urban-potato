# Data Model

**Version:** v1.1
**Last Updated:** 2026-05-25

---

## 1. Database Overview

| Database | Type | Purpose |
|----------|------|---------|
| PostgreSQL | Relational | User accounts, dietary profiles, food logs, personal food library, search feedback, saved restaurants |
| SQLite | Embedded file | Static food database (distributed with the codebase, no separate service needed) |
| Elasticsearch 8.x | Document index | Restaurant main index, dish sub-index, full-text search and faceted filtering |
| Redis | In-memory cache | Autocomplete cache, trending search terms |

---

## 2. Entity Relationship Overview

```
users ─┬─► diet_profiles (user_id)         # Dietary profile (1-to-1)
       ├─► food_log_entries (user_id)       # Daily food log entries (1-to-many)
       ├─► user_food_items (user_id)        # Personal food library (1-to-many)
       ├─► saved_restaurants (user_id)      # Saved restaurants (many-to-many)
       └─► search_feedbacks (user_id)       # Search relevance feedback (1-to-many)

food_log_entries ──► food_items (food_id)       # Log entries reference static food items
food_log_entries ──► user_food_items (food_id)  # Or a user-added food item

food_items (SQLite)
  └── source: "static"         # Pre-built static library (read-only at runtime)

user_food_items (PostgreSQL)
  └── source: "user"           # Manually entered by the user; editable at any time

restaurants (Elasticsearch index)
  └── menu_items[]             # Nested documents (dishes)

search_feedbacks ──► restaurants (restaurant_id, denormalised fields)
```

---

## 3. PostgreSQL Table Schemas

### 3.1 users

| Field | Type | Description |
|-------|------|-------------|
| id | SERIAL PK | User ID |
| username | VARCHAR(64) UNIQUE NOT NULL | Username |
| password_hash | VARCHAR(256) NOT NULL | bcrypt-hashed password |
| email | VARCHAR(128) UNIQUE | Email address |
| created_at | TIMESTAMPTZ DEFAULT now() | Registration timestamp |
| last_login_at | TIMESTAMPTZ | Last login timestamp |

---

### 3.2 diet_profiles

One row per user, created automatically (empty) on registration.

| Field | Type | Description |
|-------|------|-------------|
| user_id | INT PK FK→users.id | User ID (1-to-1) |
| diet_labels | TEXT[] | Dietary type labels (e.g. `{vegan, gluten-free}`) |
| allergens | TEXT[] | Allergens (e.g. `{peanut, shellfish}`) |
| calorie_goal | INT | Daily calorie target (kcal); NULL means not set |
| protein_goal_g | FLOAT | Daily protein target (g) |
| fat_goal_g | FLOAT | Daily fat target (g) |
| carb_goal_g | FLOAT | Daily carbohydrate target (g) |
| price_pref | SMALLINT | Price preference (1–4; NULL = no preference) |
| cuisine_prefs | TEXT[] | Preferred cuisines |
| updated_at | TIMESTAMPTZ | Last modified timestamp |

**Constraints:**
- Values in `diet_labels` must belong to the predefined taxonomy (validated at the application layer)
- `calorie_goal` > 0 (when not NULL)

---

### 3.3 food_log_entries

Records each food item a user consumes per day. This is the core table for the diet tracking module.

| Field | Type | Description |
|-------|------|-------------|
| id | SERIAL PK | Entry ID |
| user_id | INT FK→users.id NOT NULL | Owning user |
| log_date | DATE NOT NULL | Date of the entry |
| meal_type | VARCHAR(16) | Meal slot: breakfast / lunch / dinner / snack |
| food_id | INT | Referenced food item ID from SQLite `food_items`; NULL if from personal library |
| user_food_id | INT FK→user_food_items.id | Referenced personal food item; NULL if from static DB |
| food_name | VARCHAR(128) NOT NULL | Denormalised food name (preserved in case source record changes) |
| quantity_g | FLOAT NOT NULL | Amount consumed (grams) |
| calories_kcal | FLOAT NOT NULL | Calories for this entry (= calories_per_100g × quantity / 100) |
| protein_g | FLOAT | Protein (grams) |
| fat_g | FLOAT | Fat (grams) |
| carb_g | FLOAT | Carbohydrates (grams) |
| created_at | TIMESTAMPTZ DEFAULT now() | Record creation timestamp |

**Constraints:**
- Exactly one of `food_id` or `user_food_id` must be non-NULL (enforced at the application layer)

**Index:** Composite index on `(user_id, log_date)` (high-frequency query pattern)

---

### 3.4 user_food_items

Stores food entries created manually by the user when a food is not found in the static database. Scoped per user account.

| Field | Type | Description |
|-------|------|-------------|
| id | SERIAL PK | Entry ID |
| user_id | INT FK→users.id NOT NULL | Owning user |
| name_zh | VARCHAR(128) NOT NULL | Chinese food name |
| name_en | VARCHAR(128) | English food name (optional) |
| calories | FLOAT NOT NULL | Calories per 100g (kcal) |
| protein_g | FLOAT NOT NULL DEFAULT 0 | Protein per 100g (g) |
| fat_g | FLOAT NOT NULL DEFAULT 0 | Fat per 100g (g) |
| carb_g | FLOAT NOT NULL DEFAULT 0 | Carbohydrates per 100g (g) |
| sodium_mg | FLOAT | Sodium per 100g (mg), optional |
| fiber_g | FLOAT | Dietary fibre per 100g (g), optional |
| diet_labels | TEXT[] | Dietary labels (e.g. `{vegan, gluten-free}`) |
| source | VARCHAR(16) NOT NULL DEFAULT 'user' | Always `user` for this table |
| created_at | TIMESTAMPTZ DEFAULT now() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | Last edited timestamp |

**Notes:**
- Users can edit or delete any row in this table at any time
- Searched alongside the static DB on every food lookup; personal entries take precedence on exact name match
- `food_log_entries` that reference a `user_food_id` retain a denormalised `food_name` snapshot so historical logs remain intact even if the user edits or deletes the source entry

---

### 3.5 saved_restaurants

| Field | Type | Description |
|-------|------|-------------|
| id | SERIAL PK | |
| user_id | INT FK→users.id NOT NULL | |
| restaurant_id | VARCHAR(64) NOT NULL | Elasticsearch document ID |
| restaurant_name | VARCHAR(256) NOT NULL | Denormalised restaurant name (for fast display) |
| saved_at | TIMESTAMPTZ DEFAULT now() | Timestamp when saved |

**Constraint:** Unique on `(user_id, restaurant_id)`

---

### 3.6 search_feedbacks

Records user relevance feedback on search results; used for offline IR evaluation.

| Field | Type | Description |
|-------|------|-------------|
| id | SERIAL PK | |
| user_id | INT FK→users.id | NULL indicates an anonymous user |
| query_text | TEXT NOT NULL | Original search query |
| restaurant_id | VARCHAR(64) NOT NULL | Restaurant that received feedback |
| restaurant_name | VARCHAR(256) | Denormalised field |
| rank_position | SMALLINT | Position of the restaurant in the result list (1-based) |
| is_relevant | BOOLEAN NOT NULL | true = relevant / false = not relevant |
| created_at | TIMESTAMPTZ DEFAULT now() | |

---

## 4. SQLite Table Schema (Food Database)

### 4.1 food_items

File path: `data/food_db.sqlite`, distributed with the project codebase. **Read-only at runtime** — no application code writes to this file after deployment.

```sql
CREATE TABLE food_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name_zh      TEXT NOT NULL,               -- Chinese name
    name_en      TEXT,                        -- English name (optional)
    name_pinyin  TEXT,                        -- Pinyin (for pinyin-based search)
    calories     REAL NOT NULL,               -- Calories per 100g (kcal)
    protein_g    REAL NOT NULL DEFAULT 0,     -- Protein per 100g (g)
    fat_g        REAL NOT NULL DEFAULT 0,     -- Fat per 100g (g)
    carb_g       REAL NOT NULL DEFAULT 0,     -- Carbohydrates per 100g (g)
    sodium_mg    REAL DEFAULT NULL,           -- Sodium per 100g (mg), optional
    fiber_g      REAL DEFAULT NULL,           -- Dietary fibre per 100g (g), optional
    diet_labels  TEXT DEFAULT '[]',           -- JSON array, e.g. '["vegan","gluten-free"]'
    source       TEXT NOT NULL DEFAULT 'static',  -- always 'static' for this file
    created_at   TEXT DEFAULT (datetime('now'))
);

-- Full-text search index
CREATE VIRTUAL TABLE food_fts USING fts5(
    name_zh, name_en, name_pinyin,
    content='food_items', content_rowid='id'
);
```

**Data source notes:**
- `source='static'`: Pre-built library, ≥ 500 entries, manually curated, trusted data. This is the only source value used in this file.
- User-added entries live in PostgreSQL (`user_food_items`), not in this SQLite file.

---

## 5. Elasticsearch Index Mapping

### 5.1 restaurants (main index)

> **Note:** LLM is used **offline at data-collection time only** to infer dietary labels from dish names. No LLM calls occur at query time or during normal application runtime.

```json
{
  "mappings": {
    "properties": {
      "restaurant_id":  { "type": "keyword" },
      "name":           { "type": "text", "analyzer": "ik_max_word", "boost": 3 },
      "name_en":        { "type": "text", "analyzer": "standard" },
      "description":    { "type": "text", "analyzer": "ik_max_word" },
      "cuisine_types":  { "type": "keyword" },
      "diet_labels":    { "type": "keyword" },
      "allergen_free":  { "type": "keyword" },
      "address":        { "type": "text", "analyzer": "ik_smart" },
      "geo":            { "type": "geo_point" },
      "price_level":    { "type": "byte" },
      "rating":         { "type": "float" },
      "source":         { "type": "keyword" },
      "hours": {
        "type": "object",
        "properties": {
          "open":  { "type": "keyword" },
          "close": { "type": "keyword" }
        }
      },
      "menu_items": {
        "type": "nested",
        "properties": {
          "item_id":     { "type": "keyword" },
          "name":        { "type": "text", "analyzer": "ik_max_word", "boost": 1.5 },
          "description": { "type": "text", "analyzer": "ik_max_word" },
          "diet_labels": { "type": "keyword" },
          "allergens":   { "type": "keyword" },
          "price":       { "type": "float" },
          "calories":    { "type": "float" },
          "protein_g":   { "type": "float" },
          "fat_g":       { "type": "float" },
          "carb_g":      { "type": "float" }
        }
      },
      "indexed_at": { "type": "date" }
    }
  },
  "settings": {
    "analysis": {
      "analyzer": {
        "diet_synonym_analyzer": {
          "type": "custom",
          "tokenizer": "ik_smart",
          "filter": ["lowercase", "diet_synonyms"]
        }
      },
      "filter": {
        "diet_synonyms": {
          "type": "synonym",
          "synonyms_path": "analysis/diet_synonyms.txt"
        }
      }
    }
  }
}
```

---

## 6. Data Flow

### 6.1 Food Search and Log Entry

```
User inputs food name
    → Query food_fts (SQLite FTS5) + query user_food_items (PostgreSQL, this user)
    ├─ Hit (static DB)      → Pre-fill log entry form with food_items fields
    ├─ Hit (personal library) → Pre-fill log entry form with user_food_items fields
    │                           (personal library takes precedence on exact name match)
    └─ No hit               → Prompt user: "Not found — add it manually?"
                                → User fills in all fields
                                → INSERT user_food_items (source='user')
                                → Pre-fill log entry form with the new entry

User reviews pre-filled fields, adjusts quantity (and any other fields) as needed
    → Calculate calories_kcal = calories × quantity_g / 100
    → INSERT food_log_entries
```

### 6.2 Restaurant Data Ingestion (Crawler → Elasticsearch)

```
Crawler collects raw data (JSON)                         [one-time offline batch job]
    → Data cleaning & normalisation (field mapping to Restaurant document schema)
    → LLM dietary label inference (dish names → labels + allergen flags)
    → Deduplication (same name + coordinate proximity)
    → Elasticsearch bulk index
```

> LLM is invoked only during this offline ingestion step. Once the index is built, no further LLM calls are made unless the dataset is re-collected and re-indexed.

### 6.3 Search Request Flow

```
User submits search query
    → QueryParser (tokenisation + intent recognition + synonym expansion)
    → Build ES Bool Query (must + filter + should)
    → Elasticsearch returns hits (with _score + highlights)
    → Multi-dimensional re-ranking (BM25 + diet_match + rating + distance)
    → Serialise response → Return to frontend
```