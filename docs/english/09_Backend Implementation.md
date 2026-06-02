# Backend Implementation

**Version:** v1.2
**Last Updated:** 2026-05-25

---

## 1. Startup Sequence

`main.py` executes the following steps in order:

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    await config.load()                  # 1. Load .env → Config object
    await database.init_postgres()       # 2. Create PG connection pool (asyncpg)
    await database.init_sqlite()         # 3. Initialise SQLite food_db (read-only)
    await database.init_elasticsearch()  # 4. Connect to ES, verify index exists
    await database.init_redis()          # 5. Connect to Redis
    await index_service.ensure_index()   # 6. Ensure ES index exists (creates empty index if not)
    yield
    await database.close_all()           # Close all connection pools

app = FastAPI(lifespan=lifespan)

# Register routers
app.include_router(auth_router, prefix="/api/auth")
app.include_router(diet_router, prefix="/api/diet")
app.include_router(food_router, prefix="/api/food")
app.include_router(search_router, prefix="/api/search")
app.include_router(restaurants_router, prefix="/api/restaurants")
app.include_router(feedback_router, prefix="/api/feedback")
app.include_router(internal_router, prefix="/api/internal")
```

Start commands:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload    # development
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 # production
```

---

## 2. Configuration System

**File:** `backend/config.py`

```python
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    # Databases
    postgres_dsn: str           # postgresql+asyncpg://user:pass@host/db
    sqlite_path: str = "data/food_db.sqlite"
    redis_url: str = "redis://localhost:6379/0"
    elasticsearch_url: str = "http://localhost:9200"

    # External APIs
    gaode_api_key: str          # Gaode Maps POI (crawler)

    # IR configuration
    es_index_name: str = "restaurants"
    ranking_config_path: str = "config/ranking.yaml"

    # Session
    session_secret: str         # Required — no default value

    class Config:
        env_file = ".env"       # .env takes priority
```

Sensitive fields (`gaode_api_key`, `postgres_dsn`, `session_secret`) have no default values and must be set in `.env` before starting the server.

> **Note:** LLM API keys (`deepseek_api_key`, `llm_model`) are only required when running the crawler pipeline (`crawler/pipeline.py`), not for normal application operation. They are configured separately in the crawler's own `.env` or environment and are not part of the runtime backend config.

---

## 3. Database Layer

### 3.1 PostgreSQL (asyncpg + SQLAlchemy 2.0)

```python
# database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    config.postgres_dsn,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # Automatically detect dropped connections
)

async def get_db() -> AsyncSession:
    async with AsyncSession(engine) as session:
        yield session
```

**Connection pool settings:** `pool_size=10`, `max_overflow=20`, `pool_recycle=3600`

### 3.2 SQLite (aiosqlite)

```python
# database.py
import aiosqlite

_sqlite_conn: aiosqlite.Connection = None

async def init_sqlite():
    global _sqlite_conn
    _sqlite_conn = await aiosqlite.connect(config.sqlite_path)
    _sqlite_conn.row_factory = aiosqlite.Row
    # Enable WAL mode for better concurrent read performance
    await _sqlite_conn.execute("PRAGMA journal_mode=WAL")
    await _sqlite_conn.execute("PRAGMA foreign_keys=ON")
    await _sqlite_conn.commit()
```

**Note:** SQLite is **read-only at runtime** — it contains only the static preset food library and is never written to by the application. All user-created food entries are stored in PostgreSQL (`user_food_items`).

### 3.3 Elasticsearch

```python
from elasticsearch import AsyncElasticsearch

es: AsyncElasticsearch = None

async def init_elasticsearch():
    global es
    es = AsyncElasticsearch([config.elasticsearch_url])
    info = await es.info()
    logger.info(f"ES connected: {info['version']['number']}")
```

---

## 4. Authentication Implementation

```python
# middleware/auth_middleware.py
from fastapi import Request, HTTPException, Depends
from starlette.middleware.sessions import SessionMiddleware

# Mounted when the app is registered
app.add_middleware(SessionMiddleware, secret_key=config.session_secret)

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    """FastAPI dependency — injected into routes that require login."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Please log in")
    user = await db.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="User not found")
    return user

# Optional auth (anonymous access allowed; extra features available when logged in)
async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return await db.get(User, user_id)
```

