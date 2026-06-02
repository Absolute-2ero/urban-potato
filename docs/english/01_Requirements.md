# Requirements

**Product Name:** MacroBite · Diet-Oriented Restaurant Search System  
**Version:** v1.1 
**Last Updated:** 2026-05-25

---

## 1. Overview

### 1.1 Background

As health awareness increases and dietary cultures diversify, users face growing dietary restrictions and preference needs when dining out: veganism, gluten-free, low-carb, halal, keto, allergen avoidance, calorie targets, macronutrient goals, etc. Existing restaurant search tools (e.g., Dianping, Google Maps) have several core shortcomings:

- **Limited dietary filtering dimensions:** Only coarse-grained tags like cuisine or price; cannot precisely match specific dietary requirements or nutritional targets (e.g., calorie ranges, protein or carb thresholds).
- **Insufficient information accuracy:** Ingredients and cooking methods are crucial for users with allergies or medical dietary needs, yet existing platforms rarely include such details.
- **Poor retrieval relevance:** Users describe dietary needs in natural language (e.g., "high protein low fat lunch near Sanlitun under 600 calories"), but current systems cannot understand the semantics.
- **Lack of personalization:** Users' dietary restrictions vary greatly; existing systems lack personalized ranking based on user profiles and past interactions.

### 1.2 Product Vision

MacroBite is a food-focused search engine designed to be simple and intuitive while giving users much finer control over dietary and nutritional filters. It is built on **Information Retrieval (IR)** techniques: users describe dietary needs in natural language, and the system uses document indexing, semantic retrieval, and multi-dimensional ranking to return restaurants and dishes that match dietary requirements, with explainable results.

The goal is to let people search the way they think — whether that's *"high-protein lunch under 600 calories near Sanlitun"* or *"cheap vegan noodles within 2 km."* Beyond basic tags, MacroBite allows filtering by vegetarian, vegan, halal, and specific calorie, protein, or carb ranges, while also incorporating standard factors like distance, price, and reviews into ranking.

The first prototype is developed for **Beijing, China**, using local food data as the foundation.

### 1.3 Scope of This Version

This document covers the core features of v1.0:

- Offline index construction for restaurant and dish data  
- Full-text search based on dietary keywords (BM25 / TF-IDF)  
- Faceted search for dietary categories (vegan, halal, gluten-free, etc.) and nutritional ranges (calories, protein, carbs)  
- Natural language query parsing and query expansion  
- Multi-dimensional relevance ranking  
- Search result display and explainability  
- User dietary profiles and personalized re-ranking  
- Lightweight meal and calorie tracking integrated with search results  

**Out of scope:**

- Restaurant reservations and payments  
- User review generation  
- Merchant management backend  
- Native mobile apps  

---

## 2. Goals & Success Metrics

| Goal | Metric | v1.0 Target |
|------|--------|-------------|
| Improve dietary match precision | Precision@10 | ≥ 0.75 |
| Improve user search satisfaction | CTR@3 | ≥ 50% |
| Support diverse dietary types | Predefined types | ≥ 15 |
| Search response speed | P99 latency | ≤ 500ms |
| Restaurant coverage (Beijing) | Indexed restaurants | ≥ 1,000 |
| Dish-level coverage | Restaurants w/ dish index | ≥ 60% |
| Scalability | Supported index size | ≥ 100,000 |

---

## 3. Target Users

### 3.1 Persona A — Medical Dietary Needs

- **Users:** Diabetes patients, celiac patients, kidney disease dietary restrictions  
- **Needs:** Precisely exclude restaurants containing specific ingredients; require ingredient-level details  
- **Pain points:** Existing platforms lack ingredient details; filtering often yields no results  

### 3.2 Persona B — Active Health Managers

- **Users:** Fitness enthusiasts, keto/low-carb practitioners, calorie-conscious eaters  
- **Needs:** Filter by nutrition goals (e.g., high protein, low calorie, specific carb ranges); view macronutrient data; log meals to track dietary progress  
- **Pain points:** Cannot express nutrition goals in natural language; platforms lack nutrition data; no seamless link between food discovery and meal tracking  

### 3.3 Persona C — Value-Driven Dietary Choices

- **Users:** Vegans, vegetarians, halal eaters, organic food seekers  
- **Needs:** Quickly find restaurants aligned with dietary beliefs  
- **Pain points:** Cannot distinguish vegan vs. flexitarian restaurants  

### 3.4 Persona D — Group Dining Coordinators

- **Users:** People coordinating meals for groups with diverse dietary needs  
- **Needs:** Input multiple dietary restrictions and find restaurants satisfying all  
- **Pain points:** Must manually compare results  

