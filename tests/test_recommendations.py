from app.domain.catalog import CatalogModel
from app.schemas import RecommendationRequest
from app.services import recommendations as recommendation_service


class StubCatalog:
    def all(self) -> list[CatalogModel]:
        common = {
            "model_id": "threshold-model",
            "name": "Threshold Model",
            "family": "threshold",
            "parameter_count_b": 3,
            "size_gb": 2,
            "estimated_runtime_gb": 2.4,
            "quantization": "Q4_K_M",
            "context_length": 32768,
            "use_cases": ("chat",),
            "quality_score": 75,
            "description": "Threshold test model.",
        }
        return [
            CatalogModel(ollama_tag="threshold:below", **common),
            CatalogModel(ollama_tag="threshold:boundary", **common),
        ]


def test_recommendations_exclude_variants_scoring_below_70(monkeypatch) -> None:
    def fake_score(model, hardware, use_case, capacity):
        score = 69.99 if model.ollama_tag.endswith("below") else 70.0
        return score, "recommended"

    monkeypatch.setattr(recommendation_service, "score_model", fake_score)
    request = RecommendationRequest.model_validate({
        "hardware": {
            "cpu": {"logicalThreads": 8, "model": "test"},
            "memory": {"approximateGB": 8},
            "system": {"platform": "Windows", "architecture": "x86_64", "bitness": "64"},
            "gpu": {"status": "GPU detected", "confidence": "High", "renderer": "ANGLE"},
        },
        "useCase": "all",
        "memoryUtilization": 0.5,
    })

    response = recommendation_service.recommend_models(request, StubCatalog())

    assert response.recommendations["all"][0].best_variant.score == 70.0
    assert [variant.ollama_tag for variant in response.recommendations["all"][0].variants] == ["threshold:boundary"]
