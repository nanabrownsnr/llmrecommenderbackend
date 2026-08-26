import base64
import json
from collections import defaultdict

from app.catalog.llm_checker import LLMCheckerCatalog
from app.domain.hardware import normalize_hardware
from app.schemas import ModelRecommendation, RecommendedVariant, RecommendationRequest, RecommendationResponse, UseCase
from app.services.scoring import score_model

USE_CASES = tuple(item.value for item in UseCase)
MIN_RECOMMENDATION_SCORE = 70.0

def _decode_cursor(cursor: str | None) -> int:
    if not cursor: return 0
    try: return max(0, int(json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())["offset"]))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError): return 0

def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"offset": offset}, separators=(",", ":")).encode()).decode()

def recommend_models(request: RecommendationRequest, repository=None) -> RecommendationResponse:
    catalog = repository or LLMCheckerCatalog()
    hardware = normalize_hardware(request.hardware)
    capacity = hardware.ram_gb * request.memory_utilization
    compatible = [model for model in catalog.all() if 0 < model.estimated_runtime_gb <= capacity]
    results: dict[str, list[ModelRecommendation]] = {}
    cursors: dict[str, str | None] = {}
    selected = request.use_case.value
    for use_case in USE_CASES:
        scored = []
        for model in compatible:
            score, fit = score_model(model, hardware, UseCase(use_case), capacity)
            if score >= MIN_RECOMMENDATION_SCORE:
                scored.append((model.model_id, score, fit, model))
        grouped: dict[str, list[tuple[float, str, object]]] = defaultdict(list)
        for base_id, score, fit, model in scored: grouped[base_id].append((score, fit, model))
        groups = []
        for base_id, variants in grouped.items():
            variants.sort(key=lambda item: (-item[0], item[2].estimated_runtime_gb, item[2].ollama_tag))
            best_score, best_fit, best = variants[0]
            group = ModelRecommendation(modelId=base_id, name=best.name, description=best.description, fit=best_fit,
                bestVariant=RecommendedVariant(ollamaTag=best.ollama_tag, sizeGB=best.size_gb, estimatedRuntimeGB=best.estimated_runtime_gb, fit=best_fit, score=round(best_score, 2)),
                variants=[RecommendedVariant(ollamaTag=m.ollama_tag, sizeGB=m.size_gb, estimatedRuntimeGB=m.estimated_runtime_gb, fit=fit, score=round(score, 2)) for score, fit, m in variants])
            groups.append((best_score, group))
        groups.sort(key=lambda item: (-item[0], item[1].model_id))
        offset = _decode_cursor(request.cursor) if use_case == selected else 0
        page = groups[offset:offset + request.limit]
        results[use_case] = [group for _, group in page]
        cursors[use_case] = _encode_cursor(offset + request.limit) if offset + request.limit < len(groups) else None
    return RecommendationResponse(recommendations=results, nextCursors=cursors)
