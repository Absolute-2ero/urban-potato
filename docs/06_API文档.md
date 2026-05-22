# API 文档

**版本：** v1.0
**更新日期：** 2026-05-22

---

## 概述

- **Base URL：** `http://localhost:8000`（开发）/ `https://<host>`（生产）
- **协议：** HTTP / HTTPS
- **鉴权方式：** Cookie Session（`HttpOnly; SameSite=Lax`）
  - 需登录的接口须先调用 `POST /api/auth/login` 获取 Session
  - 未登录访问受保护接口返回 `401`
- **通用响应格式：**
  ```json
  { "code": 200, "data": { ... } }          // 成功
  { "code": 400, "error": "描述信息" }       // 客户端错误
  { "code": 401, "error": "请先登录" }       // 未授权
  { "code": 500, "error": "服务器内部错误" } // 服务端错误
  ```
- **分页参数：** `page`（从 1 起）、`page_size`（默认 10，最大 50）

---

## 目录

1. [用户认证](#1-用户认证)
2. [饮食档案](#2-饮食档案)
3. [食物数据库](#3-食物数据库)
4. [饮食日志](#4-饮食日志)
5. [餐厅搜索](#5-餐厅搜索)
6. [餐厅详情与收藏](#6-餐厅详情与收藏)
7. [搜索反馈](#7-搜索反馈)
8. [爬虫管理（内部）](#8-爬虫管理内部)

---

## 1. 用户认证

### 1.1 注册

```
POST /api/auth/register
```

**Request Body（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | ✅ | 用户名（唯一，4-32位，字母数字下划线） |
| password | string | ✅ | 明文密码（≥8位，含字母+数字） |
| email | string | ✅ | 邮箱 |

**Response 200**
```json
{
  "code": 200,
  "data": { "user_id": 1, "username": "alice" }
}
```

**Error 400**
```json
{ "code": 400, "error": "用户名已被占用" }
```

---

### 1.2 登录

```
POST /api/auth/login
```

**Request Body（JSON）**

| 字段 | 类型 | 必填 |
|------|------|------|
| username | string | ✅ |
| password | string | ✅ |

**Response 200**
```json
{ "code": 200, "data": { "user_id": 1, "username": "alice" } }
```

---

### 1.3 登出

```
POST /api/auth/logout
```
清除 Session。无需请求体。

**Response 200**
```json
{ "code": 200, "data": null }
```

---

### 1.4 获取当前用户信息

```
GET /api/auth/me
```
需登录。

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

## 2. 饮食档案

### 2.1 获取饮食档案

```
GET /api/diet/profile
```
需登录。

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
    "cuisine_prefs": ["中式", "日式"]
  }
}
```

---

### 2.2 更新饮食档案

```
PUT /api/diet/profile
```
需登录。支持部分更新（只传需要修改的字段）。

**Request Body（JSON，所有字段可选）**

| 字段 | 类型 | 说明 |
|------|------|------|
| diet_labels | string[] | 饮食类型，值须在预定义列表中 |
| allergens | string[] | 过敏原 |
| calorie_goal | int \| null | 每日热量目标（kcal） |
| protein_goal_g | float \| null | 蛋白质目标（g） |
| fat_goal_g | float \| null | 脂肪目标（g） |
| carb_goal_g | float \| null | 碳水目标（g） |
| price_pref | int(1-4) \| null | 价格偏好 |
| cuisine_prefs | string[] | 菜系偏好 |

**Response 200**
```json
{ "code": 200, "data": { "updated": true } }
```

---

## 3. 食物数据库

### 3.1 搜索食物

```
GET /api/food/search?q={query}&limit=10
```

**Query Parameters**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| q | string | ✅ | 食物名称（支持中文/拼音/英文） |
| limit | int | ❌ | 返回数量，默认 10，最大 20 |

**Response 200 — 数据库命中**
```json
{
  "code": 200,
  "data": {
    "source": "database",
    "requires_confirm": false,
    "items": [
      {
        "food_id": 42,
        "name_zh": "红烧肉",
        "name_en": "Red-braised Pork Belly",
        "calories": 395,
        "protein_g": 14.6,
        "fat_g": 34.2,
        "carb_g": 6.4,
        "diet_labels": [],
        "source": "static"
      }
    ]
  }
}
```

**Response 200 — LLM 估算（需用户确认）**
```json
{
  "code": 200,
  "data": {
    "source": "llm_estimated",
    "requires_confirm": true,
    "items": [
      {
        "food_id": null,
        "name_zh": "螺蛳粉",
        "name_en": "River Snail Rice Noodle",
        "calories": 458,
        "protein_g": 18.0,
        "fat_g": 15.0,
        "carb_g": 62.0,
        "diet_labels": [],
        "source": "llm_inferred"
      }
    ]
  }
}
```

---

### 3.2 确认 LLM 数据入库

```
POST /api/food/confirm
```
需登录。将 LLM 估算数据写入食物数据库（经用户确认后）。

**Request Body（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name_zh | string | ✅ | 食物中文名 |
| name_en | string | ❌ | 英文名 |
| calories | float | ✅ | 每 100g 热量 |
| protein_g | float | ✅ | 蛋白质（g） |
| fat_g | float | ✅ | 脂肪（g） |
| carb_g | float | ✅ | 碳水（g） |
| diet_labels | string[] | ❌ | 饮食标签 |

**Response 200**
```json
{
  "code": 200,
  "data": { "food_id": 501, "name_zh": "螺蛳粉", "already_existed": false }
}
```

**Response 200（已存在时）**
```json
{
  "code": 200,
  "data": { "food_id": 198, "name_zh": "螺蛳粉", "already_existed": true }
}
```

---

## 4. 饮食日志

### 4.1 添加饮食记录

```
POST /api/diet/log
```
需登录。

**Request Body（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| food_id | int | ✅ | 食物 ID（来自 food_items） |
| quantity_g | float | ✅ | 食用量（克），> 0 |
| meal_type | string | ✅ | breakfast / lunch / dinner / snack |
| log_date | string(date) | ❌ | 格式 YYYY-MM-DD，默认今日 |

**Response 200**
```json
{
  "code": 200,
  "data": {
    "entry_id": 1001,
    "food_name": "红烧肉",
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

### 4.2 获取某日饮食记录

```
GET /api/diet/log?date={YYYY-MM-DD}
```
需登录。

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
        "food_name": "燕麦粥",
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

### 4.3 删除饮食记录

```
DELETE /api/diet/log/{entry_id}
```
需登录。只能删除自己的记录。

**Response 200**
```json
{ "code": 200, "data": { "deleted": true } }
```

---

## 5. 餐厅搜索

### 5.1 搜索餐厅

```
GET /api/search
```

**Query Parameters**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| q | string | ❌ | 自然语言查询词（与 diet_labels 至少有一个） |
| diet_labels | string | ❌ | 逗号分隔，如 `vegan,gluten-free` |
| price_level | string | ❌ | 逗号分隔，如 `1,2` |
| rating_min | float | ❌ | 最低评分（0-5） |
| lat | float | ❌ | 纬度（用于距离排序） |
| lng | float | ❌ | 经度 |
| sort | string | ❌ | default / diet_first / rating_first / distance_first |
| page | int | ❌ | 默认 1 |
| page_size | int | ❌ | 默认 10，最大 20 |

**Response 200**
```json
{
  "code": 200,
  "data": {
    "total": 142,
    "page": 1,
    "page_size": 10,
    "query_parsed": {
      "text": "素食",
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
        { "label": "中式", "count": 89 },
        { "label": "日式", "count": 21 }
      ],
      "price_level": [
        { "level": 1, "count": 32 },
        { "level": 2, "count": 58 }
      ]
    },
    "results": [
      {
        "restaurant_id": "r_001",
        "name": "绿色心情素食餐厅",
        "cuisine_types": ["中式", "素食"],
        "diet_labels": ["vegan", "vegetarian"],
        "allergen_warning": null,
        "address": "朝阳区建国路88号",
        "price_level": 2,
        "rating": 4.6,
        "distance_m": 820,
        "relevance_score": 0.87,
        "diet_match_detail": {
          "matched_labels": ["vegan"],
          "confidence": "confirmed"
        },
        "highlights": {
          "name": ["<em>素食</em>餐厅"],
          "description": ["提供<em>纯素</em>套餐"]
        }
      }
    ],
    "spell_suggestion": null
  }
}
```

**含过敏原警告的结果示例：**
```json
{
  "restaurant_id": "r_042",
  "name": "川味火锅",
  "allergen_warning": {
    "triggered_allergens": ["peanut", "shellfish"],
    "message": "该餐厅含有您标注的过敏原：花生、贝壳类海鲜"
  }
}
```

---

### 5.2 搜索建议（Autocomplete）

```
GET /api/search/suggest?q={prefix}
```

**Response 200**
```json
{
  "code": 200,
  "data": {
    "suggestions": [
      { "text": "素食餐厅", "type": "diet_keyword" },
      { "text": "vegan pizza", "type": "popular_query" },
      { "text": "gluten-free", "type": "diet_label" }
    ]
  }
}
```

---

## 6. 餐厅详情与收藏

### 6.1 获取餐厅详情

```
GET /api/restaurants/{restaurant_id}
```

**Response 200**
```json
{
  "code": 200,
  "data": {
    "restaurant_id": "r_001",
    "name": "绿色心情素食餐厅",
    "description": "专注纯素烹饪，所有食材均为有机认证...",
    "cuisine_types": ["中式", "素食"],
    "diet_labels": ["vegan", "vegetarian", "organic"],
    "allergen_free": ["gluten", "dairy"],
    "address": "朝阳区建国路88号",
    "geo": { "lat": 39.908, "lng": 116.465 },
    "price_level": 2,
    "rating": 4.6,
    "hours": { "open": "10:00", "close": "21:00" },
    "source": "dianping",
    "menu_items": [
      {
        "item_id": "m_001",
        "name": "招牌豆腐煲",
        "description": "有机豆腐，低热量高蛋白",
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

### 6.2 收藏餐厅

```
POST /api/restaurants/{restaurant_id}/save
```
需登录。

**Response 200**
```json
{ "code": 200, "data": { "saved": true } }
```

---

### 6.3 取消收藏

```
DELETE /api/restaurants/{restaurant_id}/save
```
需登录。

**Response 200**
```json
{ "code": 200, "data": { "saved": false } }
```

---

### 6.4 获取收藏列表

```
GET /api/restaurants/saved?page=1&page_size=10
```
需登录。

**Response 200**
```json
{
  "code": 200,
  "data": {
    "total": 5,
    "items": [
      {
        "restaurant_id": "r_001",
        "restaurant_name": "绿色心情素食餐厅",
        "saved_at": "2026-05-20T14:30:00Z"
      }
    ]
  }
}
```

---

## 7. 搜索反馈

### 7.1 提交相关性反馈

```
POST /api/feedback
```
登录可选（匿名也可提交）。

**Request Body（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query_text | string | ✅ | 原始查询词 |
| restaurant_id | string | ✅ | 被反馈的餐厅 ID |
| restaurant_name | string | ✅ | 餐厅名（冗余存储） |
| rank_position | int | ✅ | 结果排名位置（从 1 起） |
| is_relevant | boolean | ✅ | true=相关 / false=不相关 |

**Response 200**
```json
{ "code": 200, "data": { "feedback_id": 88 } }
```

---

## 8. 爬虫管理（内部）

> ⚠️ 以下接口仅供管理员或脚本调用，生产环境应限制访问（IP 白名单或内网调用）

### 8.1 触发爬取任务

```
POST /api/internal/crawler/run
```

**Request Body（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| city | string | ✅ | 城市名，如 "北京" |
| source | string | ❌ | all / gaode / dianping / meituan，默认 all |
| limit | int | ❌ | 最多爬取餐厅数，默认 500 |

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

### 8.2 查询爬取任务状态

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

### 8.3 重建 Elasticsearch 索引

```
POST /api/internal/index/rebuild
```

**Response 200**
```json
{ "code": 200, "data": { "message": "索引重建已启动，预计耗时 5 分钟" } }
```