---

## 4. User Stories

### P0 — Must-Have

| ID | Story |
|----|-------|
| US-01 | Natural language dietary search (e.g., "high-protein lunch under 600 calories near Sanlitun") |
| US-02 | Faceted filtering with dietary tags and nutritional ranges (calories, protein, carbs) |
| US-03 | Relevance explanation |
| US-04 | Restaurant detail view |
| US-05 | Spell correction & synonym expansion |

### P1 — Important

| ID | Story |
|----|-------|
| US-06 | Dietary profile creation with default preferences applied automatically on login |
| US-07 | Additional filters (rating, price, distance) |
| US-08 | Sorting modes |
| US-09 | Autocomplete suggestions |
| US-10 | Favorites (liked restaurants and dishes used to refine ranking) |
| US-11 | Meal and calorie tracking: add dishes from search results, log meals, record food notes |
| US-12 | Search and view history: logged-in users can revisit past queries and previously viewed restaurant pages; history can be used as an implicit personalization signal |

### P2 — Nice-to-Have

| ID | Story |
|----|-------|
| US-13 | Relevance feedback |
| US-14 | Similar restaurant recommendations |
| US-15 | Voice input |
| US-16 | Personalized home screen: recommended dishes, trending healthy options nearby, time-of-day or seasonal suggestions |

---

## 5. Functional Requirements
 
### 5.1 Data Layer
 
#### 5.1.1 Restaurant Document
 
| Field | Type | Description |
|-------|------|-------------|
| restaurant_id | string | Unique ID |
| name | string | Restaurant name |
| cuisine_types | string[] | Cuisine tags |
| diet_labels | string[] | Dietary labels |
| allergen_free | string[] | Declared allergen-free items |
| description | string | Description |
| address | string | Street address |
| geo | {lat, lng} | Coordinates |
| price_level | int | 1–4 |
| rating | float | Rating score |
| hours | object | Opening hours |
| menu_items | MenuItem[] | Dishes (ranked by dietary match score at query time) |
 
#### 5.1.2 MenuItem Document
 
| Field | Type | Description |
|-------|------|-------------|
| item_id | string | Dish ID |
| name | string | Dish name |
| description | string | Description |
| diet_labels | string[] | Dietary labels |
| allergens | string[] | Allergens present |
| nutrition | object | Nutrition info (calories, protein, carbs, fat) |
| price | float | Price |
 
#### 5.1.3 User Activity Records (PostgreSQL)
 
Stored per logged-in user; used for personalisation and history browsing.
 
| Record Type | Key Fields | Retention |
|-------------|------------|-----------|
| search_history | user_id, query_text, filters_applied, result_count, searched_at | 90 days |
| restaurant_view_history | user_id, restaurant_id, restaurant_name, viewed_at | 90 days |
 
- Anonymous users generate no history records.
- History is surfaced in the UI as a browsable list and used as an implicit signal in personalised re-ranking (alongside favourites and dietary profile).
#### 5.1.4 Dietary Taxonomy
 
**Values / Beliefs:** vegan, vegetarian, halal, kosher, organic
 
**Medical / Allergy:** gluten-free, dairy-free, nut-free, shellfish-free, soy-free
 
**Health Goals:** low-carb, keto, high-protein, low-calorie, low-sodium
 
**Nutritional Ranges:** calorie range, protein range, carb range (user-specified numeric filters; v1.0 will simplify these to low / medium / high tiers)
 
#### 5.1.5 Data Sources
 
- Xiaohongshu (小红书), Ele.me (饿了么), Meituan (美团), Dianping (大众点评)
- Amap (高德地图), Baidu Maps (百度地图)
- Semi-automated labelling pipeline
- JSON storage format
---
 
### 5.2 Index Layer: Document Index Construction
 
#### 5.2.1 Index Structure Design
 
The system maintains two independent indices:
 
**Primary Index (Restaurant Index):**
- Index granularity: restaurant document
- Full-text indexed fields: `name`, `description`, `cuisine_types` (expanded to text), `diet_labels` (expanded to text), aggregated dish name collection
- Facet indexed fields: `diet_labels`, `cuisine_types`, `price_level`, `rating` (bucketed)
- Numeric indexed fields: `rating`, `price_level`, `geo` (for geographic distance), calorie range, protein range, carb range
**Sub-index (MenuItem Index):**
- Index granularity: dish document (includes parent restaurant ID)
- Full-text indexed fields: `name`, `description`, `diet_labels`
- Numeric indexed fields: `calories`, `protein`, `carbs`, `fat`
- Used for "dish-level search" mode
#### 5.2.2 Text Preprocessing Pipeline
 
