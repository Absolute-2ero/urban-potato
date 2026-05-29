from __future__ import annotations

"""
LLM 菜品营养 / 饮食标签分析器。

使用 OpenAI 兼容 SDK，支持任意兼容接口的 LLM：
  - Gemini:   LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
  - DeepSeek: LLM_BASE_URL=https://api.deepseek.com
  - Qwen:     LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

在 .env 中配置（与项目其他 LLM 调用共享同一套配置）：
    LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
    LLM_API_KEY=your_key_here
    LLM_MODEL=gemini-1.5-flash

图片支持：使用 OpenAI vision 格式（base64 data URL）。
仅视觉模型（Gemini、GPT-4V 等）支持图片；DeepSeek 等纯文字模型
遇到图片会报错，此时自动降级为纯文字模式。

在 pipeline 中使用：
    python -m crawler.pipeline --city 北京 --eleme --gemini
"""

import asyncio
import base64
import json
import logging
import re
from typing import Any

import httpx

from config import cfg

logger = logging.getLogger(__name__)

_BATCH_SIZE  = 10      # 每次 API 调用处理的菜品数
_RATE_DELAY  = 4.0     # 批次间等待秒数（Gemini 免费层 15 RPM）

_VALID_DIET_LABELS = {
    "vegan", "vegetarian", "halal", "kosher", "organic",
    "gluten-free", "dairy-free", "keto", "high-protein",
    "low-carb", "low-calorie", "low-sodium", "nut-free",
    "shellfish-free", "soy-free", "light-meal",
}
_VALID_ALLERGENS = {
    "peanut", "tree_nut", "dairy", "gluten",
    "shellfish", "soy", "egg", "sesame", "fish",
}

_SYSTEM_PROMPT = (
    "You are a professional nutritionist specializing in Chinese and Hong Kong cuisine. "
    "For each dish listed, estimate nutritional content per typical single serving. "
    "Respond ONLY with a valid JSON array — one object per dish in the same order. "
    "No explanation, no markdown fences, raw JSON only.\n\n"
    "Each object must have:\n"
    '  "name_en":     string (English name — translate if Chinese, keep if already English)\n'
    '  "name_zh":     string (Traditional Chinese name — translate if English, keep if already Chinese)\n'
    '  "calories":    integer (kcal)\n'
    '  "protein":     float (grams, 1 decimal)\n'
    '  "fat":         float (grams, 1 decimal)\n'
    '  "carbs":       float (grams, 1 decimal)\n'
    '  "diet_labels": array from [vegan, vegetarian, halal, kosher, organic, '
    "gluten-free, dairy-free, keto, high-protein, low-carb, low-calorie, "
    "low-sodium, nut-free, shellfish-free, soy-free, light-meal]\n"
    '  "allergens":   array from [peanut, tree_nut, dairy, gluten, '
    "shellfish, soy, egg, sesame, fish]"
)


def _build_dish_list(dishes: list[dict]) -> str:
    lines = ["Dishes:"]
    for i, d in enumerate(dishes, 1):
        line = f"{i}. {d.get('name', 'Unknown')}"
        if d.get("description"):
            line += f" — {d['description'].strip()}"
        if d.get("price"):
            line += f" (¥{d['price']})"
        lines.append(line)
    return "\n".join(lines)


