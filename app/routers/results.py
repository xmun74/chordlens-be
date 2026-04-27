from fastapi import APIRouter
from app.models.result import ResultDetail, ResultListResponse
from app.services.result_service import get_result, list_results

router = APIRouter()


@router.get("/results", response_model=ResultListResponse)
async def get_results(limit: int = 20, offset: int = 0) -> ResultListResponse:
    return await list_results(limit=limit, offset=offset)


@router.get("/results/{id}", response_model=ResultDetail)
async def get_result_by_id(id: str) -> ResultDetail:
    return await get_result(id)
