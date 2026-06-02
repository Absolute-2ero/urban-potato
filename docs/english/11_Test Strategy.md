# Testing Strategy

**Version:** v1.1
**Last Updated:** 2026-05-25

---

## 1. Testing Goals

| Goal | Description |
|------|-------------|
| No regressions on core flows | Food search (static DB + personal library), restaurant search, and diet log entry must all pass before every release |
| IR retrieval quality | Evaluation metrics (Precision@10, NDCG@10) must not fall below the baseline after each iteration |
| Allergen safety | Allergen warning logic must have zero omissions; coverage tests for allergen warnings are high priority |
| Data integrity | User-added food entries must be validated before being written to the database; invalid fields must be rejected |
| Ranking stability | After ranking weight config changes, the direction of result changes must match expectations |

---

## 2. Test Layers

```
                    ┌──────────────────────┐
                    │   E2E / IR Evaluation │  ← Full retrieval pipeline + offline eval metrics
                    ├──────────────────────┤
                    │   Integration Tests   │  ← API handlers + real DB (test schema)
                    ├──────────────────────┤
                    │   Unit Tests          │  ← Pure functions, IR components, utilities
                    └──────────────────────┘
```

---

## 3. Unit Tests

### 3.1 Coverage

| Module | Test File | What's Tested |
|--------|-----------|---------------|
| `ir/query_parser.py` | `tests/test_query_parser.py` | Tokenisation correctness, synonym expansion, intent detection |
| `ir/synonyms.py` | `tests/test_synonyms.py` | Dictionary loading, synonym hits, edge-case terms |
| `ir/spell_checker.py` | `tests/test_spell_checker.py` | Edit distance calculation, corrected term accuracy |
| `services/ranking_service.py` | `tests/test_ranking_service.py` | Score fusion weights, allergen penalty, sort direction |
| `services/food_service.py` | `tests/test_food_service.py` | SQLite FTS search, personal library search, merge precedence (personal over static on exact match), manual entry validation |
| `crawler/nlp_labeler.py` | `tests/test_nlp_labeler.py` | Label inference rule correctness |
| `crawler/pipeline.py` | `tests/test_pipeline.py` | Deduplication logic (coordinate proximity), field normalisation |

### 3.2 Testing Principles

- **No mocked databases:** use a dedicated test PostgreSQL schema (`test_macrobite`) and a test SQLite file
- Each test function runs a fixture teardown beforehand (`TRUNCATE` or transaction rollback)
- **ES tests:** use an in-memory ES instance via `elasticsearch-test-utils` or a dedicated test index (`test_restaurants`)

### 3.3 Run Commands

```bash
cd backend
pytest tests/ -v --tb=short                                  # All unit tests
pytest tests/test_ranking_service.py -v                      # Ranking module only
pytest tests/ -v --cov=services --cov-report=term-missing    # Coverage report
```

---

## 4. Integration Tests

### 4.1 Endpoints Covered

| Endpoint | Test Scenarios |
|----------|---------------|
| `POST /api/auth/register` | Successful registration, duplicate username, password too short |
| `POST /api/auth/login` | Successful login, username not found, wrong password |
| `GET /api/food/search?q=` | Static DB hit, personal library hit, personal library takes precedence on exact name match, no results returns empty list with prompt message |
| `POST /api/food/manual` | Successful manual entry saved to personal library, missing required field rejected, invalid `diet_label` rejected, calories ≤ 0 rejected |
| `PUT /api/food/personal/:id` | Successful partial update, wrong user returns 404, invalid field rejected |
| `DELETE /api/food/personal/:id` | Successful delete, existing log entries unaffected, wrong user returns 404 |
| `POST /api/diet/log` | Successful entry (static source), successful entry (user source), food ID not found, cross-source mismatch rejected |
| `GET /api/diet/log` | Query by date, date with no entries, cross-user data isolation |
| `GET /api/search` | Full-text search, facet filtering, allergen warning injection, empty results |
| `PUT /api/diet/profile` | Partial update, invalid `diet_label` rejected |

### 4.2 Test Configuration

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient

@pytest.fixture
async def client(db_session):
    """Each test uses an independent HTTP client with isolated session."""
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c

@pytest.fixture
async def auth_client(client):
    """A pre-authenticated test client."""
    await client.post("/api/auth/register", json={
        "username": "test_user", "password": "Test1234", "email": "t@t.com"
    })
    await client.post("/api/auth/login", json={
        "username": "test_user", "password": "Test1234"
    })
    return client