```
Raw text
  → Language detection (English / Chinese branch)
  → Tokenisation (English: whitespace + punctuation; Chinese: jieba)
  → Lowercase normalisation (English)
  → Stopword removal (custom stopword list; dietary keywords like "no", "free",
      "without" are intentionally preserved)
  → Stemming / Lemmatisation (English: NLTK PorterStemmer or spaCy Lemmatizer)
  → Synonym expansion (dietary synonym dictionary — see 5.3.2)
  → Build inverted index (term → posting list with TF)
```
 
#### 5.2.3 Technology Selection
 
- **Primary:** Elasticsearch 8.x
  - Rationale: built-in BM25, native Facet support, geo-distance support, result highlighting
- **Lightweight alternative** (for course demo): Whoosh (pure Python) or Tantivy
- The index must support incremental updates — adding or modifying a restaurant must not require a full index rebuild
---
 
### 5.3 Query Processing Layer
 
#### 5.3.1 Query Parsing Pipeline
 
```
User input text
  → Language detection
  → Tokenisation + stopword filtering (consistent with indexing)
  → Entity extraction: location, price intent, dietary type intent,
      calorie / macro numeric values
  → Intent classification:
      - Dietary restriction query ("gluten free restaurants")
      - Nutrition goal query ("high protein low fat")
      - Cuisine query ("Italian vegan pizza")
      - Compound query (any combination of the above)
  → Query expansion (see 5.3.2)
  → Build structured query (Boolean + BM25 combination)
```
 
#### 5.3.2 Query Expansion Strategy
 
**Dietary synonym dictionary (core asset — must be actively maintained):**
 
| Canonical Term | Synonyms / Aliases |
|----------------|-------------------|
| `vegan` | plant-based, no meat, no animal products, 纯素, 植物性饮食 |
| `vegetarian` | veggie, no meat, 素食, 斋菜 |
| `gluten-free` | gluten free, celiac safe, wheat-free, 无麸质, 无小麦 |
| `halal` | halal certified, 清真, 穆斯林友好 |
| `high-protein` | protein rich, high protein, 高蛋白, 增肌餐 |
| `low-carb` | low carbohydrate, carb free, 低碳, 低碳水 |
| `keto` | ketogenic, keto friendly, 生酮饮食 |
| `dairy-free` | lactose free, no milk, no dairy, 无乳糖, 无奶 |
 
**Expansion rules:**
- When a query term matches the dictionary, automatically OR-expand with its synonyms (original term boosted 1.5×, synonyms 1.0×)
- Spell correction: if edit distance ≤ 2, prompt "Did you mean...?" rather than returning empty results
#### 5.3.3 Query Structure Design
 
The standard query is a Bool query combination:
 
```json
{
  "must": [
    "full-text match(query_text, fields=[name^3, description, diet_labels^2, menu_items.name^1.5])"
  ],
  "filter": [
    "facet filter(diet_labels)",
    "price range filter",
    "calorie range filter",
    "protein range filter",
    "open-now filter (optional)"
  ],
  "should": [
    "geo distance decay(geo)",
    "rating boost(rating^0.5)"
  ],
  "minimum_should_match": 0
}
```
 
---
 
### 5.4 Ranking Layer: Relevance Scoring
 
#### 5.4.1 Base Ranking Model
 
**BM25** is used as the base text relevance scorer (parameters: k1=1.2, b=0.75), natively supported in Elasticsearch.
 
#### 5.4.2 Multi-Dimensional Score Fusion
 
Final score = weighted linear combination:
 
```
final_score = α × text_score (BM25)
            + β × diet_match_score       # Exact dietary label match bonus
            + γ × rating_score           # Normalised rating contribution
            + δ × distance_decay         # Distance decay (Gaussian function)
            + ε × personalization_boost  # Personalisation factor (active when profile exists)
```
 
Default weight parameters (adjustable by switching sort mode in the UI):
 
| Sort Mode | α | β | γ | δ | ε |
|-----------|---|---|---|---|---|
| Overall relevance (default) | 0.4 | 0.3 | 0.15 | 0.10 | 0.05 |
| Diet match first | 0.2 | 0.6 | 0.10 | 0.05 | 0.05 |
| Rating first | 0.3 | 0.2 | 0.40 | 0.05 | 0.05 |
| Distance first | 0.3 | 0.2 | 0.10 | 0.35 | 0.05 |
 
#### 5.4.3 Dietary Match Score (diet_match_score)
 
