from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["cities"])


class GeoPoint(BaseModel):
    lat: float
    lng: float


class City(BaseModel):
    id: str
    label: str
    center: GeoPoint


_CITIES: list[City] = [
    City(id="beijing", label="北京", center=GeoPoint(lat=39.9042, lng=116.4074)),
]


@router.get("/cities", response_model=list[City])
def list_cities():
    return _CITIES
