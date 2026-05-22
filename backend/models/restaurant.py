from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class GeoPoint(BaseModel):
    lat: float
    lng: float


class MenuItem(BaseModel):
    item_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    diet_labels: List[str] = []
    allergens: List[str] = []
    price: Optional[float] = None
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carb_g: Optional[float] = None


class AllergenWarning(BaseModel):
    triggered_allergens: List[str]
    message: str


class DietMatchDetail(BaseModel):
    matched_labels: List[str]
    confidence: str  # "confirmed" | "inferred"


class Restaurant(BaseModel):
    restaurant_id: str
    name: str
    description: Optional[str] = None
    cuisine_type: Optional[str] = None
    diet_labels: List[str] = []
    allergen_free: List[str] = []
    allergens: List[str] = []
    address: Optional[str] = None
    phone: Optional[str] = None
    geo: Optional[GeoPoint] = None
    price_level: Optional[int] = None
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    business_hours: List[str] = []
    images: List[str] = []
    source: Optional[str] = None
    menu_items: List[MenuItem] = []


class Facets(BaseModel):
    # key → 文档数（dict 格式，便于前端处理）
    diet_labels: Dict[str, int] = {}
    price_level: Dict[str, int] = {}
    cuisine_type: Dict[str, int] = {}


class SearchParams(BaseModel):
    q: str = ""
    diet_labels: List[str] = []
    price_levels: List[int] = []
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_km: Optional[float] = 5.0
    sort_mode: str = "default"
    offset: int = 0
    limit: int = 20


class QueryParsed(BaseModel):
    text: str
    diet_labels_detected: List[str] = []
    spell_corrected: bool = False
    spell_suggestion: Optional[str] = None


class SearchResponse(BaseModel):
    total: int
    hits: List[Dict[str, Any]]          # ES raw hits（含 _source, _score, _final_score 等）
    facets: Facets
    spell_suggestion: Optional[str] = None
    detected_diet_labels: List[str] = []
    query_tokens: List[str] = []
    sort_mode: str = "default"
    offset: int = 0
    limit: int = 20
    crawl_triggered: bool = False       # 是否触发了实时爬虫（供前端展示提示）
