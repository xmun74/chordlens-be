from fastapi import APIRouter
from app.models.result import ResultDetail, ResultListResponse
from app.services.result_service import get_result, get_popular_results, increment_view, list_results

router = APIRouter()


@router.get("/results", response_model=ResultListResponse)
async def get_results(limit: int = 20, offset: int = 0) -> ResultListResponse:
    return await list_results(limit=limit, offset=offset)


@router.get("/results/popular", response_model=ResultListResponse)
async def get_popular(limit: int = 10) -> ResultListResponse:
    return await get_popular_results(limit=limit)


@router.get("/results/{id}", response_model=ResultDetail)
async def get_result_by_id(id: str) -> ResultDetail:
    return await get_result(id)


@router.post("/results/{id}/view", status_code=204)
async def record_view(id: str) -> None:
    await increment_view(id)