```
diet_match_score =
  Σ(exact_label_match    × 1.0)   # User's query label exactly matches restaurant label
  + Σ(menu_item_match    × 0.6)   # Dish-level label match (when no restaurant-level label)
  + allergen_safe_bonus  × 0.5    # Restaurant declares it is free of user's flagged allergens
  + nutritional_range_match × 0.5 # Dish macros fall within user's target ranges
  - allergen_risk_penalty × 2.0   # Restaurant contains user's flagged allergens (severe penalty)
```
 
#### 5.4.4 Personalised Re-ranking
 
- When the user has a dietary profile, their profile labels are injected into the query's `should` clause to boost personally preferred labels
- Liked restaurants, dish-level dietary profile matches, and search / view history are used as implicit positive signals to update personal ranking weights (lightweight Learning to Rank)
- Recently viewed restaurants and past query patterns boost similar results in future searches
- Personal ranking data is stored in isolation and affects only the current user
---
 
### 5.5 Search Result Presentation
 
#### 5.5.1 Search Result List
 
Each search returns a ranked list of restaurant cards. Within each card, the restaurant's menu items are also ranked by relevance to the current query (dietary match score + keyword overlap), so the most relevant dishes surface at the top of the card rather than in default menu order.
 
Each restaurant card displays:
- Restaurant name + cuisine type tags
- Dietary label badges (colour-coded by category)
- Highlighted query match snippets (matched terms highlighted in name, description, and dish names)
- Rating (stars) + price level + distance (when location is available)
- Allergen warning badge (if applicable — triple encoding: colour + icon + text)
- Diet match indicator bar (graphical display of overall dietary match score)
- Top 2–3 most relevant dishes for the current query, each showing: dish name, dietary labels, calorie / macronutrient summary (where available), price
- "View all dishes" link to the full restaurant detail page
#### 5.5.2 Faceted Navigation Panel
 
An interactive Facet panel displayed on the left side (desktop) or as a top filter bar (tablet/mobile):
 
- **Dietary types:** multi-select checkboxes with document frequency counts (e.g. "vegan (47)")
- **Cuisine:** multi-select, top 10 shown with the rest collapsed
- **Price range:** $ / $$ / $$$ / $$$$
- **Rating:** 4 stars and above / 3 stars and above
- **Calorie range:** user-specified or preset tiers (low / medium / high)
- **Protein / carb range:** user-specified numeric filters
- Active Facets appear as removable chips below the search bar
#### 5.5.3 Search Result Explainability
 
Each result card can expand a "Why is this recommended?" panel showing:
- BM25 matched term list with per-term weights
- Dietary label match status (matched / unmatched / conflicted)
- Nutritional range match explanation (where applicable)
- Allergen risk highlighted in red if any of the user's flagged allergens are present
#### 5.5.4 Search Suggestions (Autocomplete)
 
- Triggered after the user types 2 characters; suggestions update in real time
- Suggestion sources: dietary type dictionary (exact match prioritised) + high-frequency search terms
- When the user has a dietary profile, suggestions matching their profile labels are ranked first
---
 
### 5.6 User Dietary Profile
 
- Optional — anonymous users can search without a profile
- Set during onboarding after registration, or at any time in Settings
- Profile fields: dietary types (multi-select), allergens (multi-select), calorie / macro targets, price preference, cuisine preferences
- Profile effects: pre-fills Facet filters on the Discover tab, adjusts ranking weights, customises Autocomplete suggestions, and enables history-based personalisation
- Profile can be updated or cleared at any time
---
 
### 5.7 Meal & Calorie Tracking
 
- Users can add dishes directly from search results to a daily meal log
- Users can log meals eaten or record general food notes
- Aggregated daily totals (calories, protein, carbs, fat) are displayed in the Diet Tracking tab
- Creates a seamless loop between food discovery and dietary goal tracking
---
 
### 5.8 Search Feedback & Evaluation
 
- Users can optionally mark results as "relevant" or "not relevant" (not mandatory)
- Feedback data is used to compute system-level evaluation metrics (Precision, Recall, NDCG)
- An admin dashboard displays retrieval evaluation reports generated on a regular schedule
---
 
## 6. Non-Functional Requirements
 
### 6.1 Performance
 
- Search response time: P99 ≤ 500ms (including query expansion + retrieval + ranking)
- Autocomplete response time: P99 ≤ 100ms
- Index build time (1,000 restaurants): ≤ 10 minutes (offline batch)
- Concurrent throughput: ≥ 50 QPS (v1.0)
### 6.2 Usability
 
