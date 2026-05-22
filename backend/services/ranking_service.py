from __future__ import annotations

import logging
import math
import os
from typing import Any, Dict, List, Optional, Tuple

import yaml

from config import cfg

logger = logging.getLogger(__name__)


class RankingService:
    def __init__(self) -> None:
        config_path = os.path.normpath(cfg.ranking_config_path)
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._modes: Dict[str, Dict[str, float]] = data["sort_modes"]
        logger.info("RankingService loaded %d sort modes", len(self._modes))

    def get_weights(self, sort_mode: str) -> Dict[str, float]:
        return self._modes.get(sort_mode, self._modes["default"])

    # ── 各维度评分 ─────────────────────────────────────────────────────────────

    @staticmethod
    def calc_diet_score(
        diet_labels: List[str],
        allergens: List[str],
        allergen_free: List[str],
        query_diet_labels: List[str],
        user_allergens: List[str],
    ) -> float:
        score = 0.0
        # 正向：餐厅标签命中查询
        for label in query_diet_labels:
            if label in diet_labels:
                score += 1.0
        # 正向：声明不含用户过敏原
        for allergen in user_allergens:
            if allergen in allergen_free:
                score += 0.5
        # 惩罚：含有用户过敏原
        for allergen in user_allergens:
            if allergen in allergens:
                score -= 2.0
        return max(score, -2.0)

    @staticmethod
    def calc_rating_score(rating: Optional[float]) -> float:
        if rating is None:
            return 0.5  # 无评分时给中间值
        return min(max(rating / 5.0, 0.0), 1.0)

    @staticmethod
    def calc_distance_score(
        restaurant_geo: Optional[Dict[str, float]],
        user_geo: Optional[Tuple[float, float]],
        scale_km: float = 2.0,
    ) -> float:
        """高斯距离衰减，scale_km 内衰减至 e^-1 ≈ 0.37。"""
        if restaurant_geo is None or user_geo is None:
            return 0.5
        lat1, lng1 = user_geo
        lat2 = restaurant_geo.get("lat", lat1)
        lng2 = restaurant_geo.get("lng", lng1)
        # 简化球面距离（Haversine 近似，误差 < 0.5% in < 100km）
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        dist_km = 6371 * 2 * math.asin(math.sqrt(a))
        return math.exp(-((dist_km / scale_km) ** 2) / 2)

    # ── 重排序入口 ─────────────────────────────────────────────────────────────

    def rerank(
        self,
        hits: List[Dict[str, Any]],
        query_diet_labels: List[str],
        user_allergens: List[str],
        user_geo: Optional[Tuple[float, float]],
        sort_mode: str = "default",
    ) -> List[Dict[str, Any]]:
        weights = self.get_weights(sort_mode)

        for hit in hits:
            src = hit.get("_source", {})
            text_score = hit.get("_score") or 0.0

            diet_score = self.calc_diet_score(
                src.get("diet_labels", []),
                src.get("allergens", []),
                src.get("allergen_free", []),
                query_diet_labels,
                user_allergens,
            )
            rating_score = self.calc_rating_score(src.get("rating"))
            distance_score = self.calc_distance_score(src.get("geo"), user_geo)

            # 归一化 text_score（ES BM25 无上界，简单截断到 0-1）
            norm_text = min(text_score / 10.0, 1.0) if text_score else 0.0

            hit["_final_score"] = (
                weights["text_score"]      * norm_text
                + weights["diet_score"]    * (diet_score + 2.0) / 4.0   # 映射 [-2,2]→[0,1]
                + weights["rating_score"]  * rating_score
                + weights["distance_score"]* distance_score
            )

            # 附加距离（米）
            if user_geo and src.get("geo"):
                lat1, lng1 = user_geo
                lat2 = src["geo"].get("lat", lat1)
                lng2 = src["geo"].get("lng", lng1)
                dlat = math.radians(lat2 - lat1)
                dlng = math.radians(lng2 - lng1)
                a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
                hit["_distance_m"] = round(6371000 * 2 * math.asin(math.sqrt(a)))

            # 过敏原警告
            triggered = [a for a in user_allergens if a in src.get("allergens", [])]
            hit["_allergen_warning"] = triggered

        return sorted(hits, key=lambda h: h["_final_score"], reverse=True)
