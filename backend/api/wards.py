from fastapi import APIRouter
from models.ward import WardListResponse, WardBase
from db.wards import get_all_wards
from utils.cache import cache

router = APIRouter()
CACHE_KEY = "wards:all"


@router.get("/wards", response_model=WardListResponse, tags=["wards"])
async def list_wards():
    """
    Returns all 198 BBMP ward names and IDs.
    Used for map search autocomplete. Cached 24 hours — data never changes.
    """
    cached = cache.get(CACHE_KEY)
    if cached:
        return cached

    wards = get_all_wards()
    response = WardListResponse(
        wards=[WardBase(**w) for w in wards],
        total=len(wards),
    )
    cache.set(CACHE_KEY, response, ttl_seconds=86400)
    return response