```

---

## 5. IR System Evaluation (Offline)

This is a project-specific test layer for evaluating retrieval quality. It runs independently from functional tests.

### 5.1 Evaluation Dataset

**Query set construction:**

| Query Type | Count | Source |
|------------|-------|--------|
| Diet type queries ("vegan restaurants", "halal food near me") | 30 | Hand-written |
| Nutrition goal queries ("high protein low fat", "keto friendly") | 20 | Hand-written |
| Compound queries ("vegetarian Japanese affordable") | 20 | Hand-written |
| Allergen exclusion queries ("no peanuts Chinese food") | 10 | Hand-written |
| Misspelled queries ("vegann", "gluten fre") | 10 | Constructed |

**Relevance annotation:**
- Each query is matched against 10+ restaurant documents, independently labelled by 2 annotators on a 3-point scale (0 / 1 / 2)
- Disagreements are resolved by majority; gaps > 1 are discussed and decided manually
- Relevance file format: `data/eval/qrels.tsv` (`query_id \t restaurant_id \t relevance`)

### 5.2 Evaluation Metrics

| Metric | Definition | v1.0 Baseline Target |
|--------|------------|----------------------|
| Precision@10 | Proportion of relevant documents in the top 10 results | ≥ 0.75 |
| Recall@10 | Relevant documents found in top 10 / total relevant documents | ≥ 0.60 |
| NDCG@10 | Normalised Discounted Cumulative Gain (rank-position-aware) | ≥ 0.70 |
| MRR | Mean Reciprocal Rank (rank of the first relevant document) | ≥ 0.80 |
| Allergen Warning Coverage | Proportion of allergen-containing restaurants that display a warning | 100% (zero tolerance) |

### 5.3 Running the Evaluation

```bash
# Run IR evaluation
python -m ir.evaluate \
    --queries data/eval/queries.json \
    --qrels data/eval/qrels.tsv \
    --output reports/eval_$(date +%Y%m%d).json

# Output format
{
  "timestamp": "2026-05-22T10:00:00",
  "metrics": {
    "precision_at_10": 0.78,
    "recall_at_10": 0.63,
    "ndcg_at_10": 0.74,
    "mrr": 0.85,
    "allergen_warning_coverage": 1.0
  },
  "per_query_breakdown": [ ... ]
}
```

### 5.4 When to Run the Evaluation

| Trigger | Action |
|---------|--------|
| Modifying ranking weights (`ranking.yaml`) | Must run; compare metrics before and after |
| Modifying the synonym dictionary | Must run |
| Modifying the diet match scoring formula | Must run |
| Ingesting a new batch of restaurant data | Recommended |
| Before any v1.x release | Must run; metrics must not fall below baseline |

---

## 6. Frontend Tests

### 6.1 Unit Tests (Vitest + Testing Library)

```bash
cd frontend
npm run test               # Run all tests
npm run test:coverage      # Coverage report
```

**Coverage:**

| Component / Hook | What's Tested |
|------------------|---------------|
| `DietBadge` | Correct color per `diet_label`, dashed border for `inferred` confidence, unknown label renders nothing |
| `AllergenWarning` | `aria-role="alert"` is present, allergen name displays correctly |
| `NutritionBar` | Progress bar color changes correctly with percentage (green / yellow / red), no bar rendered when `goal=null` |
| `FilterChips` | Active filters render as chips, removing a chip updates URL params |
| `LanguageToggle` | Clicking toggles between `en` and `zh`, preference is persisted to `localStorage` |
| `FoodSearchModal` | No results triggers manual entry prompt, selecting a food advances to portion step, manual entry form submits to correct endpoint |
| `ManualFoodForm` | Required field validation fires before submit, successful save calls `onSaved` with returned food item |
| `useSearch` | URL param change triggers a new search, updating a filter resets `page` to 1, user profile preferences are applied as defaults on first load |
| `useDebounce` | 200ms debounce fires correctly |

### 6.2 E2E Tests (Playwright — planned for v1.2)

High-priority user flows:

1. Home page search → Results page → Restaurant detail (including allergen warning)
2. Register → Complete preference onboarding → Search (compare personalised vs. no-profile results)
3. Add a food log entry (database hit) → View daily nutrition progress
4. Add a food log entry (no DB match) → Fill manual entry form → Confirm portion → Verify log entry saved
5. Toggle language EN ↔ 中文 → Verify all UI strings update correctly

---

## 7. Data Safety Tests

| Test | What's Verified |
|------|----------------|
| Cross-user data isolation | User A cannot read User B's diet log entries or personal food library entries |
| Manual entry validation | `calories ≤ 0`, missing `name_zh`, and invalid `diet_label` values are all rejected before any DB write |
| Personal library ownership | User A cannot edit or delete User B's `user_food_items` entries (404 returned) |
| Invalid `diet_label` rejected | `PUT /api/diet/profile` and `POST /api/food/manual` with a value not on the allowlist return 400 |
| Allergen 100% coverage | Every restaurant containing a flagged allergen must display a warning in the frontend (automated assertion) |
| Log entry integrity | Deleting a `user_food_items` entry does not delete or corrupt existing `food_log_entries` that referenced it |
| Session isolation | Two independent browser sessions do not interfere with each other |