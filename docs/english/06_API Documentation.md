# API Documentation

**Version:** v1.1
**Last Updated:** 2026-05-25

---

## Overview

- **Base URL:** `http://localhost:8000` (development) / `https://<host>` (production)
- **Protocol:** HTTP / HTTPS
- **Authentication:** Cookie Session (`HttpOnly; SameSite=Lax`)
  - Protected endpoints require a Session obtained by calling `POST /api/auth/login` first
  - Accessing a protected endpoint without login returns `401`
- **Common Response Format:**
  ```json
  { "code": 200, "data": { ... } }          // Success
  { "code": 400, "error": "Description" }    // Client error
  { "code": 401, "error": "Please log in" }  // Unauthorized
  { "code": 500, "error": "Internal server error" } // Server error
  ```
- **Pagination Parameters:** `page` (starting from 1), `page_size` (default 10, max 50)

---

## Table of Contents

1. [User Authentication](#1-user-authentication)
2. [Diet Profile](#2-diet-profile)
3. [Food Database](#3-food-database)
4. [Diet Log](#4-diet-log)
5. [Restaurant Search](#5-restaurant-search)
6. [Restaurant Details & Favorites](#6-restaurant-details--favorites)
7. [Search Feedback](#7-search-feedback)
8. [Crawler Management (Internal)](#8-crawler-management-internal)

---

## 1. User Authentication

### 1.1 Register

```
POST /api/auth/register
```

**Request Body (JSON)**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| username | string | ✅ | Username (unique, 4–32 chars, alphanumeric and underscores) |
| password | string | ✅ | Plaintext password (≥8 chars, must contain letters + numbers) |
| email | string | ✅ | Email address |

**Response 200**
```json
{
  "code": 200,
  "data": { "user_id": 1, "username": "alice" }
}
```

**Error 400**
```json
{ "code": 400, "error": "Username already taken" }
```

---

### 1.2 Login

```
POST /api/auth/login
```

**Request Body (JSON)**

| Field | Type | Required |
|-------|------|----------|
| username | string | ✅ |
| password | string | ✅ |

**Response 200**
```json
{ "code": 200, "data": { "user_id": 1, "username": "alice" } }
```

---

### 1.3 Logout

```
POST /api/auth/logout
```
Clears the Session. No request body required.

**Response 200**
```json
{ "code": 200, "data": null }
```

---

### 1.4 Get Current User Info

```
GET /api/auth/me
```
Requires login.

**Response 200**
```json
{
  "code": 200,
  "data": {
    "user_id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "created_at": "2026-05-22T10:00:00Z"
  }
}
```

---

## 2. Diet Profile

### 2.1 Get Diet Profile

```
GET /api/diet/profile
```
Requires login.

**Response 200**
```json
{
  "code": 200,
  "data": {
    "diet_labels": ["vegan", "gluten-free"],
    "allergens": ["peanut"],
    "calorie_goal": 2000,
    "protein_goal_g": 120,
    "fat_goal_g": 65,
    "carb_goal_g": 250,
    "price_pref": 2,
    "cuisine_prefs": ["Chinese", "Japanese"]
  }
}
```

---

### 2.2 Update Diet Profile

```
PUT /api/diet/profile
```
Requires login. Supports partial updates (only pass the fields you want to modify).

**Request Body (JSON, all fields optional)**

| Field | Type | Description |
|-------|------|-------------|
| diet_labels | string[] | Diet types; values must be from the predefined list |
| allergens | string[] | Allergens |
| calorie_goal | int \| null | Daily calorie goal (kcal) |
| protein_goal_g | float \| null | Protein goal (g) |
| fat_goal_g | float \| null | Fat goal (g) |
| carb_goal_g | float \| null | Carbohydrate goal (g) |
| price_pref | int(1–4) \| null | Price preference |
| cuisine_prefs | string[] | Cuisine preferences |

**Response 200**
```json
{ "code": 200, "data": { "updated": true } }
```

---

## 3. Food Database

### 3.1 Search Food

```
GET /api/food/search?q={query}&limit=10
```

Searches both the static food database (SQLite) and the user's personal food library (PostgreSQL) in parallel. Personal library exact name matches take precedence.

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| q | string | ✅ | Food name (supports Chinese / pinyin / English) |
| limit | int | ❌ | Number of results to return; default 10, max 20 |

**Response 200 — results found**
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "food_id": 42,
        "food_source": "static",
        "name_zh": "红烧肉",
        "name_en": "Red-braised Pork Belly",
        "calories": 395,
        "protein_g": 14.6,
        "fat_g": 34.2,
        "carb_g": 6.4,
        "diet_labels": []
      },
      {
        "food_id": 7,
        "food_source": "user",
        "name_zh": "自制燕麦饼",
        "name_en": "Homemade Oat Cookie",
        "calories": 420,
        "protein_g": 9.0,
        "fat_g": 16.0,
        "carb_g": 58.0,
        "diet_labels": ["vegetarian"]
      }
    ]
  }
}
```

**Response 200 — no results**
```json
{
  "code": 200,
  "data": {
    "items": [],
    "message": "No results found. You can add this food manually."
  }
}
```

---

### 3.2 Add Food Manually (Personal Library)

```
POST /api/food/manual
```
Requires login. Creates a new entry in the user's personal food library. Use when a food is not found via search.

**Request Body (JSON)**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name_zh | string | ✅ | Food name in Chinese |
| name_en | string | ❌ | Food name in English |
| calories | float | ✅ | Calories per 100g (kcal); must be > 0 |
| protein_g | float | ✅ | Protein per 100g (g) |
| fat_g | float | ✅ | Fat per 100g (g) |
| carb_g | float | ✅ | Carbohydrates per 100g (g) |
| sodium_mg | float | ❌ | Sodium per 100g (mg) |
| fiber_g | float | ❌ | Dietary fibre per 100g (g) |
| diet_labels | string[] | ❌ | Diet labels; values must be from the predefined list |

**Response 200**
```json
{
  "code": 200,
  "data": {
    "food_id": 12,
    "food_source": "user",
    "name_zh": "螺蛳粉",
    "name_en": "River Snail Rice Noodle",
    "calories": 458,
    "protein_g": 18.0,
    "fat_g": 15.0,
    "carb_g": 62.0,
    "diet_labels": []
  }
}
```

**Error 400**
```json
{ "code": 400, "error": "calories must be a positive number" }
```

---

### 3.3 List Personal Food Library

```
GET /api/food/personal?page=1&page_size=20
```
Requires login. Returns all food entries created by the current user.

**Response 200**
```json
{
  "code": 200,
  "data": {
    "total": 3,
    "items": [
      {
        "food_id": 12,
        "name_zh": "螺蛳粉",
        "name_en": "River Snail Rice Noodle",
        "calories": 458,
        "protein_g": 18.0,
        "fat_g": 15.0,
        "carb_g": 62.0,
        "diet_labels": [],
        "created_at": "2026-05-22T10:00:00Z",
        "updated_at": null
      }
    ]
  }
}
```

---

### 3.4 Edit Personal Food Entry

```
PUT /api/food/personal/{food_id}
```
Requires login. Users may only edit their own entries. Supports partial updates.

**Request Body (JSON, all fields optional)**

| Field | Type | Description |
|-------|------|-------------|
| name_zh | string | Food name in Chinese |
| name_en | string | Food name in English |
| calories | float | Calories per 100g (kcal) |
| protein_g | float | Protein per 100g (g) |
| fat_g | float | Fat per 100g (g) |
| carb_g | float | Carbohydrates per 100g (g) |
| sodium_mg | float | Sodium per 100g (mg) |
| fiber_g | float | Dietary fibre per 100g (g) |
| diet_labels | string[] | Diet labels |

**Response 200**
```json
{
  "code": 200,
  "data": {
    "food_id": 12,
    "name_zh": "螺蛳粉",
    "calories": 462,
    "updated_at": "2026-05-25T09:15:00Z"
  }
}
```

**Error 404**
```json
{ "code": 404, "error": "Food entry not found" }
```

---

### 3.5 Delete Personal Food Entry

```
DELETE /api/food/personal/{food_id}
```
Requires login. Users may only delete their own entries. Existing log entries that referenced this food are not affected — they retain their denormalised nutrition snapshot.

**Response 200**
```json
{ "code": 200, "data": { "deleted": true } }
```

**Error 404**
```json
{ "code": 404, "error": "Food entry not found" }
```

---

## 4. Diet Log

### 4.1 Add a Diet Entry

```
POST /api/diet/log
```
Requires login.

**Request Body (JSON)**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| food_source | string | ✅ | `static` (from food database) or `user` (from personal library) |
| food_id | int | ✅ | Food ID from the corresponding source |
| quantity_g | float | ✅ | Amount consumed (grams), must be > 0 |
| meal_type | string | ✅ | breakfast / lunch / dinner / snack |
| log_date | string(date) | ❌ | Format YYYY-MM-DD; defaults to today |

**Response 200**
```json
{
  "code": 200,
  "data": {
    "entry_id": 1001,
    "food_name": "Red-braised Pork Belly",
    "food_source": "static",
    "quantity_g": 150,
    "calories_kcal": 592.5,
    "protein_g": 21.9,
    "fat_g": 51.3,
    "carb_g": 9.6,
    "meal_type": "lunch",
    "log_date": "2026-05-22"
  }
}
```

---

### 4.2 Get Diet Log for a Day

```
GET /api/diet/log?date={YYYY-MM-DD}
```
Requires login.

**Response 200**
```json
{
  "code": 200,
  "data": {
    "date": "2026-05-22",
    "entries": [
      {
        "entry_id": 1001,
        "meal_type": "breakfast",
        "food_name": "Oatmeal",
        "food_source": "static",
        "quantity_g": 200,
        "calories_kcal": 136,
        "protein_g": 5.0,
        "fat_g": 2.6,
        "carb_g": 22.2
      }
    ],
    "daily_total": {
      "calories_kcal": 1450,
      "protein_g": 78.3,
      "fat_g": 52.1,
      "carb_g": 165.4
    },
    "goals": {
      "calorie_goal": 2000,
      "protein_goal_g": 120,
      "fat_goal_g": 65,
      "carb_goal_g": 250
    }
  }
}
```

---

### 4.3 Delete a Diet Entry

```
DELETE /api/diet/log/{entry_id}
```
Requires login. Users may only delete their own entries.

**Response 200**
```json
{ "code": 200, "data": { "deleted": true } }
```

---

## 5. Restaurant Search

### 5.1 Search Restaurants

```
GET /api/search
```

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| q | string | ❌ | Natural language query (at least one of `q` or `diet_labels` is required) |
| diet_labels | string | ❌ | Comma-separated, e.g. `vegan,gluten-free` |
| price_level | string | ❌ | Comma-separated, e.g. `1,2` |
| rating_min | float | ❌ | Minimum rating (0–5) |
| lat | float | ❌ | Latitude (used for distance sorting) |
| lng | float | ❌ | Longitude |
| sort | string | ❌ | default / diet_first / rating_first / distance_first |
| page | int | ❌ | Default 1 |
| page_size | int | ❌ | Default 10, max 20 |

**Response 200**
```json
{
  "code": 200,
  "data": {
    "total": 142,
    "page": 1,
    "page_size": 10,
    "query_parsed": {
      "text": "vegetarian",
      "diet_labels_detected": ["vegan", "vegetarian"],
      "spell_corrected": false
    },
    "facets": {
      "diet_labels": [
        { "label": "vegan", "count": 28 },
        { "label": "vegetarian", "count": 67 },
        { "label": "gluten-free", "count": 14 }
      ],
      "cuisine_types": [
        { "label": "Chinese", "count": 89 },
        { "label": "Japanese", "count": 21 }
      ],
      "price_level": [
        { "level": 1, "count": 32 },
        { "level": 2, "count": 58 }
      ]
    },
    "results": [
      {
        "restaurant_id": "r_001",
        "name": "Green Mood Vegetarian Restaurant",
        "cuisine_types": ["Chinese", "Vegetarian"],
        "diet_labels": ["vegan", "vegetarian"],
        "allergen_warning": null,
        "address": "88 Jianguo Rd, Chaoyang District",
        "price_level": 2,
        "rating": 4.6,
        "distance_m": 820,
        "relevance_score": 0.87,
        "diet_match_detail": {
          "matched_labels": ["vegan"],
          "confidence": "confirmed"
        },
        "highlights": {
          "name": ["<em>Vegetarian</em> Restaurant"],
          "description": ["Offers <em>fully vegan</em> set meals"]
        }
      }
    ],
    "spell_suggestion": null
  }
}
```

**Example result with allergen warning:**
```json
{
  "restaurant_id": "r_042",
  "name": "Sichuan Hot Pot",
  "allergen_warning": {
    "triggered_allergens": ["peanut", "shellfish"],
    "message": "This restaurant contains allergens you have flagged: peanuts, shellfish"
  }
}
```

---

### 5.2 Search Suggestions (Autocomplete)

```
GET /api/search/suggest?q={prefix}
```

**Response 200**
```json
{
  "code": 200,
  "data": {
    "suggestions": [
      { "text": "vegetarian restaurant", "type": "diet_keyword" },
      { "text": "vegan pizza", "type": "popular_query" },
      { "text": "gluten-free", "type": "diet_label" }
    ]
  }
}
```

---

## 6. Restaurant Details & Favorites

### 6.1 Get Restaurant Details

```
GET /api/restaurants/{restaurant_id}
```

**Response 200**
```json
{
  "code": 200,
  "data": {
    "restaurant_id": "r_001",
    "name": "Green Mood Vegetarian Restaurant",
    "description": "Dedicated to pure vegan cooking; all ingredients are organically certified...",
    "cuisine_types": ["Chinese", "Vegetarian"],
    "diet_labels": ["vegan", "vegetarian", "organic"],
    "allergen_free": ["gluten", "dairy"],
    "address": "88 Jianguo Rd, Chaoyang District",
    "geo": { "lat": 39.908, "lng": 116.465 },
    "price_level": 2,
    "rating": 4.6,
    "hours": { "open": "10:00", "close": "21:00" },
    "source": "amap",
    "menu_items": [
      {
        "item_id": "m_001",
        "name": "Signature Tofu Casserole",
        "description": "Organic tofu, low-calorie, high-protein",
        "diet_labels": ["vegan", "high-protein"],
        "allergens": [],
        "price": 38.0,
        "calories": 180,
        "protein_g": 12.0,
        "fat_g": 8.0,
        "carb_g": 14.0
      }
    ]
  }
}
```

---

### 6.2 Save a Restaurant

```
POST /api/restaurants/{restaurant_id}/save
```
Requires login.

**Response 200**
```json
{ "code": 200, "data": { "saved": true } }
```

---

### 6.3 Unsave a Restaurant

```
DELETE /api/restaurants/{restaurant_id}/save
```
Requires login.

**Response 200**
```json
{ "code": 200, "data": { "saved": false } }
```

---

### 6.4 Get Saved Restaurants

```
GET /api/restaurants/saved?page=1&page_size=10
```
Requires login.

**Response 200**
```json
{
  "code": 200,
  "data": {
    "total": 5,
    "items": [
      {
        "restaurant_id": "r_001",
        "restaurant_name": "Green Mood Vegetarian Restaurant",
        "saved_at": "2026-05-20T14:30:00Z"
      }
    ]
  }
}
```

---

## 7. Search Feedback

### 7.1 Submit Relevance Feedback

```
POST /api/feedback
```
Login optional (anonymous submissions are accepted).

**Request Body (JSON)**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query_text | string | ✅ | Original query string |
| restaurant_id | string | ✅ | ID of the restaurant being rated |
| restaurant_name | string | ✅ | Restaurant name (stored redundantly) |
| rank_position | int | ✅ | Position in the result list (starting from 1) |
| is_relevant | boolean | ✅ | true = relevant / false = not relevant |

**Response 200**
```json
{ "code": 200, "data": { "feedback_id": 88 } }
```

---

## 8. Crawler Management (Internal)

> ⚠️ The following endpoints are for administrator or script use only. In production, access should be restricted via IP allowlist or internal network.

### 8.1 Trigger a Crawl Job

```
POST /api/internal/crawler/run
```

**Request Body (JSON)**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| city | string | ✅ | City name, e.g. "Beijing" |
| source | string | ❌ | all / gaode / meituan; default all |
| limit | int | ❌ | Maximum number of restaurants to crawl; default 500 |

**Response 200**
```json
{
  "code": 200,
  "data": {
    "task_id": "crawl_20260522_001",
    "status": "started",
    "estimated_minutes": 30
  }
}
```

---

### 8.2 Check Crawl Job Status

```
GET /api/internal/crawler/status/{task_id}
```

**Response 200**
```json
{
  "code": 200,
  "data": {
    "task_id": "crawl_20260522_001",
    "status": "running",
    "progress": { "fetched": 320, "indexed": 298, "failed": 22, "total": 500 },
    "started_at": "2026-05-22T10:00:00Z"
  }
}
```

---

### 8.3 Rebuild Elasticsearch Index

```
POST /api/internal/index/rebuild
```

**Response 200**
```json
{ "code": 200, "data": { "message": "Index rebuild started; estimated completion time: 5 minutes" } }
```