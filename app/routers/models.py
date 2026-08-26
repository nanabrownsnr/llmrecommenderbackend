from fastapi import APIRouter
from app.schemas import RecommendationRequest, RecommendationResponse
from app.services.recommendations import recommend_models

router = APIRouter(tags=["recommendations"])

@router.post("/recommendations", response_model=RecommendationResponse)
def recommendations(request: RecommendationRequest) -> RecommendationResponse:
    return recommend_models(request)