---

## 5. IR Core Module Implementation

### 5.1 Query Parser

```python
# ir/query_parser.py
import jieba
import spacy
from .synonyms import DietSynonymDict

class QueryParser:
    def __init__(self):
        self.nlp_en = spacy.load("en_core_web_sm")
        self.synonyms = DietSynonymDict.load("data/diet_synonyms.json")

    def parse(self, query: str) -> ParsedQuery:
        lang = detect_language(query)     # Language detection

        if lang == "zh":
            tokens = list(jieba.cut_for_search(query))
        else:
            doc = self.nlp_en(query.lower())
            tokens = [token.lemma_ for token in doc
                      if not token.is_stop and not token.is_punct]

        # Diet label intent detection
        detected_diet_labels = []
        expanded_tokens = []
        for token in tokens:
            if token in self.synonyms:
                canonical, syns = self.synonyms[token]
                detected_diet_labels.append(canonical)
                expanded_tokens.extend(syns)  # Synonym expansion
            else:
                expanded_tokens.append(token)

        return ParsedQuery(
            original=query,
            tokens=tokens,
            expanded_tokens=expanded_tokens,
            detected_diet_labels=list(set(detected_diet_labels)),
            language=lang,
        )
```

### 5.2 Ranking Service

```python
# services/ranking_service.py
import yaml
from dataclasses import dataclass

class RankingService:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self._weights = yaml.safe_load(f)["sort_modes"]

    def get_weights(self, sort_mode: str) -> dict:
        return self._weights.get(sort_mode, self._weights["default"])

    def rerank(self, hits: list[dict], query: ParsedQuery,
               user_profile: DietProfile | None, user_geo: tuple | None) -> list[dict]:
        weights = self.get_weights(query.sort_mode)

        for hit in hits:
            r = hit["_source"]
            text_score = hit["_score"]  # ES BM25

            diet_score = calc_diet_match_score(
                r, query.detected_diet_labels,
                user_profile.allergens if user_profile else []
            )
            rating_score = r.get("rating", 0) / 5.0
            distance_score = calc_distance_score(r.get("geo"), user_geo)
            personalization = calc_personalization(r, user_profile)

            hit["_final_score"] = (
                weights["text_score"] * text_score +
                weights["diet_score"] * diet_score +
                weights["rating_score"] * rating_score +
                weights["distance_score"] * distance_score +
                weights["personalization"] * personalization
            )
            # Flag allergen warnings
            hit["allergen_warning"] = build_allergen_warning(
                r, user_profile.allergens if user_profile else []
            )

        return sorted(hits, key=lambda h: h["_final_score"], reverse=True)
```

### 5.3 Food Service

```python
# services/food_service.py
import aiosqlite
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.food import UserFoodItem

class FoodService:
    def __init__(self, sqlite: aiosqlite.Connection, pg: AsyncSession):
        self.sqlite = sqlite
        self.pg = pg

    async def search(self, query: str, user_id: int, limit: int = 10) -> SearchResult:
        # Search both sources in parallel
        static_rows, user_rows = await asyncio.gather(
            self._search_static(query, limit),
            self._search_personal(query, user_id, limit),
        )

        # Merge: personal library exact name matches take precedence
        seen_names = set()
        items = []

        for row in user_rows:
            seen_names.add(row["name_zh"])
            items.append({**dict(row), "food_source": "user"})

        for row in static_rows:
            if row["name_zh"] not in seen_names:
                items.append({**dict(row), "food_source": "static"})

        return SearchResult(items=items[:limit])

    async def _search_static(self, query: str, limit: int) -> list:
        async with self.sqlite.execute(
            "SELECT * FROM food_items JOIN food_fts ON food_items.id = food_fts.rowid "
            "WHERE food_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (f"{query}*", limit)
        ) as cursor:
            return await cursor.fetchall()

    async def _search_personal(self, query: str, user_id: int, limit: int) -> list:
        result = await self.pg.execute(
            select(UserFoodItem)
            .where(UserFoodItem.user_id == user_id)
            .where(
                UserFoodItem.name_zh.ilike(f"%{query}%") |
                UserFoodItem.name_en.ilike(f"%{query}%")
            )
            .limit(limit)
        )
        return result.scalars().all()

    async def create_user_food(self, user_id: int, data: UserFoodItemCreate) -> UserFoodItem:
        item = UserFoodItem(user_id=user_id, source="user", **data.model_dump())
        self.pg.add(item)
        await self.pg.commit()
        await self.pg.refresh(item)
        return item

    async def update_user_food(self, food_id: int, user_id: int,
                                data: UserFoodItemUpdate) -> UserFoodItem:
        item = await self._get_user_food_or_404(food_id, user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        item.updated_at = datetime.utcnow()
        await self.pg.commit()
        await self.pg.refresh(item)
        return item

    async def delete_user_food(self, food_id: int, user_id: int) -> None:
        item = await self._get_user_food_or_404(food_id, user_id)
        await self.pg.delete(item)
        await self.pg.commit()

    async def _get_user_food_or_404(self, food_id: int, user_id: int) -> UserFoodItem:
        result = await self.pg.execute(
            select(UserFoodItem)
            .where(UserFoodItem.id == food_id)
            .where(UserFoodItem.user_id == user_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Food entry not found")
        return item
```