async def _fetch_b64(url: str) -> str | None:
    """Fetch image and return as base64 string."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return base64.b64encode(resp.content).decode()
    except Exception as exc:
        logger.debug("Image fetch failed %s: %s", url[:60], exc)
        return None


def _parse_response(text: str, n: int) -> list[dict]:
    text = re.sub(r"```json|```", "", text).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data[:n]
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())[:n]
            except json.JSONDecodeError:
                pass
    logger.warning("Could not parse LLM response as JSON array")
    return []


def _sanitize(result: dict) -> dict:
    def _f(v, default=0.0):
        try:
            return round(float(v), 1)
        except (TypeError, ValueError):
            return default
    name_en = result.get("name_en", "")
    name_zh = result.get("name_zh", "")
    return {
        "name_en":     name_en if isinstance(name_en, str) else "",
        "name_zh":     name_zh if isinstance(name_zh, str) else "",
        "calories":    int(_f(result.get("calories"), 0)),
        "protein":     _f(result.get("protein")),
        "fat":         _f(result.get("fat")),
        "carbs":       _f(result.get("carbs")),
        "diet_labels": [l for l in result.get("diet_labels", []) if l in _VALID_DIET_LABELS],
        "allergens":   [a for a in result.get("allergens",   []) if a in _VALID_ALLERGENS],
    }


async def _call_llm(dishes: list[dict]) -> list[dict]:
    if not cfg.llm_api_key:
        logger.warning("LLM_API_KEY not set — skipping nutrition analysis")
        return [{} for _ in dishes]

    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.warning("openai package not installed. Run: pip install openai")
        return [{} for _ in dishes]

    client = AsyncOpenAI(base_url=cfg.llm_base_url, api_key=cfg.llm_api_key)

    content: list[dict] = [
        {"type": "text", "text": _SYSTEM_PROMPT},
        {"type": "text", "text": "\n\n" + _build_dish_list(dishes)},
    ]

    # Image sending disabled — re-enable to use vision models (costs extra tokens)
    # for d in dishes:
    #     img_url = d.get("image_url")
    #     if img_url:
    #         b64 = await _fetch_b64(img_url)
    #         if b64:
    #             mime = "image/png" if img_url.endswith(".png") else "image/jpeg"
    #             content.append({
    #                 "type": "image_url",
    #                 "image_url": {"url": f"data:{mime};base64,{b64}"},
    #             })

    messages = [{"role": "user", "content": content}]

    try:
        response = await client.chat.completions.create(
            model=cfg.llm_model,
            messages=messages,
        )
        raw = response.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        return [{} for _ in dishes]

    results = _parse_response(raw, len(dishes))
    while len(results) < len(dishes):
        results.append({})
    return [_sanitize(r) for r in results]


async def translate_restaurant_name(doc: dict[str, Any]) -> None:
    """Add name_en (English) and name_zh (Chinese) to the restaurant doc if missing."""
    if doc.get("name_en"):
        return
    name = doc.get("name", "")
    if not name:
        return
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(base_url=cfg.llm_base_url, api_key=cfg.llm_api_key)
        resp = await client.chat.completions.create(
            model=cfg.llm_model,
            messages=[{"role": "user", "content": (
                f'Translate this restaurant name to English. '
                f'Reply with ONLY the English name, nothing else.\n\nName: {name}'
            )}],
        )
        name_en = (resp.choices[0].message.content or "").strip().strip('"\'')
        if name_en:
            doc["name_en"] = name_en
    except Exception as exc:
        logger.debug("Restaurant name translation failed for %r: %s", name, exc)


async def label_menu_items_batch(doc: dict[str, Any]) -> None:
    """
    Analyze all menu items in a restaurant doc.
    Writes nutrition + labels back into each item and aggregates
    diet_labels up to the restaurant level.
    """
    items = doc.get("menu_items", [])
    if not items:
        return

    all_labels: list[str] = []

    for start in range(0, len(items), _BATCH_SIZE):
        batch = items[start: start + _BATCH_SIZE]
        results = await _call_llm(batch)

        for item, nutrition in zip(batch, results):
            if not nutrition:
                continue
            item.update(nutrition)
            all_labels.extend(item.get("diet_labels", []))

        if start + _BATCH_SIZE < len(items):
            await asyncio.sleep(_RATE_DELAY)

    doc["diet_labels"] = list(set(doc.get("diet_labels", [])) | set(all_labels))
    logger.info("LLM labeled %d items for %r — labels: %s",
                len(items), doc.get("name"), doc["diet_labels"])