- System availability SLA: ≥ 99% (excluding planned maintenance)
- Meaningful empty result pages with actionable suggestions (e.g. "try removing a filter")
- Spell correction suggestions shown proactively rather than returning empty results
- Interface and search optimised for Chinese-language queries
### 6.3 Scalability
 
- Index architecture must scale to 100,000+ restaurant documents without rewriting core logic
- Dietary taxonomy must support new categories without affecting existing retrieval logic
- Ranking weight parameters are config-file driven — never hardcoded
### 6.4 Accuracy & Fairness
 
- Allergen information display must cite data source and timestamp, and include a "Please confirm with the restaurant" disclaimer
- Nutritional data must show source and confidence level
- Missing data fields must not penalise a restaurant in ranking (absent ≠ negative)
- Dietary labels must be assigned strictly according to the taxonomy — no fuzzy interpretation
### 6.5 Security & Privacy
 
- User dietary profiles (including allergen data) and meal logs are sensitive data and must be encrypted at rest
- Anonymous users' search logs are not linked to any personal identity
- User dietary and tracking data must never be used for ad targeting
---
 
## 7. Scope & Boundaries
 
### In Scope
 
- Restaurant and dish document indexing and full-text search
- Faceted filtering (including nutritional range filters)
- Query parsing, synonym expansion, and spell correction
- BM25 + multi-dimensional score fusion ranking
- Search result highlighting and relevance explainability
- User dietary profile and personalised re-ranking
- Search and restaurant view history (logged-in users)
- Search relevance feedback collection and retrieval evaluation
- Meal and calorie tracking (Diet Tracking tab)
### Out of Scope
 
- Restaurant reservations or food delivery ordering
- Social features (reviews, sharing)
- Merchant-facing data management backend
- Real-time menu crawling
- Native mobile apps
- Full nutrition plan generation
---
 
## 8. Edge Cases & Open Questions
 
### Edge Cases
 
| Scenario | Handling |
|----------|----------|
| Contradictory query constraints (e.g. "vegan beef burger") | Prioritise the stricter dietary label (vegan); return results but display a warning |
| Restaurant has no dietary labels | No dietary badges shown; excluded from dietary match scoring; ranked by text relevance only |
| Restaurant contains user's severe allergen | Red warning badge shown in frontend; restaurant is NOT filtered out (to avoid information suppression), but ranking penalty significantly lowers its position |
| Query is a pure location term with no dietary keywords | Fall back to generic restaurant search; show "No dietary requirements detected — showing nearby restaurants" |
| Multiple dietary constraints yield zero intersection | Show "No restaurants satisfy all requirements simultaneously"; suggest the closest near-match (result after relaxing one constraint) |
| Nutritional range filter is too narrow | Suggest a widened range with nearby results |
 
### Open Questions
 
1. **Evaluation dataset:** How will the query–relevant document pairs be sourced for Beijing data? Expert annotation or crowdsourcing?
2. **User location:** How is location handled in v1.0 — browser GPS permission, manual city input, or manual landmark input?
3. **Bilingual support priority:** Does v1.0 support full Chinese + English search simultaneously, or Chinese-first with English as secondary?
4. **Search granularity for calorie tracking:** When a user adds a dish from search results to the meal log, is the source the restaurant-level dish or the MenuItem index document?
5. **Nutrition data source and update frequency:** USDA FoodData Central API mapping, merchant self-reported data, or LLM estimation? How often is it refreshed?
6. **Dataset licensing:** Local Beijing data sources (Meituan, Dianping, etc.) have usage restrictions — licensing for academic and commercial use must be confirmed.
---
 
## 9. Dependencies
 
| Dependency | Purpose | Risk |
|------------|---------|------|
| Elasticsearch 8.x | Core index and retrieval engine | Requires deployment and maintenance; licensing and resource cost to be assessed |
| Meituan / Dianping dataset | Beijing restaurant and dish corpus | Variable data quality; requires manual cleaning and labelling; licensing constraints |
| spaCy / NLTK | Text preprocessing (tokenisation, lemmatisation) | Version compatibility; Chinese requires additional jieba integration |
| jieba | Chinese tokenisation | Dietary domain terms require a custom dictionary |
| USDA FoodData Central API / local nutrition DB | Dish nutrition data | API rate limits; coverage of Chinese dishes may be limited |
| Amap / Baidu Maps API | User geolocation for distance ranking | User may deny location permission; fallback handling required |
| PostgreSQL | User profiles, favourites, meal logs, activity history | Standard dependency — low risk |
| Redis | Autocomplete cache, popular search term cache | Standard dependency — low risk |