---

## 6. Crawler Implementation Notes

### 6.1 Gaode POI Crawler

```python
# crawler/gaode_crawler.py
import httpx

GAODE_PLACE_URL = "https://restapi.amap.com/v3/place/text"

class GaodeCrawler:
    async def fetch_all(self, city: str, limit: int = 500) -> list[RestaurantDoc]:
        results = []
        page = 1
        async with httpx.AsyncClient() as client:
            while len(results) < limit:
                resp = await client.get(GAODE_PLACE_URL, params={
                    "key": config.gaode_api_key,
                    "keywords": "餐厅|饭店|餐馆",
                    "city": city,
                    "page": page,
                    "offset": 20,
                    "extensions": "all",
                })
                data = resp.json()
                if data["status"] != "1" or not data["pois"]:
                    break
                for poi in data["pois"]:
                    results.append(self._normalize(poi))
                page += 1
                await asyncio.sleep(0.1)  # Small delay out of courtesy, even though Gaode's API has no rate limit
        return results[:limit]
```

### 6.2 Dianping Crawler (Playwright)

```python
# crawler/dianping_crawler.py
from playwright.async_api import async_playwright

class DianpingCrawler:
    RATE_LIMIT = 3.0   # seconds

    async def enrich(self, restaurants: list[RestaurantDoc]):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=random.choice(UA_POOL)
            )
            for r in restaurants:
                await self._fetch_one(context, r)
                await asyncio.sleep(self.RATE_LIMIT +
                                    random.uniform(0, 1))   # Random jitter
            await browser.close()

    async def _fetch_one(self, context, restaurant: RestaurantDoc):
        page = await context.new_page()
        try:
            await page.goto(
                f"https://www.dianping.com/search/keyword/{restaurant.city}/10_{restaurant.name}",
                timeout=15000
            )
            # Extract menu items and labels from the first search result
            menu_items = await page.eval_on_selector_all(
                ".menu-item", "els => els.map(e => e.textContent)"
            )
            restaurant.menu_items = parse_menu_items(menu_items)
        except Exception as e:
            logger.warning(f"Dianping fetch failed for {restaurant.name}: {e}")
        finally:
            await page.close()
```

---

## 7. Error Handling

```python
# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "error": exc.detail}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "error": "Internal server error"}
    )
```

**Principles:**
- The business layer raises `HTTPException` (with `status_code` and `detail`)
- Service-layer errors are logged before being re-raised; internal details are never exposed to the user
- Crawler failures degrade gracefully and do not affect the main request flow

---

## 8. Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),                                    # Console
        logging.FileHandler("logs/app.log", encoding="utf-8"),     # File
    ]
)

# Log levels:
# INFO    — Normal business operations (search, diet log entry, user registration)
# WARNING — Degraded fallbacks (crawler 403, ES fallback ranking)
# ERROR   — Issues requiring intervention (DB connection failure, missing config)
```