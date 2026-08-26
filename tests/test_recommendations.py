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


class ManyVariantsCatalog:
    def all(self) -> list[CatalogModel]:
        return [
            CatalogModel(
                model_id="many-variants",
                name="Many Variants",
                ollama_tag=f"many:{index}",
                family="many",
                parameter_count_b=index,
                size_gb=1,
                estimated_runtime_gb=1,
                quantization="Q4_K_M",
                context_length=32768,
                use_cases=("chat",),
                quality_score=80,
                description="Variant cap test model.",
            )
            for index in range(1, 7)
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


def test_recommendations_return_best_variant_and_two_alternatives(monkeypatch) -> None:
    def fake_score(model, hardware, use_case, capacity):
        return 70 + int(model.ollama_tag.split(":")[1]), "recommended"

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

    response = recommendation_service.recommend_models(request, ManyVariantsCatalog())
    model = response.recommendations["all"][0]

    assert model.best_variant.ollama_tag == "many:6"
    assert [variant.ollama_tag for variant in model.variants] == ["many:6", "many:5", "many:4"]
